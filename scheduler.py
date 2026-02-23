#!/usr/bin/env python3
"""
scheduler.py — 자동 실행 전용 (Gemini)
config.json에서 API 키와 설정을 읽어옵니다
"""

import os
import sys
import json
import re

import datetime
import smtplib
import argparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google import genai
from google.genai import types

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "stock_agent_data"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"
REPORTS_DIR = DATA_DIR / "reports"
CONFIG_FILE = DATA_DIR / "config.json"
USERS_FILE = DATA_DIR / "users.json"
LOG_FILE = DATA_DIR / "scheduler.log"

DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

MODEL = "gemini-2.5-flash"


def log(msg: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_watchlist() -> dict:
    if WATCHLIST_FILE.exists():
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"stocks": [], "industries": []}


def load_users() -> list:
    if USERS_FILE.exists():
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def call_gemini(client, prompt: str) -> str:
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
        )
    )
    return response.text


# ── 공통 섹션 ──────────────────────────────────────────────────────────────

def get_portfolio_overview(client, stocks: list, industries: list) -> str:
    """📌 오늘의 포트폴리오 요약 — 자산별 1줄"""
    today = datetime.date.today().strftime("%Y년 %m월 %d일")
    all_targets = list(stocks) + list(industries)
    targets_str = ", ".join(all_targets) or "없음"
    count = len(all_targets)
    prompt = (
        f"오늘은 {today}입니다. Google 검색으로 최신 시장 정보를 확인하여 "
        f"아래 {count}개 종목/산업 각각에 대해 정확히 {count}줄을 작성하세요.\n"
        f"종목/산업 목록: {targets_str}\n\n"
        f"형식 (1개 종목/산업당 1줄):\n"
        f"- 자산명 → 핵심 해석 / 액션: (관망·매수·비중조절·리스크관리 중 1개)\n\n"
        f"규칙:\n"
        f"- 자산명 뒤 내용은 10단어 이내\n"
        f"- 안내 문구·서론 없이 bullet(- )만 바로 출력\n"
        f"- 마크다운(#, ** 등) 금지\n\n"
        f"예시:\n"
        f"- 한화에어로스페이스 → 목표주가 상향, 모멘텀 유효 / 액션: 눌림목 관찰\n"
        f"- 전력 → 데이터센터 수요 증가 / 액션: 분할매수"
    )
    return call_gemini(client, prompt)


def get_portfolio_risk(client, stocks: list, industries: list) -> str:
    """⚠️ 오늘의 포트폴리오 리스크 — 전체 포트 기준 1~2줄"""
    today = datetime.date.today().strftime("%Y년 %m월 %d일")
    all_targets = list(stocks) + list(industries)
    targets_str = ", ".join(all_targets) or "없음"
    prompt = (
        f"오늘은 {today}입니다. Google 검색으로 최신 정보를 확인하여 "
        f"아래 포트폴리오 전체에 영향을 미치는 공통 리스크를 작성하세요.\n"
        f"포트폴리오: {targets_str}\n\n"
        f"규칙:\n"
        f"- 개별 종목 리스크가 아닌 포트폴리오 전체 공통 리스크만\n"
        f"- bullet(- ) 1~2개, 각 12단어 이내\n"
        f"- 안내 문구·서론 없이 bullet만 바로 출력\n"
        f"- 마크다운 금지\n\n"
        f"예시:\n"
        f"- 미 연준 긴축 장기화 → 성장주 전반 밸류에이션 압박\n"
        f"- 원/달러 환율 급등 → 수입 비용 증가, 내수주 부담"
    )
    return call_gemini(client, prompt)


