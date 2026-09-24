"""
오늘의 국내 증시 카드 자동 생성 + X 업로드
 - 데이터: pykrx (한국거래소)
 - 이미지: Pillow (1080x1350)
 - 게시: X API v2 (OAuth 1.0a, 미디어 업로드 → 포스트 생성)

실행:  python daily_market_card.py            # 수집 → 이미지 → 업로드
       python daily_market_card.py --dry-run  # 업로드 없이 이미지만 생성
       python daily_market_card.py --mock     # KRX 접속 없이 샘플 데이터로 레이아웃 확인
"""
import argparse
import datetime as dt
import os
import sys

from PIL import Image, ImageDraw, ImageFont

# ───────────────────────── 설정 ─────────────────────────
CFG = {
    "TOP_N": 5,                     # 순위 표시 개수
    "MARKET": "ALL",                # 순위 집계 시장: "KOSPI" | "KOSDAQ" | "ALL"
    "OUT_DIR": "output",
    # 한글 폰트: Windows는 맑은 고딕, 리눅스/맥은 Noto Sans CJK 등으로 교체
    "FONT_REG": os.getenv("FONT_REG", "C:/Windows/Fonts/malgun.ttf"),
    "FONT_BOLD": os.getenv("FONT_BOLD", "C:/Windows/Fonts/malgunbd.ttf"),
    "W": 1080, "H": 1350,
}
MKT_LABEL = {"ALL": "코스피+코스닥", "KOSPI": "코스피", "KOSDAQ": "코스닥"}
UP, DOWN = (235, 72, 72), (66, 133, 244)          # 상승·순매수 빨강 / 하락·순매도 파랑
BG, PANEL, TXT, SUB = (16, 18, 24), (28, 31, 40), (240, 240, 240), (150, 155, 165)


# ───────────────────────── 1. 데이터 수집 ─────────────────────────
def is_trading_day(date_str: str) -> bool:
    from pykrx import stock
    return stock.get_nearest_business_day_in_a_week(date_str) == date_str


def index_summary(date_str: str, code: str) -> dict:
    """지수 종가·등락 (code: 1001=KOSPI, 2001=KOSDAQ)"""
    from pykrx import stock
    start = (dt.datetime.strptime(date_str, "%Y%m%d") - dt.timedelta(days=14)).strftime("%Y%m%d")
    df = stock.get_index_ohlcv(start, date_str, code)
    close, prev = float(df["종가"].iloc[-1]), float(df["종가"].iloc[-2])
    return {"close": close, "chg": close - prev, "pct": (close / prev - 1) * 100,
            "value": float(df["거래대금"].iloc[-1]) / 1e8}            # 억 원


def investor_totals(date_str: str) -> dict:
    """투자자별 순매수 합계 (억 원)"""
    from pykrx import stock
    df = stock.get_market_trading_value_by_investor(date_str, date_str, CFG["MARKET"])
    keys = ["개인", "외국인", "기관합계", "연기금"]
    return {k: float(df.loc[k, "순매수"]) / 1e8 for k in keys if k in df.index}


def ranking(date_str: str, investor: str) -> tuple[list, list]:
    """투자자별 순매수/순매도 상위 N (종목명, 억 원)"""
    from pykrx import stock
    df = stock.get_market_net_purchases_of_equities(date_str, date_str, CFG["MARKET"], investor)
    df = df.sort_values("순매수거래대금", ascending=False)
    to_list = lambda d: [(r["종목명"], float(r["순매수거래대금"]) / 1e8) for _, r in d.iterrows()]
    n = CFG["TOP_N"]
    return to_list(df.head(n)), to_list(df.tail(n).iloc[::-1])


def collect(date_str: str) -> dict:
    pb, ps = ranking(date_str, "연기금")
    fb, fs = ranking(date_str, "외국인")
    return {"date": date_str,
            "kospi": index_summary(date_str, "1001"),
            "kosdaq": index_summary(date_str, "2001"),
            "investor": investor_totals(date_str),
            "pension_buy": pb, "pension_sell": ps,
            "foreign_buy": fb, "foreign_sell": fs}


def mock_data(date_str: str) -> dict:
    return {"date": date_str,
            "kospi": {"close": 3412.55, "chg": 18.21, "pct": 0.54, "value": 128450},
            "kosdaq": {"close": 871.30, "chg": -4.12, "pct": -0.47, "value": 84210},
            "investor": {"개인": -3120, "외국인": 2210, "기관합계": 905, "연기금": 1480},
            "pension_buy": [("삼성전자", 1296), ("SK하이닉스", 1102), ("SK스퀘어", 309), ("대덕전자", 170), ("삼성전기", 155)],
            "pension_sell": [("삼성전자우", -504), ("NAVER", -385), ("현대차", -155), ("두산에너빌리티", -136), ("HD현대중공업", -131)],
            "foreign_buy": [("SK하이닉스", 2140), ("삼성전자", 1580), ("한화에어로스페이스", 420), ("LG에너지솔루션", 310), ("셀트리온", 198)],
            "foreign_sell": [("현대차", -610), ("기아", -402), ("KB금융", -233), ("POSCO홀딩스", -190), ("카카오", -144)]}


