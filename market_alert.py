"""
Taiwan Market Alert System
台股大盤定時警報系統

執行時間：09:30 / 10:30 / 11:30 / 12:30（台灣時間）
- 09:30：完整版（含美股昨夜收盤、美元/台幣匯率、最新新聞）
- 10:30 / 11:30 / 12:30：精簡版（台股數據 + 最新新聞）
觸發條件：與前日收盤價相比，漲跌幅 ≥ ±0.3% 才推播

資料來源：
- 即時指數 + 前日收盤：Yahoo Finance ^TWII
- 美股、匯率：Yahoo Finance
- 新聞：Google News RSS（只顯示 2 小時內新聞，避免重複）
"""

import os
import sys
import requests
import email.utils
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta, timezone
import pytz

# ── 時區設定 ──────────────────────────────────────────
TZ = pytz.timezone("Asia/Taipei")
now_tw = datetime.now(TZ)
HOUR  = now_tw.hour
TODAY = date.today().strftime("%Y/%m/%d")

# ── 環境變數 ──────────────────────────────────────────
LINE_TOKEN      = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
FINMIND_TOKEN   = os.environ.get("FINMIND_TOKEN", "")
ALERT_THRESHOLD = 0.003  # 0.3%

USER_IDS = [
    os.environ.get("LINE_USER_ID_1", ""),
    os.environ.get("LINE_USER_ID_2", ""),
    os.environ.get("LINE_USER_ID_3", ""),
    os.environ.get("LINE_USER_ID_4", ""),
    os.environ.get("LINE_USER_ID_5", ""),
]
USER_IDS = [uid.strip() for uid in USER_IDS
            if uid.strip() and uid.strip().startswith(("U", "C"))]

IS_MORNING = (HOUR == 9)

# 新聞只抓幾小時內（避免重複推播舊新聞）
NEWS_MAX_HOURS = 2


# ═══════════════════════════════════════════════════════
# 資料抓取
# ═══════════════════════════════════════════════════════

def get_taiwan_index():
    """
    Yahoo Finance ^TWII
    - closes[-2] = 前日收盤
    - closes[-1] = 今日即時
    - volume 盤中不可靠，改顯示 -- 
    """
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII"
        r = requests.get(url,
                         params={"interval": "1d", "range": "2d"},
                         headers={"User-Agent": "Mozilla/5.0"},
                         timeout=15)
        r.raise_for_status()
        result = r.json()["chart"]["result"][0]
        quote  = result["indicators"]["quote"][0]

        def clean(lst):
            return [x for x in lst if x is not None]

        closes  = clean(quote.get("close",  []))
        opens   = clean(quote.get("open",   []))
        highs   = clean(quote.get("high",   []))
        lows    = clean(quote.get("low",    []))

        if len(closes) < 2:
            print("[WARN] ^TWII 資料不足")
            return None, None

        prev_close = closes[-2]
        close      = closes[-1]
        open_      = opens[-1]  if opens  else close
        high       = highs[-1]  if highs  else close
        low        = lows[-1]   if lows   else close

        print(f"[INFO] ^TWII 即時：{close:.2f}，前日收盤：{prev_close:.2f}")
        return {
            "close": close, "open": open_,
            "high": high,   "low": low,
            "volume_ok": False,  # 盤中 volume 不可靠，標記為不顯示
        }, prev_close

    except Exception as e:
        print(f"[ERROR] ^TWII 失敗: {e}")
        return None, None


def get_us_markets():
    results = {}
    symbols = {"道瓊 DJI": "^DJI", "那斯達克": "^IXIC"}
    for name, sym in symbols.items():
        try:
            r = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                params={"interval": "1d", "range": "2d"},
                headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            r.raise_for_status()
            closes = [c for c in r.json()["chart"]["result"][0]
                      ["indicators"]["quote"][0]["close"] if c is not None]
            if len(closes) >= 2:
                chg_pct = (closes[-1] - closes[-2]) / closes[-2] * 100
                results[name] = {"value": closes[-1], "chg_pct": chg_pct}
        except Exception as e:
            print(f"[WARN] 美股 {name}: {e}")
    return results