def get_news_summary(client) -> str:
    """📰 시장 방향 & 심리 — bullet 최대 3개"""
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y년 %m월 %d일")
    today = datetime.date.today().strftime("%Y년 %m월 %d일")
    prompt = (
        f"어제({yesterday})~오늘({today}) 글로벌·한국 주식시장을 Google 검색으로 확인하여 "
        f"핵심 요인 정확히 3개를 작성하세요.\n\n"
        f"규칙:\n"
        f"- 안내 문구·서론 없이 bullet(- )만 바로 출력\n"
        f"- 형태: '- 요인 → 시장 영향' (1줄, 12단어 이내)\n"
        f"- 중복 없이 서로 다른 요인만\n"
        f"- 마크다운 금지\n\n"
        f"예시:\n"
        f"- 트럼프 관세 불확실성 → 수출주 변동성 확대\n"
        f"- AI 반도체 업황 개선 → 기술주 강세"
    )
    return call_gemini(client, prompt)


def get_report_footer(client, stocks: list, industries: list) -> str:
    """⏱ 타임프레임 관점 — 자산별 단기/중기/장기 1줄씩"""
    today = datetime.date.today().strftime("%Y년 %m월 %d일")
    all_targets = list(stocks) + list(industries)
    targets_str = ", ".join(all_targets) or "없음"
    prompt = (
        f"오늘은 {today}입니다. Google 검색으로 최신 정보를 확인하여 "
        f"아래 종목/산업 각각의 타임프레임 관점을 한국어로 작성하세요.\n"
        f"종목/산업: {targets_str}\n\n"
        f"각 자산마다 아래 형식으로 작성하세요. 안내 문구·반복 문구 금지.\n"
        f"### 자산명\n"
        f"- 단기(7일): 이벤트·수급 중심 1줄 (10단어 이내)\n"
        f"- 중기(1~3개월): 모멘텀·실적 사이클 1줄 (10단어 이내)\n"
        f"- 장기(1년): 구조적 성장 스토리 1줄 (10단어 이내)"
    )
    return call_gemini(client, prompt)


# ── 개별 리서치 ────────────────────────────────────────────────────────────

def run_research(client, target: str, research_type: str) -> str:
    today = datetime.date.today().strftime("%Y년 %m월 %d일")

    if research_type == "stock":
        # 종목 템플릿 — 포지션 판단용 (5개 항목)
        prompt = (
            f"오늘은 {today}입니다. Google 검색으로 '{target}' 종목의 최신 정보를 조사하여 "
            f"아래 5개 항목만 한국어로 작성하세요.\n"
            f"금지: 뉴스 나열 / 숫자·가격·목표가·거래량 직접 기재 / 중복 문장\n\n"
            f"## 📌 한줄 요약\n"
            f"(오늘 핵심 이슈 + 주가 의미, 1줄, 15단어 이내)\n\n"
            f"## 🧠 오늘의 해석\n"
            f"(사건 → 실적 영향 → 주가 해석 흐름, 최대 2줄, 각 15단어 이내)\n\n"
            f"## 📍 가격 위치\n"
            f"(신고가 근접 / 급등 후 조정 / 박스권 / 저점 반등 등 위치 서술, 숫자 금지, 1줄)\n\n"
            f"## 📊 투자 매력도: n/10\n"
            f"근거:\n"
            f"(점수 이유 중심, 최대 2줄, 각 15단어 이내)\n\n"
            f"## ⚠️ 리스크\n"
            f"(핵심 리스크 1줄, 12단어 이내)"
        )
    else:
        # 산업 템플릿 — 자금 흐름 판단용 (6개 항목)
        prompt = (
            f"오늘은 {today}입니다. Google 검색으로 '{target}' 산업의 최신 정보를 조사하여 "
            f"아래 6개 항목만 한국어로 작성하세요.\n"
            f"금지: 개별 기업 실적·가격·세부 통계 나열 / 중복 문장\n\n"
            f"## 📌 한줄 요약\n"
            f"(산업 상승/둔화 사이클 판단, 1줄, 15단어 이내)\n\n"
            f"## 💰 자금 흐름\n"
            f"(시장에서 수급 유입 여부 또는 투자자 관심도, 1줄)\n\n"
            f"## 🧭 산업 사이클 위치\n"
            f"(초기 / 중기 / 피크 / 하락 중 하나 선택 + 1줄 근거)\n\n"
            f"## ⭐ 핵심 수혜 포인트\n"
            f"(구조적 성장 요인 또는 투자 테마, 1줄)\n\n"
            f"## 📊 투자 매력도: n/10\n"
            f"근거:\n"
            f"(점수 이유 중심, 최대 2줄, 각 15단어 이내)\n\n"
            f"## ⚠️ 리스크\n"
            f"(핵심 리스크 1줄, 12단어 이내)"
        )
    return call_gemini(client, prompt)


