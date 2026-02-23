#!/usr/bin/env python3
"""
Flask 웹 대시보드 서버
브라우저에서 localhost:5000 접속해서 모든 설정 가능
"""

import os
import json
import sys
import uuid
import smtplib
import datetime
import threading
import subprocess
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

app = Flask(__name__)

# ─────────────────────────────────────────────
# 경로 설정
# ─────────────────────────────────────────────
DATA_DIR = Path("stock_agent_data")
WATCHLIST_FILE = DATA_DIR / "watchlist.json"
REPORTS_DIR = DATA_DIR / "reports"
CONFIG_FILE = DATA_DIR / "config.json"
USERS_FILE = DATA_DIR / "users.json"

DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────
# 설정 관리
# ─────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
        "gmail_user": "",
        "gmail_app_password": "",
        "email_recipient": "",
        "schedule_hour": 9,
        "schedule_minute": 0
    }


def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_watchlist() -> dict:
    if WATCHLIST_FILE.exists():
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"stocks": [], "industries": []}


def save_watchlist(watchlist: dict):
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)


def load_users() -> list:
    if USERS_FILE.exists():
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_users(users: list):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# 라우트: 메인 페이지
# ─────────────────────────────────────────────
@app.route("/")
def index():
    config = load_config()
    watchlist = load_watchlist()
    reports = sorted(REPORTS_DIR.glob("*.md"), reverse=True)[:10]
    
    report_list = []
    for r in reports:
        parts = r.stem.split("_", 2)
        if len(parts) >= 3:
            d, t, name = parts
            date_str = f"{d[:4]}-{d[4:6]}-{d[6:]} {t[:2]}:{t[2:4]}"
            report_list.append({"filename": r.name, "date": date_str, "name": name})
    
    return render_template("index.html",
                         config=config,
                         watchlist=watchlist,
                         reports=report_list)


# ─────────────────────────────────────────────
# API: 설정 저장
# ─────────────────────────────────────────────
@app.route("/api/save_config", methods=["POST"])
def api_save_config():
    data = request.json
    config = load_config()

    if "gemini_api_key" in data:
        config["gemini_api_key"] = data["gemini_api_key"].strip()
    if "gmail_user" in data:
        config["gmail_user"] = data["gmail_user"].strip()
    if "gmail_app_password" in data:
        # Google 앱 비밀번호는 "xxxx xxxx xxxx xxxx" 형식으로 표시되므로 공백 제거
        config["gmail_app_password"] = data["gmail_app_password"].replace(" ", "").strip()
    if "email_recipient" in data:
        config["email_recipient"] = data["email_recipient"].strip()
    if "schedule_hour" in data:
        config["schedule_hour"] = int(data["schedule_hour"])
    if "schedule_minute" in data:
        config["schedule_minute"] = int(data["schedule_minute"])

    save_config(config)
    return jsonify({"success": True, "message": "설정이 저장되었습니다."})


# ─────────────────────────────────────────────
# API: 관심 목록 저장
# ─────────────────────────────────────────────
@app.route("/api/save_watchlist", methods=["POST"])
def api_save_watchlist():
    data = request.json
    watchlist = {
        "stocks": data.get("stocks", []),
        "industries": data.get("industries", [])
    }
    save_watchlist(watchlist)
    return jsonify({"success": True, "message": "관심 목록이 저장되었습니다."})