def get_usd_twd():
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/USDTWD=X",
            params={"interval": "1d", "range": "2d"},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        closes = [c for c in r.json()["chart"]["result"][0]
                  ["indicators"]["quote"][0]["close"] if c is not None]
        if len(closes) >= 2:
            return {"value": closes[-1], "chg": closes[-1] - closes[-2]}
    except Exception as e:
        print(f"[WARN] 匯率: {e}")
    return None


def get_market_news():
    """
    Google News RSS
    - 只取 NEWS_MAX_HOURS 小時內（預設 2 小時）的新聞
    - 沒有夠新的新聞 → 回傳空 list → 顯示「目前無最新新聞」
    """
    news_list = []
    try:
        url = "https://news.google.com/rss/search?q=台股+大盤+今日&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        root = ET.fromstring(r.content)
        now_tz = datetime.now(timezone(timedelta(hours=8)))

        for item in root.findall(".//item"):
            if len(news_list) >= 3:
                break
            try:
                pub_date = email.utils.parsedate_to_datetime(
                    item.find("pubDate").text)
                pub_tw = pub_date.astimezone(timezone(timedelta(hours=8)))
                age_h = (now_tz - pub_tw).total_seconds() / 3600
                if age_h > NEWS_MAX_HOURS:
                    continue          # 超過 2 小時，跳過
            except:
                continue

            title = item.find("title").text or ""
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
            title = title.strip()
            if len(title) < 8:
                continue
            if len(title) > 30:
                title = title[:30] + "…"

            news_list.append({
                "title":  title,
                "source": "Google新聞",
                "time":   pub_tw.strftime("%H:%M"),
            })

    except Exception as e:
        print(f"[WARN] Google News: {e}")

    print(f"[INFO] 取得 {NEWS_MAX_HOURS} 小時內新聞 {len(news_list)} 則")
    return news_list


# ═══════════════════════════════════════════════════════
# 格式化工具
# ═══════════════════════════════════════════════════════

def fmt_num(n):
    return str(int(round(n)))

def sign_str(val, pct=False):
    if pct:
        return f"+{val:.2f}%" if val >= 0 else f"{val:.2f}%"
    return f"+{int(round(val))}" if val >= 0 else f"{int(round(val))}"

def arrow(val):
    return "▲" if val >= 0 else "▼"

def color_up_down(val):
    return "#FF6B6B" if val >= 0 else "#2DD4A0"


# ═══════════════════════════════════════════════════════
# Flex Message 組裝
# ═══════════════════════════════════════════════════════

def _badge(text, color):
    return {
        "type": "box", "layout": "vertical", "flex": 1,
        "contents": [{"type": "text", "text": text, "size": "md",
                      "weight": "bold", "color": color, "align": "center"}],
        "backgroundColor": color + "28", "cornerRadius": "10px",
        "paddingTop": "10px", "paddingBottom": "10px",
        "borderColor": color + "55", "borderWidth": "1px",
    }

def _stat_box(label, value, value_color="#EEEEEE"):
    return {
        "type": "box", "layout": "vertical",
        "contents": [
            {"type": "text", "text": label, "size": "xxs", "color": "#888888"},
            {"type": "text", "text": value, "size": "md",
             "weight": "bold", "color": value_color},
        ],
        "backgroundColor": "#FFFFFF0D", "cornerRadius": "8px",
        "paddingAll": "10px", "flex": 1,
    }

def _separator():
    return {"type": "separator", "margin": "lg", "color": "#FFFFFF11"}

def _section_label(text):
    return {"type": "text", "text": text, "size": "xxs",
            "color": "#555555", "margin": "md"}

def _news_items(news_list, border_color):
    if not news_list:
        return []  # 無新聞 → 完全不顯示

    contents = [_separator(), _section_label("📰 最新大盤新聞")]

    for news in news_list:
        meta = f"{news['source']} · {news['time']}" if news.get("time") else news["source"]
        contents.append({
            "type": "box", "layout": "vertical",
            "contents": [
                {"type": "text", "text": news["title"], "size": "xs",
                 "color": "#DDDDDD", "wrap": True, "weight": "bold", "maxLines": 2},
                {"type": "text", "text": meta, "size": "xxs",
                 "color": "#555555", "margin": "xs"},
            ],
            "backgroundColor": "#FFFFFF06", "cornerRadius": "8px",
            "paddingAll": "10px", "margin": "sm",
            "borderColor": border_color + "44", "borderWidth": "2px",
        })
    return contents