def save_report(target: str, research_type: str, content: str) -> Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    type_label = "종목" if research_type == "stock" else "산업"
    filename = REPORTS_DIR / f"{timestamp}_{type_label}_{target}.md"
    header = (
        f"# 📈 {type_label} 리서치: {target}\n"
        f"> {datetime.datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}\n\n---\n\n"
    )
    with open(filename, "w", encoding="utf-8") as f:
        f.write(header + content)
    return filename


def md_to_html(text: str) -> str:
    """마크다운을 이메일용 HTML로 변환"""
    def inline(s: str) -> str:
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
        s = re.sub(r"`(.+?)`", r"<code style='background:#f4f4f4;padding:1px 4px;border-radius:3px'>\1</code>", s)
        return s

    lines = text.split("\n")
    out = []
    in_ul = False
    in_ol = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    for line in lines:
        if line.startswith("### "):
            close_lists()
            out.append(f'<h4 style="color:#555;font-size:13px;font-weight:700;margin:12px 0 3px">{inline(line[4:])}</h4>')
        elif line.startswith("## "):
            close_lists()
            out.append(
                f'<h3 style="color:#1a73e8;font-size:14px;font-weight:700;'
                f'margin:14px 0 5px;padding-left:8px;'
                f'border-left:3px solid #1a73e8">{inline(line[3:])}</h3>'
            )
        elif line.startswith("# "):
            close_lists()
            out.append(f'<h2 style="color:#0b3d91;font-size:16px;margin:16px 0 8px">{inline(line[2:])}</h2>')
        elif line.strip() in ("---", "***", "___"):
            close_lists()
            out.append('<hr style="border:none;border-top:1px solid #eee;margin:10px 0">')
        elif re.match(r"^[-*] ", line):
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append('<ul style="margin:4px 0;padding-left:18px;line-height:1.7">')
                in_ul = True
            out.append(f'<li>{inline(line[2:])}</li>')
        elif re.match(r"^\d+\. ", line):
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append('<ol style="margin:4px 0;padding-left:18px;line-height:1.7">')
                in_ol = True
            content = re.sub(r"^\d+\. ", "", line)
            out.append(f'<li>{inline(content)}</li>')
        elif line.strip() == "":
            close_lists()
            out.append("")
        else:
            close_lists()
            out.append(f'<p style="margin:4px 0;line-height:1.7">{inline(line)}</p>')

    close_lists()
    return "\n".join(out)