# ───────────────────────── 2. 카드 렌더링 ─────────────────────────
def render(d: dict, path: str) -> str:
    W, H = CFG["W"], CFG["H"]
    img = Image.new("RGB", (W, H), BG)
    g = ImageDraw.Draw(img)
    F = lambda s, b=False: ImageFont.truetype(CFG["FONT_BOLD"] if b else CFG["FONT_REG"], s)
    color = lambda v: UP if v > 0 else DOWN if v < 0 else TXT
    sign = lambda v: f"+{v:,.0f}" if v > 0 else f"{v:,.0f}"

    date = dt.datetime.strptime(d["date"], "%Y%m%d")
    wd = "월화수목금토일"[date.weekday()]
    g.text((60, 55), "오늘의 국내 증시", font=F(56, True), fill=TXT)
    g.text((60, 128), f"{date:%Y.%m.%d} ({wd}) 장 마감", font=F(30), fill=SUB)

    # ── 지수 패널
    for i, (name, key) in enumerate([("KOSPI", "kospi"), ("KOSDAQ", "kosdaq")]):
        x0, y0 = 60 + i * 490, 195
        g.rounded_rectangle((x0, y0, x0 + 470, y0 + 190), 18, fill=PANEL)
        s = d[key]
        g.text((x0 + 28, y0 + 22), name, font=F(30, True), fill=SUB)
        g.text((x0 + 28, y0 + 62), f"{s['close']:,.2f}", font=F(56, True), fill=TXT)
        arrow = "▲" if s["chg"] > 0 else "▼" if s["chg"] < 0 else "-"
        g.text((x0 + 28, y0 + 132), f"{arrow} {abs(s['chg']):,.2f}  ({s['pct']:+.2f}%)",
               font=F(30, True), fill=color(s["chg"]))

    # ── 투자자별 순매수
    y0 = 410
    g.rounded_rectangle((60, y0, W - 60, y0 + 130), 18, fill=PANEL)
    g.text((88, y0 + 16), "투자자별 순매수 (억 원)", font=F(26, True), fill=SUB)
    items = list(d["investor"].items())
    cw = (W - 120) / max(len(items), 1)
    for i, (k, v) in enumerate(items):
        cx = 60 + cw * i + cw / 2
        g.text((cx, y0 + 68), k.replace("합계", ""), font=F(24), fill=SUB, anchor="mm")
        g.text((cx, y0 + 103), sign(v), font=F(32, True), fill=color(v), anchor="mm")

    # ── 순위 표 4개 (2x2)
    def table(x0, y0, title, rows, col):
        g.rounded_rectangle((x0, y0, x0 + 470, y0 + 330), 18, fill=PANEL)
        g.text((x0 + 26, y0 + 20), title, font=F(28, True), fill=col)
        for j, (nm, v) in enumerate(rows):
            yy = y0 + 78 + j * 48
            g.text((x0 + 26, yy), f"{j + 1}", font=F(26, True), fill=SUB)
            g.text((x0 + 62, yy), nm[:9], font=F(27), fill=TXT)
            g.text((x0 + 444, yy), sign(v), font=F(27, True), fill=col, anchor="ra")

    table(60, 565, "연기금 순매수 TOP 5", d["pension_buy"], UP)
    table(550, 565, "연기금 순매도 TOP 5", d["pension_sell"], DOWN)
    table(60, 915, "외국인 순매수 TOP 5", d["foreign_buy"], UP)
    table(550, 915, "외국인 순매도 TOP 5", d["foreign_sell"], DOWN)

    g.text((60, H - 70), f"단위: 억 원 · 집계: {MKT_LABEL[CFG['MARKET']]} · 자료: 한국거래소 · 정보 제공 목적",
           font=F(22), fill=SUB)

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    img.save(path)
    return path


# ───────────────────────── 3. X 업로드 ─────────────────────────
def post_to_x(image_path: str, text: str) -> str:
    """X API v2: 미디어 업로드 → 포스트 생성 (OAuth 1.0a 사용자 컨텍스트)"""
    from requests_oauthlib import OAuth1Session
    s = OAuth1Session(os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                      os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])
    with open(image_path, "rb") as f:
        r = s.post("https://api.x.com/2/media/upload",
                   files={"media": f}, data={"media_category": "tweet_image"})
    if not r.ok:
        raise RuntimeError(f"미디어 업로드 실패 {r.status_code}: {r.text}")
    media_id = r.json()["data"]["id"]

    r = s.post("https://api.x.com/2/tweets",
               json={"text": text, "media": {"media_ids": [media_id]}})
    if not r.ok:
        raise RuntimeError(f"포스트 생성 실패 {r.status_code}: {r.text}")
    return r.json()["data"]["id"]


def build_text(d: dict) -> str:
    """본문: 링크 금지(링크 포함 시 과금 급증), 해석·추천 문구 없음"""
    date = dt.datetime.strptime(d["date"], "%Y%m%d")
    k, q = d["kospi"], d["kosdaq"]
    return (f"{date:%Y.%m.%d} 국내 증시 마감\n"
            f"KOSPI {k['close']:,.2f} ({k['pct']:+.2f}%)\n"
            f"KOSDAQ {q['close']:,.2f} ({q['pct']:+.2f}%)\n"
            f"#코스피 #코스닥 #연기금")


# ───────────────────────── 실행 ─────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().strftime("%Y%m%d"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if a.mock:
        data = mock_data(a.date)
    else:
        if not is_trading_day(a.date):
            print(f"[SKIP] {a.date} 휴장일"); return
        data = collect(a.date)

    img = render(data, os.path.join(CFG["OUT_DIR"], f"market_{a.date}.png"))
    text = build_text(data)
    print(f"[IMG] {img}\n[TEXT]\n{text}")

    if a.dry_run or a.mock:
        return
    tid = post_to_x(img, text)
    print(f"[POSTED] https://x.com/i/status/{tid}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr); sys.exit(1)