def build_flex(index_data, prev_close, chg_val, chg_pct, news_list,
               us_data=None, fx_data=None):
    time_label   = f"{HOUR:02d}:30"
    is_up        = chg_pct >= 0
    main_color   = "#FF6B6B" if is_up else "#2DD4A0"
    bg_color     = "#16213E" if is_up else "#0D1B2A"
    alert_bg     = "#3D1A1A" if is_up else "#0D2E22"
    alert_text   = "#FF8585" if is_up else "#2DD4A0"
    alert_msg    = f"⚠️ {'漲' if is_up else '跌'}幅超過警報門檻 {'+' if is_up else ''}{chg_pct:.2f}%"
    border_color = "#FF6B6B" if is_up else "#2DD4A0"

    # 統計格：開盤價／今日最高／今日最低（三格，開盤價移到第一格）
    stat_row1 = [
        _stat_box("開盤價", fmt_num(index_data["open"])),
        _stat_box("今日最高", fmt_num(index_data["high"]),
                  "#FF6B6B" if is_up else "#DDDDDD"),
        _stat_box("今日最低", fmt_num(index_data["low"]),
                  "#2DD4A0" if not is_up else "#DDDDDD"),
    ]

    body_contents = [
        # 大數字 + 前日收盤（右側，與開盤價對調）
        {
            "type": "box", "layout": "horizontal", "margin": "md",
            "alignItems": "center",
            "contents": [
                {
                    "type": "box", "layout": "baseline", "flex": 1,
                    "contents": [
                        {"type": "text", "text": fmt_num(index_data["close"]),
                         "size": "3xl", "weight": "bold", "color": main_color, "flex": 0},
                        {"type": "text", "text": " 點", "size": "sm",
                         "color": "#666666", "gravity": "bottom"},
                    ],
                },
                {
                    "type": "box", "layout": "vertical", "flex": 0,
                    "paddingAll": "8px", "width": "110px",
                    "contents": [
                        {"type": "text", "text": "前日收盤",
                         "size": "xxs", "color": "#777777", "align": "center"},
                        {"type": "text", "text": fmt_num(prev_close),
                         "size": "lg", "weight": "bold", "color": "#CCCCCC",
                         "align": "center"},
                    ],
                },
            ],
        },
        # 漲跌徽章 — 全寬等比
        {
            "type": "box", "layout": "horizontal", "spacing": "sm", "margin": "sm",
            "contents": [
                _badge(f"{arrow(chg_val)} {sign_str(chg_val)} pts", main_color),
                _badge(sign_str(chg_pct, pct=True), main_color),
            ],
        },
        {
            "type": "box", "layout": "horizontal", "spacing": "sm", "margin": "lg",
            "contents": stat_row1,
        },
    ]

    # 09:30 美股 & 匯率
    if IS_MORNING and us_data:
        body_contents.append(_separator())
        body_contents.append(_section_label("🌙 美股昨夜收盤"))
        for name, d in us_data.items():
            c = color_up_down(d["chg_pct"])
            body_contents.append({
                "type": "box", "layout": "horizontal", "margin": "sm",
                "contents": [
                    {"type": "text", "text": name, "size": "xs",
                     "color": "#888888", "flex": 3},
                    {"type": "text", "text": fmt_num(d["value"]),
                     "size": "sm", "color": "#DDDDDD", "weight": "bold",
                     "align": "center", "flex": 3},
                    {"type": "text",
                     "text": f"{arrow(d['chg_pct'])} {abs(d['chg_pct']):.2f}%",
                     "size": "xs", "color": c, "align": "end", "flex": 3},
                ],
            })

    if IS_MORNING and fx_data:
        body_contents.append(_separator())
        body_contents.append({
            "type": "box", "layout": "horizontal", "margin": "sm",
            "contents": [
                {"type": "text", "text": "💱 美元／台幣",
                 "size": "xs", "color": "#666666", "flex": 4},
                {"type": "text", "text": f"{fx_data['value']:.2f}",
                 "size": "sm", "color": "#DDDDDD", "weight": "bold",
                 "align": "center", "flex": 3},
                {"type": "text",
                 "text": f"{'▲' if fx_data['chg'] >= 0 else '▼'} {abs(fx_data['chg']):.2f}",
                 "size": "xs", "color": color_up_down(fx_data["chg"]),
                 "align": "end", "flex": 3},
            ],
        })

    body_contents.extend(_news_items(news_list, border_color))

    return {
        "type": "flex",
        "altText": f"台股大盤警報 {time_label}｜{fmt_num(index_data['close'])}點 ({sign_str(chg_pct, pct=True)})",
        "contents": {
            "type": "bubble", "size": "mega",
            "styles": {
                "body":   {"backgroundColor": bg_color},
                "footer": {"backgroundColor": bg_color},
            },
            "header": {
                "type": "box", "layout": "horizontal",
                "backgroundColor": bg_color, "paddingAll": "14px",
                "contents": [
                    {
                        "type": "box", "layout": "vertical", "flex": 1,
                        "contents": [
                            {"type": "text",
                             "text": "🇹🇼 台股加權指數｜定時警報",
                             "size": "xs", "color": "#AAAAAA"},
                        ],
                    },
                    {"type": "text", "text": time_label, "size": "lg",
                     "weight": "bold", "color": "#FFFFFF",
                     "gravity": "center", "flex": 0},
                ],
            },
            "body": {
                "type": "box", "layout": "vertical",
                "contents": body_contents,
                "paddingAll": "16px", "spacing": "none",
            },
            "footer": {
                "type": "box", "layout": "vertical", "paddingAll": "12px",
                "contents": [
                    {
                        "type": "box", "layout": "horizontal",
                        "contents": [{"type": "text", "text": alert_msg,
                                      "size": "sm", "color": alert_text, "wrap": True}],
                        "backgroundColor": alert_bg,
                        "cornerRadius": "8px", "paddingAll": "10px",
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": f"📅 {TODAY}",
                             "size": "xs", "color": "#888888", "flex": 1},
                            {"type": "text", "text": f"⏰ {now_tw.strftime('%H:%M')}",
                             "size": "xs", "color": "#888888",
                             "align": "end", "flex": 1},
                        ],
                    },
                ],
            },
        },
    }