def build_html_email(reports: list, news_summary: str, portfolio_overview: str,
                     portfolio_risk: str, report_footer: str) -> str:
    today_str = datetime.datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    yesterday_str = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%m/%d")
    today_short = datetime.date.today().strftime("%m/%d")

    # ── 1. 포트폴리오 요약 ───────────────────────────────
    portfolio_section = f"""
<div style="background:#fff;border-radius:10px;margin:16px 0;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.1);border-left:4px solid #1a73e8">
  <div style="font-weight:700;font-size:15px;color:#1a73e8;margin-bottom:12px">📌 오늘의 포트폴리오 요약</div>
  {md_to_html(portfolio_overview.strip())}
</div>"""

    # ── 2. 포트폴리오 리스크 ─────────────────────────────
    risk_section = f"""
<div style="background:#fff8e1;border-radius:10px;margin:16px 0;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.1);border-left:4px solid #f4b400">
  <div style="font-weight:700;font-size:15px;color:#b06000;margin-bottom:12px">⚠️ 오늘의 포트폴리오 리스크</div>
  {md_to_html(portfolio_risk.strip())}
</div>"""

    # ── 3. 시장 방향 & 심리 ──────────────────────────────
    news_lines = "".join(
        f'<p style="margin:0 0 10px;line-height:1.7;color:#333;font-size:13px">{line.strip()}</p>'
        for line in news_summary.strip().split("\n") if line.strip()
    )
    news_section = f"""
<div style="background:#fff;border-radius:10px;margin:16px 0;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.1)">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
    <span style="font-weight:700;font-size:15px;color:#0b3d91">📰 시장 방향 & 심리</span>
    <span style="font-size:12px;color:#fff;background:#0b3d91;padding:2px 8px;border-radius:10px">{yesterday_str} ~ {today_short}</span>
  </div>
  {news_lines}
</div>"""

    # ── 4. 종목/산업 카드 ────────────────────────────────
    cards = ""
    for r in reports:
        icon = "📌" if r["type"] == "stock" else "🏭"
        label = "종목" if r["type"] == "stock" else "산업"
        label_color = "#1a73e8" if r["type"] == "stock" else "#34a853"
        label_bg = "#e8f0fe" if r["type"] == "stock" else "#e6f4ea"
        body_html = md_to_html(r["content"])
        cards += f"""
<div style="background:#fff;border-radius:10px;margin:12px 0;box-shadow:0 2px 8px rgba(0,0,0,.1);overflow:hidden">
  <div style="padding:14px 20px;border-bottom:1px solid #f0f0f0;display:flex;align-items:center;gap:8px">
    <span style="background:{label_bg};color:{label_color};font-size:11px;padding:2px 8px;border-radius:10px;font-weight:700">{label}</span>
    <span style="font-weight:700;font-size:16px;color:#222">{icon} {r["target"]}</span>
  </div>
  <div style="padding:14px 20px 18px">{body_html}</div>
</div>"""

    # ── 5. 타임프레임 관점 ───────────────────────────────
    footer_section = f"""
<div style="background:#fff;border-radius:10px;margin:16px 0;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.1);border-left:4px solid #34a853">
  <div style="font-weight:700;font-size:15px;color:#2d8e47;margin-bottom:12px">⏱ 타임프레임 관점</div>
  {md_to_html(report_footer.strip())}
</div>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="font-family:'Malgun Gothic',Apple SD Gothic Neo,sans-serif;background:#f0f4f8;margin:0;padding:20px;color:#222">
<div style="max-width:680px;margin:0 auto">
  <div style="background:linear-gradient(135deg,#1a73e8,#0b3d91);color:#fff;padding:24px 28px;border-radius:12px;margin-bottom:4px">
    <h1 style="margin:0;font-size:22px">📈 주식 리서치 에이전트</h1>
    <p style="margin:6px 0 0;opacity:.85;font-size:14px">{today_str} &nbsp;•&nbsp; {len(reports)}개 종목/산업</p>
  </div>

  {portfolio_section}

  {risk_section}

  {news_section}

  {cards}

  {footer_section}

  <div style="background:#fff8e1;padding:14px 20px;border-radius:10px;font-size:12px;color:#888;margin-top:8px;line-height:1.7">
    ⚠️ 본 리포트는 AI가 생성한 정보 제공용 자료이며 투자 권유가 아닙니다.
  </div>
</div>
</body>
</html>"""