# ─────────────────────────────────────────────
# API: Gmail 테스트 전송
# ─────────────────────────────────────────────
@app.route("/api/test_email", methods=["POST"])
def api_test_email():
    config = load_config()
    gmail_user = config.get("gmail_user", "").strip()
    # Google 앱 비밀번호 공백 제거 ("xxxx xxxx xxxx xxxx" 형식 대비)
    app_password = config.get("gmail_app_password", "").replace(" ", "").strip()
    recipient = config.get("email_recipient", "").strip() or gmail_user

    if not gmail_user or not app_password:
        return jsonify({"success": False, "message": "Gmail 계정 정보를 먼저 입력하세요."})

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "📈 주식 리서치 에이전트 — 연결 테스트"
        msg["From"] = f"주식 리서치 에이전트 <{gmail_user}>"
        msg["To"] = recipient

        html = """<div style="font-family:'Malgun Gothic',sans-serif;max-width:500px;margin:0 auto;padding:24px;">
  <div style="background:linear-gradient(135deg,#1a73e8,#0b3d91);color:#fff;padding:20px;border-radius:10px;">
    <h2 style="margin:0">📈 주식 리서치 에이전트</h2>
    <p style="margin:6px 0 0;opacity:.85">웹 대시보드 • 연결 테스트 성공 ✅</p>
  </div>
  <p style="margin-top:20px">매일 설정한 시간에 리서치 리포트가 이 메일로 전송됩니다.</p>
</div>"""

        msg.attach(MIMEText("Gmail 연결 테스트 성공!", "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        # SMTP_SSL 포트 465, timeout 10초
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(gmail_user, app_password)
            server.sendmail(gmail_user, recipient, msg.as_string())

        return jsonify({"success": True, "message": f"테스트 이메일이 {recipient}로 전송되었습니다!"})

    except smtplib.SMTPAuthenticationError:
        return jsonify({"success": False,
                        "message": "Gmail 인증 실패 — 앱 비밀번호를 확인하세요.\n"
                                   "(Google 계정 → 보안 → 2단계 인증 → 앱 비밀번호)"})
    except smtplib.SMTPRecipientsRefused:
        return jsonify({"success": False,
                        "message": f"수신자 주소가 거부되었습니다: {recipient}"})
    except smtplib.SMTPSenderRefused:
        return jsonify({"success": False,
                        "message": f"발신자 주소가 거부되었습니다: {gmail_user}"})
    except smtplib.SMTPException as e:
        return jsonify({"success": False, "message": f"SMTP 오류: {e}"})
    except OSError as e:
        return jsonify({"success": False,
                        "message": f"네트워크 오류 — 인터넷 연결을 확인하세요: {e}"})
    except Exception as e:
        return jsonify({"success": False, "message": f"오류: {e}"})


# ─────────────────────────────────────────────
# API: Windows 작업 스케줄러 등록
# ─────────────────────────────────────────────
@app.route("/api/register_scheduler", methods=["POST"])
def api_register_scheduler():
    config = load_config()
    hour = config.get("schedule_hour", 9)
    minute = config.get("schedule_minute", 0)
    
    script_dir = Path(__file__).parent.resolve()
    python_exe = sys.executable
    scheduler_script = script_dir / "scheduler.py"
    
    bat_content = f"""@echo off
chcp 65001 > nul
schtasks /delete /tn "StockResearchAgent" /f >nul 2>&1
schtasks /create ^
  /tn "StockResearchAgent" ^
  /tr "\"{python_exe}\" \"{scheduler_script}\"" ^
  /sc DAILY ^
  /st {hour:02d}:{minute:02d} ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f
if %errorlevel% == 0 (
    echo SUCCESS
) else (
    echo FAIL
)
"""
    
    bat_path = script_dir / "setup_scheduler.bat"
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    
    # 자동 실행 (관리자 권한 필요)
    import subprocess
    try:
        result = subprocess.run(
            ["powershell", "-Command", f"Start-Process '{bat_path}' -Verb RunAs -Wait"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return jsonify({"success": True, "message": f"매일 {hour:02d}:{minute:02d} 자동 실행 등록 완료!"})
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"setup_scheduler.bat 파일을 우클릭 → 관리자 권한으로 실행하세요.\n오류: {str(e)}"
        })


# ─────────────────────────────────────────────
# 라우트: 유저 구독 신청 페이지
# ─────────────────────────────────────────────
@app.route("/user")
def user_page():
    return render_template("user.html")


# ─────────────────────────────────────────────
# API: 유저 등록 / 설정 업데이트
# ─────────────────────────────────────────────
@app.route("/api/register_user", methods=["POST"])
def api_register_user():
    data  = request.json
    name  = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    if not name or not email:
        return jsonify({"success": False, "message": "이름과 이메일은 필수입니다."})

    users = load_users()
    # 이름 기준 중복 확인
    existing = next((u for u in users if u["name"] == name), None)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if existing:
        existing["email"]          = email
        existing["stocks"]         = data.get("stocks", [])
        existing["industries"]     = data.get("industries", [])
        existing["schedule_hour"]  = int(data.get("schedule_hour", 9))
        existing["schedule_minute"]= int(data.get("schedule_minute", 0))
        existing["updated_at"]     = now
        msg = f"{name}님, 설정이 업데이트되었습니다!"
    else:
        users.append({
            "id":              str(uuid.uuid4()),
            "name":            name,
            "email":           email,
            "stocks":          data.get("stocks", []),
            "industries":      data.get("industries", []),
            "schedule_hour":   int(data.get("schedule_hour", 9)),
            "schedule_minute": int(data.get("schedule_minute", 0)),
            "active":          True,
            "created_at":      now,
            "updated_at":      now,
        })
        msg = f"{name}님, 구독 신청 완료! 내일부터 리포트가 발송됩니다 📈"

    save_users(users)
    return jsonify({"success": True, "message": msg})


# ─────────────────────────────────────────────
# API: 이름으로 유저 조회 (user.html 자동완성)
# ─────────────────────────────────────────────
@app.route("/api/user_by_name/<name>")
def api_user_by_name(name):
    users = load_users()
    user = next((u for u in users if u["name"] == name.strip()), None)
    if user:
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False})