# ═══════════════════════════════════════════════════════
# LINE 推播
# ═══════════════════════════════════════════════════════

def push_flex(user_id, flex_msg):
    r = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LINE_TOKEN}",
        },
        json={"to": user_id, "messages": [flex_msg]},
        timeout=15,
    )
    if r.status_code == 200:
        print(f"[OK] 推播成功 → {user_id}")
    else:
        print(f"[ERROR] 推播失敗 {user_id}: {r.status_code} {r.text}")


# ═══════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════

def main():
    print(f"[INFO] 執行時間：{now_tw.strftime('%Y-%m-%d %H:%M')} 台灣時間")
    print(f"[INFO] 收件人數：{len(USER_IDS)}")

    if not USER_IDS:
        print("[WARN] 無收件人，結束")
        sys.exit(0)
    if not LINE_TOKEN:
        print("[ERROR] LINE_CHANNEL_ACCESS_TOKEN 未設定")
        sys.exit(1)

    index_data, prev_close = get_taiwan_index()
    if not index_data or not prev_close:
        print("[ERROR] 無法取得台股資料，結束")
        sys.exit(1)

    chg_val = index_data["close"] - prev_close
    chg_pct = chg_val / prev_close

    print(f"[INFO] 漲跌幅：{chg_pct*100:.2f}%")

    if abs(chg_pct) < ALERT_THRESHOLD:
        print(f"[INFO] 未超過門檻 ±{ALERT_THRESHOLD*100:.1f}%，靜默")
        sys.exit(0)

    us_data   = get_us_markets() if IS_MORNING else None
    fx_data   = get_usd_twd()    if IS_MORNING else None
    news_list = get_market_news()

    flex_msg = build_flex(
        index_data=index_data,
        prev_close=prev_close,
        chg_val=chg_val,
        chg_pct=chg_pct * 100,
        news_list=news_list,
        us_data=us_data,
        fx_data=fx_data,
    )

    for uid in USER_IDS:
        push_flex(uid, flex_msg)

    print("[INFO] 完成")


if __name__ == "__main__":
    main()