def send_email_to(config: dict, recipient: str, subject: str, html_body: str) -> bool:
    gmail_user   = config.get("gmail_user", "").strip()
    app_password = config.get("gmail_app_password", "").replace(" ", "").strip()
    if not gmail_user or not app_password or not recipient:
        log("❌ Gmail 미설정 또는 수신자 없음")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"주식 리서치 <{gmail_user}>"
        msg["To"] = recipient
        msg.attach(MIMEText(re.sub(r"<[^>]+>", "", html_body), "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(gmail_user, app_password)
            server.sendmail(gmail_user, recipient, msg.as_string())
        log(f"✅ 이메일 전송 → {recipient}")
        return True
    except Exception as e:
        log(f"❌ 이메일 오류 ({recipient}): {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default=None, help="단일 유저 ID (지정 시 해당 유저에게만 발송)")
    args = parser.parse_args()

    log("=" * 50)
    log("📈 자동 실행 시작" + (f" (유저: {args.user_id})" if args.user_id else ""))
    config = load_config()
    api_key = os.environ.get("GEMINI_API_KEY") or config.get("gemini_api_key", "")
    if not api_key:
        log("❌ GEMINI_API_KEY 없음")
        sys.exit(1)

    client    = genai.Client(api_key=api_key)
    users     = load_users()
    today_str = datetime.date.today().strftime("%Y년 %m월 %d일")

    # ── 단일 유저 모드 ─────────────────────────────────────
    if args.user_id:
        target_user = next((u for u in users if u.get("id") == args.user_id), None)
        if not target_user:
            log(f"❌ 유저를 찾을 수 없음: {args.user_id}")
            sys.exit(1)

        u_stocks     = target_user.get("stocks", [])
        u_industries = target_user.get("industries", [])

        if not u_stocks and not u_industries:
            log(f"⚠️ {target_user['name']} — 관심 목록 없음, 종료")
            sys.exit(0)

        # 뉴스
        log("뉴스 요약 수집 중...")
        try:
            news_summary = get_news_summary(client)
            log("✅ 뉴스 요약 완료")
        except Exception as e:
            log(f"⚠️ 뉴스 요약 실패: {e}")
            news_summary = "- 뉴스 요약을 불러오지 못했습니다."

        # 개별 종목/산업 리서치
        items = [("stock", s) for s in u_stocks] + [("industry", i) for i in u_industries]
        report_map = {}
        for rtype, target in items:
            log(f"리서치: {target}")
            try:
                content = run_research(client, target, rtype)
                if content:
                    save_report(target, rtype, content)
                    report_map[(rtype, target)] = content
                    log(f"✅ {target}")
            except Exception as e:
                log(f"❌ {target}: {e}")

        if not report_map:
            log("리서치 결과 없음 — 종료")
            sys.exit(0)

        # 포트폴리오 요약
        log("포트폴리오 요약 수집 중...")
        try:
            portfolio_overview = get_portfolio_overview(client, u_stocks, u_industries)
            log("✅ 포트폴리오 요약 완료")
        except Exception as e:
            log(f"⚠️ 포트폴리오 요약 실패: {e}")
            portfolio_overview = "- 포트폴리오 요약을 불러오지 못했습니다."

        # 포트폴리오 리스크
        log("포트폴리오 리스크 수집 중...")
        try:
            portfolio_risk = get_portfolio_risk(client, u_stocks, u_industries)
            log("✅ 포트폴리오 리스크 완료")
        except Exception as e:
            log(f"⚠️ 포트폴리오 리스크 실패: {e}")
            portfolio_risk = "- 리스크 정보를 불러오지 못했습니다."

        # 타임프레임
        log("타임프레임 분석 수집 중...")
        try:
            report_footer = get_report_footer(client, u_stocks, u_industries)
            log("✅ 타임프레임 분석 완료")
        except Exception as e:
            log(f"⚠️ 타임프레임 분석 실패: {e}")
            report_footer = "- 분석을 불러오지 못했습니다."

        user_reports = []
        for s in u_stocks:
            if ("stock", s) in report_map:
                user_reports.append({"target": s, "type": "stock", "content": report_map[("stock", s)]})
        for i in u_industries:
            if ("industry", i) in report_map:
                user_reports.append({"target": i, "type": "industry", "content": report_map[("industry", i)]})

        if user_reports:
            subject = f"📈 {target_user['name']}님의 [{today_str}] 리서치 ({len(user_reports)}건)"
            send_email_to(config, target_user["email"], subject,
                          build_html_email(user_reports, news_summary, portfolio_overview,
                                           portfolio_risk, report_footer))
        else:
            log(f"⚠️ {target_user['name']} — 해당 종목 결과 없음")

        log("📈 완료")
        log("=" * 50)
        return

    # ── 전체 발송 모드 ─────────────────────────────────────
    active_users = [u for u in users if u.get("active", True)]

    # 1. 활성 구독자의 고유 종목/산업 수집
    all_stocks     = set()
    all_industries = set()
    for u in active_users:
        all_stocks.update(u.get("stocks", []))
        all_industries.update(u.get("industries", []))

    if not all_stocks and not all_industries:
        log("⚠️  관심 목록 없음 — 종료")
        sys.exit(0)

    # 2. 뉴스 요약 (공통 1회)
    log("뉴스 요약 수집 중...")
    try:
        news_summary = get_news_summary(client)
        log("✅ 뉴스 요약 완료")
    except Exception as e:
        log(f"⚠️ 뉴스 요약 실패: {e}")
        news_summary = "- 뉴스 요약을 불러오지 못했습니다."

    # 3. 고유 종목/산업 1회씩 리서치
    items = [("stock", s) for s in all_stocks] + [("industry", i) for i in all_industries]
    report_map = {}
    for rtype, target in items:
        log(f"리서치: {target}")
        try:
            content = run_research(client, target, rtype)
            if content:
                save_report(target, rtype, content)
                report_map[(rtype, target)] = content
                log(f"✅ {target}")
        except Exception as e:
            log(f"❌ {target}: {e}")

    if not report_map:
        log("리서치 결과 없음 — 종료")
        sys.exit(0)

    # 4. 구독자별 맞춤 이메일 발송
    for u in active_users:
        u_stocks     = u.get("stocks", [])
        u_industries = u.get("industries", [])

        user_reports = []
        for s in u_stocks:
            if ("stock", s) in report_map:
                user_reports.append({"target": s, "type": "stock", "content": report_map[("stock", s)]})
        for i in u_industries:
            if ("industry", i) in report_map:
                user_reports.append({"target": i, "type": "industry", "content": report_map[("industry", i)]})
        if not user_reports:
            log(f"⚠️ {u['name']} — 해당 종목 결과 없음, 건너뜀")
            continue

        log(f"{u['name']} 포트폴리오 요약 수집 중...")
        try:
            portfolio_overview = get_portfolio_overview(client, u_stocks, u_industries)
        except Exception as e:
            log(f"⚠️ 포트폴리오 요약 실패: {e}")
            portfolio_overview = "- 포트폴리오 요약을 불러오지 못했습니다."

        log(f"{u['name']} 포트폴리오 리스크 수집 중...")
        try:
            portfolio_risk = get_portfolio_risk(client, u_stocks, u_industries)
        except Exception as e:
            log(f"⚠️ 포트폴리오 리스크 실패: {e}")
            portfolio_risk = "- 리스크 정보를 불러오지 못했습니다."

        log(f"{u['name']} 타임프레임 분석 수집 중...")
        try:
            report_footer = get_report_footer(client, u_stocks, u_industries)
        except Exception as e:
            log(f"⚠️ 타임프레임 분석 실패: {e}")
            report_footer = "- 분석을 불러오지 못했습니다."

        subject = f"📈 {u['name']}님의 [{today_str}] 리서치 ({len(user_reports)}건)"
        send_email_to(config, u["email"], subject,
                      build_html_email(user_reports, news_summary, portfolio_overview,
                                       portfolio_risk, report_footer))

    log("📈 완료")
    log("=" * 50)


if __name__ == "__main__":
    main()