# ─────────────────────────────────────────────
# API: 즉시 리포트 전송 (특정 유저)
# ─────────────────────────────────────────────
def _run_scheduler(args: list):
    script = Path(__file__).parent / "scheduler.py"
    subprocess.Popen([sys.executable, str(script)] + args)

@app.route("/api/send_now", methods=["POST"])
def api_send_now():
    """user.html에서 이름 기준으로 즉시 전송"""
    data = request.json
    name = data.get("name", "").strip()
    users = load_users()
    user = next((u for u in users if u["name"] == name), None)
    if not user:
        return jsonify({"success": False, "message": "먼저 구독 신청을 완료해주세요."})
    threading.Thread(target=_run_scheduler, args=(["--user-id", user["id"]],), daemon=True).start()
    return jsonify({"success": True, "message": "리포트 생성 중입니다. 약 2~3분 후 이메일을 확인하세요 📬"})

@app.route("/api/send_now/<uid>", methods=["POST"])
def api_send_now_uid(uid):
    """관리자 대시보드에서 특정 유저에게 즉시 전송"""
    users = load_users()
    user = next((u for u in users if u["id"] == uid), None)
    if not user:
        return jsonify({"success": False, "message": "유저를 찾을 수 없습니다."})
    threading.Thread(target=_run_scheduler, args=(["--user-id", uid],), daemon=True).start()
    return jsonify({"success": True, "message": f"{user['name']}님께 전송 시작! 약 2~3분 후 확인하세요 📬"})


# ─────────────────────────────────────────────
# API: 유저 목록 조회 (관리자용)
# ─────────────────────────────────────────────
@app.route("/api/users")
def api_get_users():
    return jsonify(load_users())


# ─────────────────────────────────────────────
# API: 유저 활성/비활성 토글
# ─────────────────────────────────────────────
@app.route("/api/users/<uid>/toggle", methods=["POST"])
def api_toggle_user(uid):
    users = load_users()
    user = next((u for u in users if u["id"] == uid), None)
    if not user:
        return jsonify({"success": False, "message": "유저를 찾을 수 없습니다."})
    user["active"] = not user["active"]
    save_users(users)
    status = "활성화" if user["active"] else "비활성화"
    return jsonify({"success": True, "message": f"{user['name']}님 {status}", "active": user["active"]})


# ─────────────────────────────────────────────
# API: 유저 삭제
# ─────────────────────────────────────────────
@app.route("/api/users/<uid>", methods=["DELETE"])
def api_delete_user(uid):
    users = load_users()
    new_users = [u for u in users if u["id"] != uid]
    if len(new_users) == len(users):
        return jsonify({"success": False, "message": "유저를 찾을 수 없습니다."})
    save_users(new_users)
    return jsonify({"success": True, "message": "삭제되었습니다."})


# ─────────────────────────────────────────────
# API: 리포트 파일 읽기
# ─────────────────────────────────────────────
@app.route("/api/report/<filename>")
def api_get_report(filename):
    filepath = REPORTS_DIR / filename
    if filepath.exists():
        content = filepath.read_text(encoding="utf-8")
        return jsonify({"success": True, "content": content})
    return jsonify({"success": False, "message": "파일을 찾을 수 없습니다."})


if __name__ == "__main__":
    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║  📈 주식 리서치 에이전트 웹 대시보드     ║")
    print("  ╚══════════════════════════════════════════╝")
    print()
    print("  🌐 브라우저에서 접속하세요:")
    print("     http://localhost:5000")
    print()
    print("  종료하려면 Ctrl+C 누르세요.")
    print()
    
    app.run(host="0.0.0.0", port=5000, debug=True)
