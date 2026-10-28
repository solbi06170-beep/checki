import streamlit as st
from google import genai
from PIL import Image
from supabase import create_client
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from io import BytesIO
from collections import Counter
import uuid
import requests
import re
import os
import base64
import html

# =============================================================
# CHECKI v4 (모바일 앱 스타일)
# - 기존 Supabase 테이블 2개(checki_expenses, checki_records) 그대로 사용
# - DB에 연결되지 않으면 화면 안내 없이 세션 저장으로 자동 동작
# - AI 분석 = ① 구매 화면 다크패턴 분석 + ② 개인 소비데이터 기반 맞춤 판단
# =============================================================
st.set_page_config(page_title="CHECKI | 체키", page_icon="🔎", layout="centered",
                   initial_sidebar_state="collapsed")

KST = timezone(timedelta(hours=9))
MODEL = "gemini-3.5-flash-lite"
CATEGORIES = ["패션/의류", "뷰티", "식품", "생활용품", "전자기기",
              "가구/인테리어", "취미/여가", "구독서비스", "기타"]
CAT_ICON = {"패션/의류": "👕", "뷰티": "💄", "식품": "🍔", "생활용품": "🧴", "전자기기": "🎧",
            "가구/인테리어": "🛋️", "취미/여가": "🎮", "구독서비스": "📺", "기타": "🛍️"}
MASCOTS = {
    "scan": "checki_mascot_scan.png",
    "search": "checki_mascot_search.png",
    "wait": "checki_mascot_wait.png",
    "chart": "checki_mascot_chart.png",
}
NAV = ["홈", "체크", "리포트", "기록"]
NAV_ICON = {"홈": "🏠", "체크": "🔎", "리포트": "📊", "기록": "🗂️"}
DECISION_LABEL = {"PENDING": "선택 대기", "HOLD": "30분 생각하기",
                  "BUY": "구매 완료", "NOT_BUY": "구매하지 않음"}
DECISION_BADGE = {"PENDING": "선택 대기", "HOLD": "보류 중",
                  "BUY": "구매", "NOT_BUY": "포기"}
TIME_SLOTS = [("새벽", 0, 6), ("오전", 6, 12), ("오후", 12, 18),
              ("저녁", 18, 22), ("밤", 22, 24)]
LATE_NIGHT = {22, 23, 0, 1, 2, 3, 4}
DEFAULT_BUDGET = 500000
DEFAULT_GOAL = 200000
RECOMMEND = {
    "BUY": ("✅", "구매해도 괜찮아요"),
    "HOLD": ("⏱️", "30분 보류를 권장해요"),
    "RECONSIDER": ("🛑", "구매를 다시 생각해보세요"),
}
ss = st.session_state


# ---------------- 공통 유틸 ----------------
def now_kst():
    return datetime.now(KST)


def iso_now():
    return now_kst().isoformat()


def money(value):
    try:
        return f"{int(value or 0):,}원"
    except (ValueError, TypeError):
        return "0원"


def number(value):
    try:
        return int(float(value or 0))
    except (ValueError, TypeError):
        return 0


def safe(value):
    return html.escape(str(value or ""))


def parse_date(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=KST) if dt.tzinfo is None else dt.astimezone(KST)
    except (ValueError, TypeError):
        return None


def time_slot(hour):
    for name, start, end in TIME_SLOTS:
        if start <= hour < end:
            return name
    return "밤"


def greeting(hour):
    if 5 <= hour < 11:
        return "좋은 아침이에요"
    if 11 <= hour < 17:
        return "좋은 오후예요"
    if 17 <= hour < 22:
        return "편안한 저녁이에요"
    return "늦은 밤이에요"


def norm_name(value):
    return re.sub(r"[\s\W_]+", "", str(value or "").lower())


def get_setting(name, default):
    """예산/저금 목표: 새 테이블 없이 URL 파라미터에 저장해 재접속 시에도 유지."""
    if name not in ss:
        value = number(st.query_params.get(name))
        ss[name] = value if value > 0 else default
    return ss[name]


def set_setting(name, value):
    ss[name] = number(value)
    st.query_params[name] = str(number(value))


def mascot_src(which):
    path = MASCOTS.get(which)
    if not path or not os.path.isfile(path):
        return ""
    key = f"_mascot_{which}"
    if key not in ss:
        with open(path, "rb") as f:
            ss[key] = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    return ss[key]


def mascot_img(which, cls=""):
    src = mascot_src(which)
    return f'<img class="{cls}" src="{src}" alt="">' if src else ""


def preview_image(image):
    try:
        im = image.copy()
        im.thumbnail((900, 900))
        buf = BytesIO()
        if im.mode == "RGBA":
            im.save(buf, format="PNG")
            mime = "image/png"
        else:
            im.convert("RGB").save(buf, format="JPEG", quality=85)
            mime = "image/jpeg"
        encoded = base64.b64encode(buf.getvalue()).decode()
        st.markdown(f'<div class="preview"><img src="data:{mime};base64,{encoded}"></div>',
                    unsafe_allow_html=True)
    except Exception:
        st.image(image, width=260)


# ---------------- 스타일 ----------------
# 아이콘(Material Symbols) 요소에는 폰트를 덮어쓰지 않는다 → '_arrow_right' 글자 깨짐 방지
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css');
:root{--blue:#1689F8;--blue2:#5DB4FF;--deep:#0F4C9C;--navy:#14283D;--muted:#7A8DA3;--line:#E4EDF6;
  --bg:#EAF3FD;--surface:#F7FAFE;--card:#FFFFFF;--soft:#EEF6FF;--green:#12A27A;--red:#E25555;--amber:#E9A21B}
.stApp *:not([data-testid="stIconMaterial"]):not([class*="material"]):not(code):not(pre):not(kbd){
  font-family:"Pretendard Variable",Pretendard,-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
[data-testid="stIconMaterial"],[class*="material-symbols"],[class*="material-icons"]{
  font-family:"Material Symbols Rounded","Material Symbols Outlined","Material Icons"!important}
.stApp{background:radial-gradient(800px 500px at 90% -5%,#D4E9FF 0%,transparent 60%),
  radial-gradient(600px 420px at 0% 100%,#E3F0FF 0%,transparent 60%),var(--bg);color:var(--navy)}
header[data-testid="stHeader"],#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"],
[data-testid="stStatusWidget"]{display:none!important}

/* 앱 화면: 모바일 폭으로 가운데 정렬 */
.block-container{max-width:440px!important;padding:14px 16px 64px!important}

/* 메뉴 탭: 화면 위쪽에 고정하지 않고 배치 → 내용을 가리지 않음 */
.st-key-nav,.st-key-nav > div,.st-key-nav [data-testid="stButtonGroup"],
.st-key-nav [data-testid="stButtonGroup"] > div{width:100%!important;max-width:100%!important}
.st-key-nav{margin:0 0 6px}
[data-testid="stButtonGroup"] div:has(> button){display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr));width:100%!important;
  background:#FFFFFF;border:1px solid var(--line);border-radius:22px;padding:5px;gap:4px;box-shadow:0 8px 24px #1C5FA41F}
[data-testid="stButtonGroup"] button{width:100%!important;min-width:0!important;border:0!important;border-radius:17px!important;
  min-height:48px;padding:0 4px!important;background:transparent!important;color:var(--muted)!important;box-shadow:none!important}
[data-testid="stButtonGroup"] button *{white-space:nowrap!important;overflow:visible!important;text-overflow:clip!important;max-width:none!important}
[data-testid="stButtonGroup"] button p{font-size:13px!important;font-weight:800!important;color:inherit!important;margin:0!important}
[data-testid="stButtonGroup"] button[kind*="Active"],[data-testid="stButtonGroup"] button[aria-checked="true"],
[data-testid="stButtonGroup"] button[aria-pressed="true"]{background:linear-gradient(135deg,var(--blue2),var(--blue))!important;
  color:#fff!important;box-shadow:0 6px 16px #1689F84D!important}
div[role="radiogroup"]{gap:6px;flex-wrap:wrap}
div[role="radiogroup"] label{background:#fff;border:1px solid var(--line);border-radius:14px;padding:6px 12px!important;margin:0!important}

/* 헤더 */
.app-head{display:flex;align-items:center;justify-content:space-between;margin:2px 0 14px}
.app-head .hi{font-size:13px;color:var(--muted);font-weight:600}
.app-head h2{font-size:21px;font-weight:900;letter-spacing:-.8px;color:var(--navy);margin:2px 0 0;padding:0;line-height:1.3}
.app-head h2 em{font-style:normal;color:var(--blue)}
.avatar{width:46px;height:46px;border-radius:16px;background:linear-gradient(135deg,#FFFFFF,#E2F0FF);border:1px solid var(--line);
  display:flex;align-items:center;justify-content:center;overflow:hidden;box-shadow:0 6px 16px #1C5FA41F;font-size:22px;flex:0 0 46px}
.avatar img{width:42px;height:42px;object-fit:contain}
.brand-row{display:flex;align-items:center;gap:6px;margin-bottom:4px}
.brand-row b{font-size:15px;font-weight:900;letter-spacing:-.5px;color:var(--blue)}
.brand-row span{font-size:9.5px;font-weight:800;letter-spacing:1.6px;color:#9DB2C6}

/* 히어로 카드 */
.hero{position:relative;overflow:hidden;border-radius:28px;padding:20px;color:#fff;margin:0 0 12px;
  background:linear-gradient(140deg,#62B8FF 0%,#1689F8 45%,#0F4C9C 100%);box-shadow:0 18px 36px #1689F83D}
.hero:after{content:"";position:absolute;right:-60px;top:-60px;width:200px;height:200px;border-radius:50%;background:#FFFFFF14}
.hero .row{display:flex;align-items:center;justify-content:space-between;gap:12px;position:relative;z-index:1}
.hero .pill{display:inline-block;background:#FFFFFF2B;border:1px solid #FFFFFF40;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:800}
.hero .label{font-size:13px;color:#DDEEFF;font-weight:600;margin-top:12px}
.hero .big{font-size:30px;font-weight:900;letter-spacing:-1.2px;line-height:1.2;margin-top:2px;white-space:nowrap}
.hero .sub{font-size:12px;color:#CFE5FF;margin-top:4px}
.ring{position:relative;width:96px;height:96px;flex:0 0 96px}
.ring .track{position:absolute;inset:0;border-radius:50%;background:conic-gradient(#fff calc(var(--p) * 1%),#FFFFFF33 0);
  -webkit-mask:radial-gradient(farthest-side,transparent calc(100% - 10px),#000 calc(100% - 9px));
  mask:radial-gradient(farthest-side,transparent calc(100% - 10px),#000 calc(100% - 9px))}
.ring .val{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.1}
.ring .val b{font-size:20px;font-weight:900}
.ring .val small{font-size:10px;color:#DDEEFF;font-weight:700}
.ring.dark .track{background:conic-gradient(var(--c,var(--blue)) calc(var(--p) * 1%),#E6EEF6 0)}
.ring.dark .val b{color:var(--navy)}.ring.dark .val small{color:var(--muted)}
.hero-intro{position:relative;overflow:hidden;border-radius:28px;padding:22px 20px;color:#fff;margin:0 0 12px;min-height:150px;
  background:linear-gradient(140deg,#62B8FF 0%,#1689F8 45%,#0F4C9C 100%);box-shadow:0 18px 36px #1689F83D}
.hero-intro h1{color:#fff;font-size:23px;font-weight:900;letter-spacing:-1px;line-height:1.35;margin:10px 0 6px;padding:0}
.hero-intro p{color:#DDEEFF;font-size:12.5px;line-height:1.55;margin:0;max-width:64%}
.hero-intro img{position:absolute;right:6px;bottom:4px;width:112px;max-height:124px;object-fit:contain;filter:drop-shadow(0 10px 16px #00000030)}

/* 미니 통계 */
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:12px 10px;box-shadow:0 6px 18px #1C5FA40D}
.tile .ic{width:30px;height:30px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:15px;margin-bottom:8px}
.tile .ic.blue{background:#E6F2FF}.tile .ic.green{background:#E2F7EF}.tile .ic.amber{background:#FFF3DC}.tile .ic.red{background:#FFE9E9}
.tile b{display:block;font-size:15px;font-weight:900;color:var(--navy);letter-spacing:-.4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tile span{font-size:11px;color:var(--muted);font-weight:700}

/* 섹션 */
.sec{display:flex;align-items:flex-end;justify-content:space-between;margin:22px 2px 8px}
.sec b{font-size:16.5px;font-weight:850;color:var(--navy);letter-spacing:-.4px}
.sec span{font-size:12px;color:var(--blue);font-weight:700}
.sec small{display:block;font-size:12px;color:var(--muted);font-weight:600;margin-top:2px}
.kicker{color:var(--blue);font-size:11px;font-weight:850;letter-spacing:.8px;margin-bottom:6px}
.step{display:flex;align-items:center;gap:8px;font-weight:850;font-size:14.5px;color:var(--navy);margin:16px 2px 6px}
.step i{font-style:normal;width:22px;height:22px;border-radius:8px;background:linear-gradient(135deg,var(--blue2),var(--blue));color:#fff;
  font-size:12px;display:inline-flex;align-items:center;justify-content:center}

/* 가로 스크롤 카드 */
.hscroll{display:flex;gap:10px;overflow-x:auto;scroll-snap-type:x mandatory;padding:2px 2px 10px;margin:0 -2px;scrollbar-width:none}
.hscroll::-webkit-scrollbar{display:none}
.hcard{flex:0 0 148px;scroll-snap-align:start;background:var(--card);border:1px solid var(--line);border-radius:22px;padding:14px;box-shadow:0 6px 18px #1C5FA40D}
.hcard.on{background:linear-gradient(150deg,var(--blue2),var(--blue));color:#fff;border:0;box-shadow:0 12px 24px #1689F840}
.hcard .n{width:26px;height:26px;border-radius:9px;background:var(--soft);color:var(--blue);font-weight:900;font-size:12px;display:flex;align-items:center;justify-content:center}
.hcard.on .n{background:#FFFFFF33;color:#fff}
.hcard b{display:block;font-size:13.5px;margin-top:10px;color:inherit;font-weight:850}
.hcard p{font-size:11.5px;line-height:1.45;margin:4px 0 0;color:var(--muted)}
.hcard.on p{color:#E1EFFF}

/* 리스트 */
.list{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:4px 14px;box-shadow:0 6px 18px #1C5FA40D;margin:6px 0}
.lrow{display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid #EEF3F8}
.lrow:last-child{border-bottom:0}
.lrow .ic{width:40px;height:40px;border-radius:14px;background:var(--soft);display:flex;align-items:center;justify-content:center;font-size:19px;flex:0 0 40px}
.lrow .tx{flex:1;min-width:0}
.lrow .tx b{display:block;font-size:14px;font-weight:800;color:var(--navy);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lrow .tx span{font-size:11.5px;color:var(--muted)}
.lrow .rt{text-align:right;flex:0 0 auto}
.lrow .rt b{display:block;font-size:13.5px;font-weight:850;color:var(--navy)}
.badge{display:inline-block;padding:3px 9px;border-radius:20px;font-size:11px;font-weight:850}
.badge.HOLD{background:#E5F2FF;color:#1468C2}.badge.BUY{background:#EEF1F4;color:#55687A}
.badge.NOT_BUY{background:#E3F7EE;color:#14855A}.badge.PENDING{background:#FFF4D6;color:#A86E00}
.rcard{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:4px 14px 10px;margin:10px 0 4px;box-shadow:0 6px 18px #1C5FA40D}
.rcard .lrow{border-bottom:0}
.rsum{font-size:12.5px;color:#4E6578;line-height:1.5;background:var(--surface);border-radius:12px;padding:8px 10px}

/* 결과 */
.card{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:18px;margin:10px 0;box-shadow:0 8px 24px #1C5FA412}
.result-head{display:flex;gap:14px;align-items:center}
.result-head h3{margin:8px 0 0;font-size:15px;line-height:1.5;font-weight:800;color:var(--navy);padding:0}
.level{display:inline-block;padding:4px 10px;border-radius:20px;font-size:11.5px;font-weight:850}
.level.low{background:#E3F7EE;color:#14855A}.level.medium{background:#FFF4D6;color:#A86E00}.level.high{background:#FFE6E6;color:#C23B3B}
.kv dt{font-size:11.5px;font-weight:850;color:var(--muted);margin-top:14px}
.kv dd{margin:6px 0 0;font-size:13.5px;line-height:1.6;color:var(--navy)}
.tags{display:flex;flex-wrap:wrap;gap:6px}
.tag{background:var(--surface);border:1px solid var(--line);border-radius:20px;padding:4px 10px;font-size:12px;font-weight:700;color:#4A6378}
.tag.warn{background:#FFF1F1;border-color:#F6D5D5;color:#B03C3C}
.rec{display:flex;align-items:center;gap:12px;border-radius:18px;padding:14px}
.rec.BUY{background:#E9F8F1}.rec.HOLD{background:#EAF4FF}.rec.RECONSIDER{background:#FFEFEF}
.rec .icon{font-size:26px;line-height:1}
.rec b{font-size:15.5px;color:var(--navy);display:block}
.rec span{font-size:13px;color:#4E6578;line-height:1.55}
.chips{display:flex;flex-direction:column;gap:7px;margin-top:10px}
.chip{border-radius:14px;padding:10px 12px;font-size:13px;line-height:1.5;font-weight:600}
.chip.high{background:#FFF0F0;color:#A23636}.chip.mid{background:#FFF8E6;color:#8A5B00}
.chip.info{background:#EEF6FF;color:#245A8A}.chip.good{background:#EAF8F1;color:#1E7A52}
.ctx{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:12px 14px;font-size:12px;line-height:1.7;color:#3D566C;white-space:pre-wrap;word-break:keep-all}
.data-chip{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;margin:10px 0 4px}
.data-chip::-webkit-scrollbar{display:none}
.data-chip span{flex:0 0 auto;background:var(--card);border:1px solid var(--line);border-radius:20px;padding:6px 11px;font-size:11.5px;font-weight:700;color:#4A6378}
.meta{font-size:12px;color:var(--muted)}

/* 차트 */
.bars{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:12px 16px;margin:6px 0;box-shadow:0 6px 18px #1C5FA40D}
.bar-row{display:flex;align-items:center;gap:10px;margin:10px 0;font-size:12.5px}
.bar-row .lb{flex:0 0 78px;color:#4A6378;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar-row .tr{flex:1;height:10px;background:#EDF3F8;border-radius:10px;overflow:hidden}
.bar-row .fl{height:100%;background:linear-gradient(90deg,var(--blue2),var(--blue));border-radius:10px}
.bar-row .fl.late{background:linear-gradient(90deg,#A497FF,#6A5CF0)}
.bar-row .vl{flex:0 0 auto;min-width:58px;text-align:right;font-weight:800;color:var(--navy)}
.vbars{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;height:120px;padding:6px 4px 0}
.vbar{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;gap:6px}
.vbar .col{width:100%;max-width:34px;border-radius:10px;background:linear-gradient(180deg,var(--blue2),var(--blue));min-height:4px}
.vbar .col.late{background:linear-gradient(180deg,#B3A8FF,#6A5CF0)}
.vbar .col.zero{background:#E6EEF6}
.vbar span{font-size:11px;color:var(--muted);font-weight:700}
.vbar small{font-size:10.5px;color:var(--navy);font-weight:800}
.budget{display:flex;align-items:center;gap:16px}
.budget .info{flex:1;min-width:0}
.budget .info b{display:block;font-size:22px;font-weight:900;color:var(--navy);letter-spacing:-.6px}
.progress-bg{height:10px;border-radius:20px;background:#E3EDF3;overflow:hidden;margin:10px 0 6px}
.progress-fill{height:100%;background:linear-gradient(90deg,#3BC9A8,var(--blue));border-radius:20px}

.pig{border-radius:24px;padding:18px;background:linear-gradient(140deg,#DDF8EF,#E3F1FF);border:1px solid #CDEDE7;margin:8px 0;display:flex;gap:14px;align-items:center}
.pig .emoji{width:54px;height:54px;border-radius:18px;background:#FFFFFFB3;display:flex;align-items:center;justify-content:center;font-size:30px;flex:0 0 54px}
.pig .body{flex:1;min-width:0}
.pig .amount{font-size:24px;font-weight:900;color:#087E75;letter-spacing:-.8px}
.pig .sub{font-size:11.5px;color:#527E80}
.hold{background:linear-gradient(135deg,#EAF4FF,#F6FBFF);border:1px solid #D4E9FC;border-radius:16px;padding:12px;margin:4px 0;text-align:center}
.hold .clock{font-size:28px;font-weight:900;color:var(--blue);font-variant-numeric:tabular-nums;letter-spacing:1px}
.hold small{color:var(--muted);font-size:11.5px}
.notice{display:flex;gap:10px;align-items:center;background:#FFF8E6;border:1px solid #F3E2B0;border-radius:18px;padding:12px 14px;font-size:13px;font-weight:700;color:#7A5300;margin:10px 0}
.empty{text-align:center;padding:24px 12px;color:var(--muted);font-size:13px;line-height:1.6;background:var(--card);border:1.5px dashed #D3E1EC;border-radius:22px;margin:6px 0}
.empty .e{font-size:30px;display:block;margin-bottom:4px}

/* 위젯 */
.preview{text-align:center;margin:10px 0}
.preview img{max-width:min(260px,80vw);max-height:340px;border-radius:18px;border:1px solid var(--line);box-shadow:0 8px 22px #1C5FA41F}
.stButton>button{border-radius:16px!important;min-height:50px;font-weight:800!important;border:1px solid var(--line)!important;background:#fff!important;color:var(--navy)!important}
.stButton>button[kind="primary"]{background:linear-gradient(120deg,#1689F8,#5DB4FF)!important;border:0!important;color:#fff!important;box-shadow:0 10px 22px #1689F84D}
.stButton>button:disabled{opacity:.5}
.stTextInput input,.stNumberInput input{border-radius:14px!important;background:#fff!important}
[data-baseweb="select"]>div{border-radius:14px!important;background:#fff!important}
[data-testid="stFileUploaderDropzone"]{border-radius:18px;background:#fff;border:1.5px dashed #C9DCEB}
[data-testid="stTabs"] [role="tablist"]{gap:6px;background:#E6EFF8;border-radius:16px;padding:4px}
[data-testid="stTabs"] button[role="tab"]{flex:1;border-radius:12px;padding:6px 8px}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{background:#fff;box-shadow:0 4px 10px #1C5FA41A}
[data-testid="stTabs"] button p{font-weight:800}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],[data-testid="stTabs"] [data-baseweb="tab-border"]{display:none}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] p{color:var(--blue)!important}
[data-testid="stWidgetLabel"] p{font-weight:700;color:#4A6378}
/* 마스코트 */
@keyframes floaty{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
@keyframes pop{0%{transform:translateY(6px) scale(.96);opacity:0}100%{transform:none;opacity:1}}
@keyframes twinkle{0%,100%{opacity:.25;transform:scale(.8)}50%{opacity:1;transform:scale(1.1)}}
.float{animation:floaty 3.4s ease-in-out infinite}
.spark{position:absolute;z-index:1;color:#fff;font-size:13px;animation:twinkle 2.6s ease-in-out infinite}
.mhero{position:relative;overflow:hidden;border-radius:30px;padding:20px 20px 18px;color:#fff;margin:0 0 12px;min-height:182px;
  background:linear-gradient(140deg,#62B8FF 0%,#1689F8 45%,#0F4C9C 100%);box-shadow:0 18px 36px #1689F83D}
.mhero:before{content:"";position:absolute;right:-40px;bottom:-50px;width:230px;height:230px;border-radius:50%;
  background:radial-gradient(circle,#FFFFFF59 0%,#FFFFFF00 68%)}
.mhero .tx{position:relative;z-index:2;max-width:60%}
.mhero .pill{display:inline-block;background:#FFFFFF2B;border:1px solid #FFFFFF40;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:800}
.mhero .label{font-size:12.5px;color:#DDEEFF;font-weight:600;margin-top:12px}
.mhero .big{font-size:27px;font-weight:900;letter-spacing:-1px;line-height:1.2;margin-top:2px;white-space:nowrap}
.mhero .sub{font-size:11.5px;color:#CFE5FF;margin-top:2px}
.mhero .bar{height:8px;background:#FFFFFF33;border-radius:10px;overflow:hidden;margin:10px 0 6px}
.mhero .bar i{display:block;height:100%;background:#fff;border-radius:10px}
.mhero .m{position:absolute;right:-4px;bottom:-6px;width:156px;z-index:1;text-align:center}
.mhero .m img{width:156px;max-height:170px;object-fit:contain;filter:drop-shadow(0 16px 20px #00000045)}
.mhero .m .em{font-size:84px;line-height:1.1}
.phero{position:relative;overflow:hidden;border-radius:28px;padding:18px 18px 16px;margin:0 0 10px;min-height:156px;
  background:linear-gradient(145deg,#FFFFFF 0%,#EAF4FF 58%,#D3E8FF 100%);border:1px solid #D9E9F8;box-shadow:0 12px 30px #1C5FA41A}
.phero:before{content:"";position:absolute;right:-30px;bottom:-40px;width:200px;height:200px;border-radius:50%;
  background:radial-gradient(circle,#9ED0FF80 0%,#9ED0FF00 68%)}
.phero .tx{position:relative;z-index:2;max-width:63%}
.phero .hi{font-size:12.5px;color:var(--muted);font-weight:600}
.phero h2{font-size:22px;font-weight:900;letter-spacing:-.8px;color:var(--navy);margin:2px 0 0;padding:0;line-height:1.3}
.phero h2 em{font-style:normal;color:var(--blue)}
.say{display:inline-block;margin-top:10px;background:#fff;border:1px solid var(--line);border-radius:16px 16px 16px 4px;
  padding:8px 11px;font-size:12px;font-weight:700;color:#35506A;line-height:1.45;box-shadow:0 6px 14px #1C5FA414;animation:pop .5s ease-out}
.phero .m{position:absolute;right:2px;bottom:-4px;width:132px;z-index:1;text-align:center}
.phero .m img{width:132px;max-height:146px;object-fit:contain;filter:drop-shadow(0 12px 16px #1C5FA44D)}
.phero .m .em{font-size:70px;line-height:1.2}
.phero .spark{color:var(--blue2)}
.talk{display:flex;align-items:flex-end;gap:8px;margin:16px 0 4px}
.talk .m{flex:0 0 86px;position:relative;text-align:center}
.talk .m img{width:86px;height:86px;object-fit:contain;filter:drop-shadow(0 10px 12px #1C5FA433)}
.talk .m .em{font-size:52px}
.talk .m:after{content:"";position:absolute;left:20px;right:20px;bottom:-5px;height:8px;border-radius:50%;background:#1C5FA424;filter:blur(2px)}
.bubble{flex:1;position:relative;background:#fff;border:1px solid var(--line);border-radius:22px 22px 22px 6px;padding:13px 15px;
  font-size:13.5px;font-weight:650;color:var(--navy);line-height:1.55;box-shadow:0 8px 20px #1C5FA414;margin-bottom:26px;animation:pop .5s ease-out}
.bubble small{display:block;color:var(--blue);font-size:11px;font-weight:850;margin-bottom:3px;letter-spacing:.3px}
.rec .mimg{width:66px;height:66px;object-fit:contain;flex:0 0 66px;filter:drop-shadow(0 8px 10px #1C5FA433)}
.empty img{width:92px;height:92px;object-fit:contain;display:block;margin:0 auto 6px}
@media(max-width:400px){
  .mhero .m,.mhero .m img{width:128px}.phero .m,.phero .m img{width:110px}.mhero .big{font-size:24px}
}
</style>
""", unsafe_allow_html=True)

# ---------------- 연결 (기존 Secrets 이름 유지, 없어도 앱은 동작) ----------------
def secret(name):
    try:
        return st.secrets.get(name)
    except Exception:
        return None


GEMINI_API_KEY = secret("GEMINI_API_KEY")
SUPABASE_URL = secret("SUPABASE_URL")
SUPABASE_KEY = secret("SUPABASE_KEY")


@st.cache_resource
def get_gemini(key):
    return genai.Client(api_key=key)


@st.cache_resource
def get_supabase(url, key):
    return create_client(url, key)


gemini, supabase = None, None
try:
    if GEMINI_API_KEY:
        gemini = get_gemini(GEMINI_API_KEY)
except Exception:
    gemini = None
try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = get_supabase(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    supabase = None

if "user_id" not in ss:
    try:
        uid = st.query_params.get("uid")
        if isinstance(uid, list):
            uid = uid[0]
        if uid:
            uuid.UUID(str(uid))
            ss.user_id = str(uid)
        else:
            ss.user_id = str(uuid.uuid4())
            st.query_params["uid"] = ss.user_id
    except Exception:
        ss.user_id = str(uuid.uuid4())
user_id = ss.user_id


# ---------------- 데이터 (DB 실패 시 조용히 세션 저장) ----------------
def online():
    return supabase is not None and not ss.get("db_offline")


def go_offline(exc):
    ss["db_offline"] = True
    ss["db_error"] = str(exc)


def local(name):
    if name not in ss:
        ss[name] = []
    return ss[name]


def by_created_desc(rows):
    return sorted(rows, key=lambda r: str(r.get("created_at") or ""), reverse=True)


def get_expenses():
    if online():
        try:
            response = (supabase.table("checki_expenses").select("*")
                        .eq("user_id", user_id).order("created_at", desc=True).execute())
            return response.data or []
        except Exception as exc:
            go_offline(exc)
    return by_created_desc(local("local_expenses"))


def get_records():
    if online():
        try:
            response = (supabase.table("checki_records").select("*")
                        .eq("user_id", user_id).order("created_at", desc=True).execute())
            return response.data or []
        except Exception as exc:
            go_offline(exc)
    return by_created_desc(local("local_records"))


def add_expense(category, item_name, amount, when=None):
    when = when or now_kst()
    data = {
        "user_id": user_id, "category": category, "item_name": item_name,
        "amount": number(amount), "purchased_at": when.date().isoformat(),
        "created_at": when.isoformat(),
    }
    if online():
        try:
            supabase.table("checki_expenses").insert(data).execute()
            return True
        except Exception as exc:
            go_offline(exc)
    local("local_expenses").append(dict(data, id=str(uuid.uuid4())))
    return True


def insert_record(result, category, decision="PENDING", saved_amount=0):
    now = now_kst()
    data = {
        "user_id": user_id,
        "product_name": result["product_name"],
        "category": category,
        "product_price": number(result["price"]),
        "risk_level": result["risk_level"],
        "risk_score": number(result["risk_score"]),
        "one_line_summary": result["summary"],
        "detected_elements": result["detected"],
        "ai_result": result["raw"],  # AI 원문 + AI가 참고한 개인 소비데이터 요약
        "action_text": DECISION_LABEL.get(decision, "선택 대기"),
        "decision": decision,
        "saved_amount": number(saved_amount),
        "hold_started_at": now.isoformat() if decision == "HOLD" else None,
        "hold_until": (now + timedelta(minutes=30)).isoformat() if decision == "HOLD" else None,
        "created_at": now.isoformat(),
    }
    if online():
        try:
            response = supabase.table("checki_records").insert(data).execute()
            if response.data:
                return response.data[0]
        except Exception as exc:
            go_offline(exc)
    row = dict(data, id=str(uuid.uuid4()))
    local("local_records").append(row)
    return row


def update_record(record_id, decision, saved_amount=0):
    if not record_id:
        return False
    now = now_kst()
    data = {
        "decision": decision,
        "action_text": DECISION_LABEL.get(decision, "선택 대기"),
        "saved_amount": number(saved_amount),
    }
    if decision == "HOLD":
        data["hold_started_at"] = now.isoformat()
        data["hold_until"] = (now + timedelta(minutes=30)).isoformat()
    else:
        data["decided_at"] = now.isoformat()
    for row in local("local_records"):
        if row.get("id") == record_id:
            row.update(data)
            return True
    if online():
        try:
            supabase.table("checki_records").update(data).eq("id", record_id).eq("user_id", user_id).execute()
            return True
        except Exception as exc:
            go_offline(exc)
    st.toast("기록을 바꾸지 못했어요. 다시 시도해주세요.")
    return False


def finalize_latest(decision, saved_amount=0):
    result = ss.get("latest_analysis")
    if not result:
        return False
    category = ss.get("latest_category", "기타")
    existing = ss.get("latest_record")
    if existing and existing.get("id"):
        if update_record(existing["id"], decision, saved_amount):
            return True
    return insert_record(result, category, decision, saved_amount) is not None


def clear_latest():
    for key in ("latest_analysis", "latest_record", "latest_category",
                "purchase_action", "latest_buy_amount", "show_ctx"):
        ss.pop(key, None)


def go(page):
    """버튼 처리 후 페이지 이동 (위젯 생성 후 nav 직접 변경 오류 방지)."""
    ss["pending_nav"] = page


def add_sample_data():
    """발표·체험용 샘플 소비 (최근 한 달)."""
    now = now_kst()
    samples = [
        ("식품", "배달 치킨", 23000, 1, 23), ("구독서비스", "넷플릭스", 17000, 2, 10),
        ("패션/의류", "후드티", 49000, 3, 0), ("뷰티", "선크림", 18000, 5, 14),
        ("전자기기", "무선 이어폰", 89000, 7, 1), ("식품", "배달 치킨", 21000, 9, 22),
        ("구독서비스", "유튜브 프리미엄", 14900, 12, 9), ("생활용품", "세제", 12000, 15, 16),
        ("패션/의류", "운동화", 79000, 18, 23), ("취미/여가", "보드게임", 32000, 22, 20),
    ]
    for cat, name, amt, days, hour in samples:
        when = (now - timedelta(days=days)).replace(hour=hour, minute=15, second=0, microsecond=0)
        if when > now:
            when = now - timedelta(minutes=days)
        add_expense(cat, name, amt, when)


# ---------------- 개인 소비 패턴 분석 ----------------
def expense_time(x):
    return parse_date(x.get("created_at")) or parse_date(x.get("purchased_at"))


def build_profile(expenses, records):
    """축적된 소비/결정 기록 → 개인 소비 프로필."""
    now = now_kst()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    recent90 = now - timedelta(days=90)
    recent30 = now - timedelta(days=30)
    month_by_cat, slots, name_count = Counter(), Counter(), Counter()
    cat_amounts, name_display = {}, {}
    recent_items, subs_month = [], []
    late = timed = 0

    for x in expenses:
        cat = x.get("category") or "기타"
        amt = number(x.get("amount"))
        t = expense_time(x)
        cat_amounts.setdefault(cat, []).append(amt)
        if not t:
            continue
        timed += 1
        slots[time_slot(t.hour)] += 1
        if t.hour in LATE_NIGHT:
            late += 1
        if t >= month_start:
            month_by_cat[cat] += amt
            if cat == "구독서비스":
                subs_month.append(x)
        if t >= recent90:
            key = norm_name(x.get("item_name"))
            if key:
                name_count[key] += 1
                name_display.setdefault(key, str(x.get("item_name")))
        if t >= recent30:
            recent_items.append(str(x.get("item_name") or ""))

    decisions = Counter(str(r.get("decision") or "PENDING") for r in records)
    cat_decisions = {}
    for r in records:
        cat = r.get("category") or "기타"
        cat_decisions.setdefault(cat, Counter())[str(r.get("decision") or "PENDING")] += 1
    held_done = [r for r in records
                 if r.get("hold_started_at") and r.get("decision") in ("BUY", "NOT_BUY")]
    hold_drop = sum(1 for r in held_done if r.get("decision") == "NOT_BUY")

    budget = get_setting("cfg_budget", DEFAULT_BUDGET)
    month_spent = sum(month_by_cat.values())
    return {
        "now": now, "budget": budget, "month_spent": month_spent,
        "budget_left": budget - month_spent,
        "month_by_cat": month_by_cat, "cat_amounts": cat_amounts, "slots": slots,
        "late": late, "timed": timed, "late_ratio": late / timed if timed else 0,
        "decisions": decisions, "cat_decisions": cat_decisions,
        "held_done": len(held_done), "hold_drop": hold_drop,
        "repeats": [(name_display[k], c) for k, c in name_count.most_common() if c >= 2],
        "recent_items": recent_items,
        "subs_month": subs_month,
        "subs_total": sum(number(x.get("amount")) for x in subs_month),
        "saved": sum(number(r.get("saved_amount")) for r in records if r.get("decision") == "NOT_BUY"),
        "has_data": bool(expenses or records),
    }


def personal_signals(p, product_name, category, price):
    """구매 직전, 개인 소비 패턴과 이번 상품을 비교한 신호 (level, 문장)."""
    s = []
    left = p["budget_left"]
    if price > 0:
        if left <= 0:
            s.append(("high", f"이번 달 예산을 이미 {money(-left)} 초과했어요."))
        elif price > left:
            s.append(("high", f"사면 이번 달 예산을 {money(price - left)} 초과해요. (남은 예산 {money(left)})"))
        elif price >= left * 0.3:
            s.append(("mid", f"남은 예산 {money(left)} 중 {price / left * 100:.0f}%를 쓰게 돼요."))
    if p["now"].hour in LATE_NIGHT:
        s.append(("mid", "지금은 밤 10시~새벽 5시 심야 시간대예요. 피곤할 때는 충동구매가 늘어나기 쉬워요."))
    if p["timed"] >= 3 and p["late_ratio"] >= 0.3:
        s.append(("info", f"지금까지 구매의 {p['late_ratio'] * 100:.0f}%가 심야에 이뤄졌어요."))
    cat_spent = p["month_by_cat"].get(category, 0)
    if cat_spent > 0:
        share = cat_spent / p["month_spent"] * 100 if p["month_spent"] else 0
        s.append(("info", f"이번 달 {category}에 이미 {money(cat_spent)} 썼어요. (전체 소비의 {share:.0f}%)"))
    amounts = p["cat_amounts"].get(category, [])
    if price > 0 and len(amounts) >= 2:
        avg = sum(amounts) / len(amounts)
        if avg > 0 and price >= avg * 1.5:
            s.append(("mid", f"평소 {category} 구매 평균({money(avg)})보다 {price / avg:.1f}배 비싸요."))
    key = norm_name(product_name)
    if len(key) >= 2:
        for item in p["recent_items"]:
            k2 = norm_name(item)
            if len(k2) >= 2 and (key in k2 or k2 in key):
                s.append(("high", f"최근 30일 안에 비슷한 상품 '{item}'을(를) 이미 구매했어요."))
                break
    cd = p["cat_decisions"].get(category)
    if cd:
        decided = cd["BUY"] + cd["NOT_BUY"]
        if decided >= 2 and cd["NOT_BUY"] / decided >= 0.5:
            s.append(("info", f"{category} 상품은 체크 후 {cd['NOT_BUY'] / decided * 100:.0f}%를 사지 않기로 했어요."))
    if p["held_done"] >= 2 and p["hold_drop"] / p["held_done"] >= 0.4:
        s.append(("info", f"30분 보류했던 상품의 {p['hold_drop'] / p['held_done'] * 100:.0f}%는 결국 사지 않았어요."))
    if category == "구독서비스" and p["subs_month"]:
        s.append(("mid", f"이번 달 이미 정기결제 {len(p['subs_month'])}건({money(p['subs_total'])})을 이용 중이에요."))
    if not s:
        if p["has_data"]:
            s.append(("good", "지금까지의 소비 기록에서 특별히 걸리는 패턴은 없어요."))
        else:
            s.append(("info", "아직 소비 기록이 적어요. 기록이 쌓일수록 체키의 판단이 더 정확해져요."))
    return s


def profile_to_text(p, category, price, signals):
    """AI 프롬프트에 넣을 개인 소비데이터 요약."""
    now = p["now"]
    slot_txt = ", ".join(f"{k} {v}회" for k, v in p["slots"].most_common()) or "기록 없음"
    amounts = p["cat_amounts"].get(category, [])
    avg_txt = money(sum(amounts) / len(amounts)) if amounts else "기록 없음"
    d = p["decisions"]
    hold_rate = f"{p['hold_drop'] / p['held_done'] * 100:.0f}%" if p["held_done"] else "기록 없음"
    rep = ", ".join(f"{n}({c}회)" for n, c in p["repeats"][:5]) or "없음"
    lines = [
        "[사용자 소비 데이터 요약]",
        f"- 현재 시각: {now:%Y-%m-%d %H:%M} ({time_slot(now.hour)}{', 심야' if now.hour in LATE_NIGHT else ''})",
        f"- 확인 중인 상품 가격: {money(price) if price else '미확인'}",
        f"- 이번 달 총 소비: {money(p['month_spent'])} / 월 예산 {money(p['budget'])} (남은 예산 {money(p['budget_left'])})",
        f"- 이번 달 {category} 소비: {money(p['month_by_cat'].get(category, 0))}",
        f"- {category} 평균 구매가: {avg_txt}",
        f"- 구매 시간대 분포: {slot_txt}",
        f"- 체키 결정 기록: 구매 {d['BUY']}회, 보류 중 {d['HOLD']}회, 포기 {d['NOT_BUY']}회, 보류 후 포기율 {hold_rate}",
        f"- 최근 90일 반복 구매: {rep}",
        f"- 이번 달 정기결제(구독서비스): {len(p['subs_month'])}건, {money(p['subs_total'])}",
        "[규칙 기반 신호]",
    ] + [f"- {t}" for _, t in signals]
    return "\n".join(lines)


# ---------------- AI ----------------
def read_url(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    response = requests.get(url, timeout=8,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; CHECKI/1.0)"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    return f"페이지 제목: {title}\n페이지 내용: {soup.get_text(' ', strip=True)[:12000]}"


def parse_field(text, field, default=""):
    match = re.search(rf"(?m)^\s*[-*]*\s*\**{re.escape(field)}\**\s*:\s*\**\s*(.*)$", text, re.I)
    return match.group(1).strip().strip("*").strip() if match else default


def parse_price(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else 0


def call_gemini(contents):
    if gemini is None:
        raise RuntimeError("AI 키가 설정되지 않았어요. Streamlit Secrets의 GEMINI_API_KEY를 확인해주세요.")
    response = gemini.models.generate_content(
        model=MODEL, contents=contents,
        config={"thinking_config": {"thinking_level": "minimal"}},
    )
    raw = getattr(response, "text", None)
    if not raw:
        raise RuntimeError("AI 응답이 비어 있어요.")
    return raw


def analyze_product(product_name, category, image=None, page_text=None, user_price=0, context=""):
    prompt = f"""
너는 소비자를 보호하는 AI 서비스 '체키(CHECKI)'다. 두 가지를 판단한다.

1) 구매 화면 분석
제공된 쇼핑 화면 또는 페이지에서 실제로 확인 가능한 요소만 판단하라.
거짓/과장된 긴급성, 재고 부족 압박, 시간 제한, 사회적 증거,
할인 과장, 가격 혼동, 사전 선택 옵션, 숨겨진 비용,
구독 유도, 해지 방해, 구매 압박 표현을 확인한다.
다크패턴이 확실하지 않다면 단정하지 않는다.

2) 맞춤 판단
아래 사용자 소비 데이터를 함께 고려해 이 사용자가 지금 이 상품을 사는 것이 적절한지 판단하라.
예산 대비 소비, 같은 카테고리 과소비, 반복 구매, 심야 구매, 정기결제 중복, 과거 보류·포기 습관을 근거로 삼는다.
데이터가 부족하면 부족하다고 말하고 일반적인 조언을 한다. 데이터에 없는 사실을 만들지 않는다.
RECOMMEND 기준: BUY=뚜렷한 문제 없음, HOLD=충동구매 신호나 유도 요소가 있음, RECONSIDER=예산 초과·반복 구매 등 뚜렷한 문제.

상품명: {product_name}
카테고리: {category}
사용자가 입력한 가격: {user_price if user_price else '미입력'}

{context}

판매 가격을 확실히 확인할 수 없으면 PRICE: 0 (사용자가 입력한 가격이 있으면 그 값).
위험도는 LOW/MEDIUM/HIGH, 점수는 0~100 (구매 화면의 유도 요소 기준).
아래 형식을 정확히 지키고, 한 줄당 한 항목으로 답하라. 마크다운 기호는 쓰지 마라.
PRODUCT_NAME: 상품명
PRICE: 숫자만
RISK_LEVEL: LOW 또는 MEDIUM 또는 HIGH
RISK_SCORE: 숫자
SUMMARY: 구매 화면에 대한 쉬운 한국어 한 문장
DETECTED: 실제 확인된 요소를 쉼표로 구분. 없으면 없음
ADVICE: 구매 전 확인할 사항 한 문장
RECOMMEND: BUY 또는 HOLD 또는 RECONSIDER
PERSONAL: 사용자 소비 데이터를 근거로 한 맞춤 조언 한두 문장 (숫자 근거 포함, 한 줄로)
"""
    contents = [prompt]
    if page_text:
        contents.append("쇼핑 페이지 정보:\n" + page_text)
    if image is not None:
        contents.append(image)
    raw = call_gemini(contents)

    level = parse_field(raw, "RISK_LEVEL", "MEDIUM").upper()
    level = next((k for k in ("LOW", "MEDIUM", "HIGH") if k in level), "MEDIUM")
    rec = parse_field(raw, "RECOMMEND", "HOLD").upper()
    rec = next((k for k in RECOMMEND if k in rec), "HOLD")
    price = parse_price(parse_field(raw, "PRICE", "0")) or number(user_price)
    return {
        "product_name": parse_field(raw, "PRODUCT_NAME", product_name) or product_name,
        "price": price,
        "risk_level": level,
        "risk_score": min(100, max(0, parse_price(parse_field(raw, "RISK_SCORE", "50")))),
        "summary": parse_field(raw, "SUMMARY", "구매 전 다시 확인해보세요."),
        "detected": parse_field(raw, "DETECTED", "확인 필요"),
        "advice": parse_field(raw, "ADVICE", "필요성과 가격을 확인하세요."),
        "recommend": rec,
        "personal": parse_field(raw, "PERSONAL", "소비 기록이 쌓이면 더 구체적인 조언을 드릴게요."),
        "context": context,
        "raw": raw + "\n\n" + context,
    }


def ai_report(profile):
    stats = profile_to_text(profile, "전체", 0, [])
    top = ", ".join(f"{k} {money(v)}" for k, v in profile["month_by_cat"].most_common(5)) or "없음"
    prompt = f"""
너는 소비 코치 '체키'다. 아래 사용자 소비 데이터를 보고 한국어로 짧은 월간 소비 리포트를 작성하라.
데이터에 있는 사실만 쓰고, 숫자를 근거로 든다. 과장하거나 훈계하지 않는다.
형식(마크다운):
**한 줄 진단:** 문장 하나
- 소비 패턴 2~3개 (카테고리, 시간대, 반복구매·정기결제 등)
- 주의할 점 1개
- 다음 달 실천 제안 1~2개

{stats}
- 이번 달 카테고리별 소비 상위: {top}
- 누적 절약 금액(구매 포기): {money(profile['saved'])}
"""
    return call_gemini([prompt])


# ---------------- UI 컴포넌트 ----------------
def html_block(markup):
    st.markdown(markup, unsafe_allow_html=True)


BRAND = '<div class="brand-row"><b>CHECKI</b><span>CHECK BEFORE YOU BUY</span></div>'
SPARKS = ('<span class="spark" style="right:44%;top:18px">✦</span>'
          '<span class="spark" style="right:10%;top:22px;animation-delay:.8s">✦</span>'
          '<span class="spark" style="right:36%;bottom:26px;animation-delay:1.5s;font-size:10px">✦</span>')
MASCOT_FALLBACK = {"scan": "🤖", "search": "🔍", "wait": "⏳", "chart": "📊"}


def mascot_or_emoji(which):
    img = mascot_img(which, "float")
    return img or f'<div class="em float">{MASCOT_FALLBACK.get(which, "🤖")}</div>'


def app_head(small, title):
    html_block(f'<div class="app-head"><div>{BRAND}<div class="hi">{safe(small)}</div><h2>{title}</h2></div></div>')


def page_hero(small, title, which, say):
    html_block(
        f'<div class="phero">{SPARKS}<div class="tx">{BRAND}<div class="hi">{safe(small)}</div><h2>{title}</h2>'
        f'<div class="say">💬 {safe(say)}</div></div><div class="m">{mascot_or_emoji(which)}</div></div>'
    )


def talk(which, label, text):
    img = mascot_img(which, "float") or f'<div class="em float">{MASCOT_FALLBACK.get(which, "🤖")}</div>'
    html_block(f'<div class="talk"><div class="m">{img}</div>'
               f'<div class="bubble"><small>{safe(label)}</small>{safe(text)}</div></div>')


def sec(title, right="", sub=""):
    sub_html = f"<small>{safe(sub)}</small>" if sub else ""
    right_html = f"<span>{safe(right)}</span>" if right else ""
    html_block(f'<div class="sec"><div><b>{safe(title)}</b>{sub_html}</div>{right_html}</div>')


def step(n, title):
    html_block(f'<div class="step"><i>{n}</i>{safe(title)}</div>')


def empty(icon, text, which=None):
    img = mascot_img(which, "float") if which else ""
    html_block(f'<div class="empty">{img or f"<span class=e>{icon}</span>"}{text}</div>')


def tiles(items):
    cells = "".join(
        f'<div class="tile"><div class="ic {cls}">{icon}</div><b>{safe(v)}</b><span>{safe(k)}</span></div>'
        for icon, k, v, cls in items)
    html_block(f'<div class="tiles">{cells}</div>')


def ring_html(pct, top, bottom, dark=False, color=None):
    p = max(0, min(100, pct))
    style = f"--p:{p:.0f}" + (f";--c:{color}" if color else "")
    return (f'<div class="ring{" dark" if dark else ""}" style="{style}"><div class="track"></div>'
            f'<div class="val"><b>{safe(top)}</b><small>{safe(bottom)}</small></div></div>')


def list_html(rows):
    """rows: (icon, title, sub, right_html)"""
    return '<div class="list">' + "".join(
        f'<div class="lrow"><div class="ic">{icon}</div><div class="tx"><b>{safe(t)}</b>'
        f'<span>{safe(s)}</span></div><div class="rt">{r}</div></div>'
        for icon, t, s, r in rows) + "</div>"


def chips_html(signals):
    icons = {"high": "⚠️", "mid": "💡", "info": "📊", "good": "✅"}
    return '<div class="chips">' + "".join(
        f'<div class="chip {lv}">{icons.get(lv, "•")} {safe(t)}</div>' for lv, t in signals) + "</div>"


def bars_html(items, fmt=money):
    if not items:
        return ""
    mx = max(v for _, v in items) or 1
    rows = "".join(
        f'<div class="bar-row"><div class="lb">{CAT_ICON.get(k, "")} {safe(k)}</div><div class="tr">'
        f'<div class="fl" style="width:{v / mx * 100:.1f}%"></div></div>'
        f'<div class="vl">{fmt(v)}</div></div>' for k, v in items)
    return f'<div class="bars">{rows}</div>'


def vbars_html(items, highlight=()):
    mx = max([v for _, v in items] + [1])
    cols = "".join(
        f'<div class="vbar"><small>{v}</small>'
        f'<div class="col{" zero" if v == 0 else (" late" if k in highlight else "")}" '
        f'style="height:{max(4, v / mx * 86):.0f}%"></div><span>{safe(k)}</span></div>'
        for k, v in items)
    return f'<div class="bars"><div class="vbars">{cols}</div></div>'


def budget_card(p):
    budget, spent = p["budget"], p["month_spent"]
    pct = spent / budget * 100 if budget else 0
    left = budget - spent
    color = "#E25555" if pct > 100 else ("#E9A21B" if pct > 80 else "#1689F8")
    left_txt = f"남은 예산 {money(left)}" if left >= 0 else f"{money(-left)} 초과"
    html_block(
        f'<div class="card"><div class="budget">{ring_html(pct, f"{pct:.0f}%", "사용", dark=True, color=color)}'
        f'<div class="info"><div class="kicker">{p["now"].month}월 예산</div><b>{money(spent)}</b>'
        f'<div class="meta">/ {money(budget)} · {left_txt}</div></div></div></div>'
    )


def piggy_card(records):
    completed = [r for r in records if r.get("decision") == "NOT_BUY"]
    total = sum(number(r.get("saved_amount")) for r in completed)
    goal = max(1, get_setting("cfg_goal", DEFAULT_GOAL))
    pct = min(100, total / goal * 100)
    html_block(
        f'<div class="pig"><div class="emoji">🐷</div><div class="body">'
        f'<div class="sub">체키 저금통 · 포기 {len(completed)}건</div>'
        f'<div class="amount">{money(total)}</div>'
        f'<div class="progress-bg"><div class="progress-fill" style="width:{pct:.1f}%"></div></div>'
        f'<div class="sub">목표 {money(goal)} · {pct:.0f}% 달성</div></div></div>'
    )
    return goal


def record_row(r):
    decision = str(r.get("decision") or "PENDING")
    created = parse_date(r.get("created_at"))
    when = f"{created:%m.%d %H:%M}" if created else ""
    cat = r.get("category") or "기타"
    sub = " · ".join(x for x in [money(r.get("product_price")), f"위험 {r.get('risk_level') or '-'}", when] if x)
    summary = r.get("one_line_summary")
    html_block(
        f'<div class="rcard"><div class="lrow"><div class="ic">{CAT_ICON.get(cat, "🛍️")}</div>'
        f'<div class="tx"><b>{safe(r.get("product_name") or "상품")}</b><span>{safe(sub)}</span></div>'
        f'<div class="rt"><span class="badge {safe(decision)}">{DECISION_BADGE.get(decision, safe(decision))}</span></div></div>'
        + (f'<div class="rsum">{safe(summary)}</div>' if summary else "") + "</div>"
    )


def _hold_timer_body(until_iso):
    until = parse_date(until_iso)
    secs = max(0, int((until - now_kst()).total_seconds())) if until else 0
    if secs <= 0:
        st.rerun()
    html_block(
        f'<div class="hold"><small>⏱️ 생각하는 중</small>'
        f'<div class="clock">{secs // 60:02d}:{secs % 60:02d}</div>'
        f'<small>기다리는 중에도 아래에서 바로 결정할 수 있어요.</small></div>'
    )


# Streamlit 1.37+ : 타이머만 1초마다 자동 갱신 / 구버전: 새로고침 버튼
try:
    hold_timer = st.fragment(run_every=1)(_hold_timer_body)
    LIVE_TIMER = True
except Exception:
    hold_timer = _hold_timer_body
    LIVE_TIMER = False


# =============================================================
# 화면
# =============================================================
expenses, records = get_expenses(), get_records()
profile = build_profile(expenses, records)

if "pending_nav" in ss:
    ss["nav"] = ss.pop("pending_nav")
if ss.get("nav") not in NAV:
    ss["nav"] = ss.get("last_nav") if ss.get("last_nav") in NAV else "홈"
if hasattr(st, "segmented_control"):
    nav_kwargs = dict(key="nav", label_visibility="collapsed",
                      format_func=lambda x: f"{NAV_ICON.get(x, '')} {x}")
    try:
        page = st.segmented_control("메뉴", NAV, width="stretch", **nav_kwargs)
    except Exception:  # width 옵션이 없는 구버전
        page = st.segmented_control("메뉴", NAV, **nav_kwargs)
    if page not in NAV:  # 선택된 탭을 다시 눌러 해제된 경우 → 이전 탭 유지
        go(ss.get("last_nav", "홈"))
        st.rerun()
else:
    page = st.radio("메뉴", NAV, key="nav", horizontal=True, label_visibility="collapsed",
                    format_func=lambda x: f"{NAV_ICON.get(x, '')} {x}")
ss["last_nav"] = page
p = profile

# ---------------- 홈 ----------------
if page == "홈":
    app_head(f"{greeting(p['now'].hour)} 👋", "오늘도 <em>똑똑한 소비</em> 해요")
    budget, spent = p["budget"], p["month_spent"]
    pct = spent / budget * 100 if budget else 0
    left = p["budget_left"]
    html_block(
        f'<div class="mhero">{SPARKS}<div class="tx">'
        f'<span class="pill">{p["now"].month}월 예산 · 체키와 함께</span>'
        f'<div class="label">{"남은 예산" if left >= 0 else "예산 초과"}</div>'
        f'<div class="big">{money(abs(left))}</div>'
        f'<div class="bar"><i style="width:{min(100, pct):.0f}%"></i></div>'
        f'<div class="sub">{money(budget)} 중 {pct:.0f}% 사용</div></div>'
        f'<div class="m">{mascot_or_emoji("scan")}</div></div>'
    )

    if st.button("🔎 지금 구매체크 시작하기", type="primary", use_container_width=True, key="home_cta"):
        go("체크")
        st.rerun()

    tiles([
        ("💳", "이번 달 소비", money(p["month_spent"]), "blue"),
        ("🐷", "아낀 금액", money(p["saved"]), "green"),
        ("⏱️", "보류 중", f"{p['decisions']['HOLD']}건", "amber"),
    ])
    ready = [r for r in records if r.get("decision") == "HOLD"
             and (parse_date(r.get("hold_until")) or now_kst()) <= now_kst()]
    if ready:
        tip = (f"30분이 지난 보류 상품이 {len(ready)}개 있어요. 지금도 꼭 필요한지 같이 생각해봐요!", "wait")
    elif p["now"].hour in LATE_NIGHT:
        tip = ("지금은 심야 시간이에요. 피곤할 땐 충동구매가 늘어나니 내일 다시 볼까요?", "wait")
    elif pct >= 80:
        tip = (f"이번 달 예산을 {pct:.0f}% 썼어요. 남은 기간은 조금만 아껴봐요!", "chart")
    elif p["saved"] > 0:
        tip = (f"지금까지 {money(p['saved'])}을 아꼈어요. 정말 멋져요!", "chart")
    else:
        tip = ("사기 전에 30분만 기다려도 충동구매가 확 줄어들어요. 저랑 같이 체크해봐요!", "search")
    talk(tip[1], "체키의 한마디", tip[0])
    if ready:
        if st.button("결정하러 가기", use_container_width=True, key="home_ready"):
            go("기록")
            st.rerun()

    sec("체키는 이렇게 판단해요", "옆으로 넘기기 →")
    flow = [
        ("소비 데이터 수집", "상품 가격·카테고리, 구매 금액과 시간을 기록"),
        ("분류·축적", "카테고리·시간대·결정 결과별로 정리"),
        ("소비 패턴 분석", "예산 대비 소비, 반복·심야 구매 파악"),
        ("맞춤 판단", "유도 요소 + 내 패턴으로 지금 사도 될지 안내"),
        ("결과 반영·리포트", "선택 결과가 다음 판단과 리포트에 반영"),
    ]
    html_block('<div class="hscroll">' + "".join(
        f'<div class="hcard{" on" if i == 4 else ""}"><div class="n">{i}</div><b>{t}</b><p>{d}</p></div>'
        for i, (t, d) in enumerate(flow, 1)) + "</div>")

    sec("최근 체키", f"{len(records)}건" if records else "")
    if records:
        rows = []
        for r in records[:3]:
            dcs = str(r.get("decision") or "PENDING")
            rows.append((CAT_ICON.get(r.get("category"), "🛍️"), r.get("product_name") or "상품",
                         f"{r.get('category') or '기타'} · 위험 {r.get('risk_level') or '-'}",
                         f'<span class="badge {safe(dcs)}">{DECISION_BADGE.get(dcs, safe(dcs))}</span>'))
        html_block(list_html(rows))
    else:
        empty("🔎", "아직 체크한 상품이 없어요.<br>첫 구매체크를 시작해보세요.", "search")

# ---------------- 체크 ----------------
elif page == "체크":
    page_hero("구매 전 한 번 더", "구매 <em>체크</em>하기", "search",
              "화면을 보여주면 숨은 구매 유도를 찾아낼게요!")

    step(1, "상품 정보")
    product_name = st.text_input("상품명", placeholder="예: 무선 이어폰", key="in_name")
    c1, c2 = st.columns(2)
    with c1:
        category = st.selectbox("카테고리", CATEGORIES, key="in_cat")
    with c2:
        user_price = st.number_input("가격 (선택)", min_value=0, step=1000, value=0, key="in_price",
                                     help="화면에서 가격을 못 읽을 때 사용해요.")

    step(2, "쇼핑 화면")
    tab_shot, tab_link = st.tabs(["📸 스크린샷", "🔗 상품 링크"])
    image = None
    with tab_shot:
        uploaded_file = st.file_uploader("쇼핑 화면 업로드", type=["png", "jpg", "jpeg", "webp"],
                                         key="in_file", label_visibility="collapsed")
        if uploaded_file:
            try:
                image = Image.open(uploaded_file)
                preview_image(image)
            except Exception:
                st.warning("이미지 파일을 열지 못했어요.")
    with tab_link:
        product_url = st.text_input("상품 링크", placeholder="https://...", key="in_url",
                                    label_visibility="collapsed")
        st.caption("스크린샷이 함께 있으면 스크린샷을 우선 분석해요.")

    cat_spent = p["month_by_cat"].get(category, 0)
    html_block('<div class="data-chip">'
               f'<span>{CAT_ICON.get(category, "")} 이번 달 {safe(category)} {money(cat_spent)}</span>'
               f'<span>💰 남은 예산 {money(p["budget_left"])}</span>'
               f'<span>🕒 지금 {time_slot(p["now"].hour)}</span></div>')

    if st.button("체키로 분석하기", type="primary", use_container_width=True, key="analyze"):
        url = (product_url or "").strip()
        if not product_name.strip():
            st.warning("상품명을 입력해주세요.")
        elif image is None and not url:
            st.warning("스크린샷을 올리거나 상품 링크를 넣어주세요.")
        else:
            try:
                page_text = None
                if image is None and url:
                    with st.spinner("상품 페이지를 확인하고 있어요..."):
                        page_text = read_url(url)
                pre_signals = personal_signals(p, product_name, category, number(user_price))
                context = profile_to_text(p, category, number(user_price), pre_signals)
                with st.spinner("구매 화면과 내 소비 패턴을 함께 분석하고 있어요..."):
                    result = analyze_product(product_name.strip(), category, image, page_text,
                                             number(user_price), context)
                result["signals"] = personal_signals(p, result["product_name"],
                                                     category, number(result["price"]))
                ss["latest_analysis"] = result
                ss["latest_category"] = category
                ss["latest_record"] = insert_record(result, category, "PENDING")
                ss.pop("purchase_action", None)
            except Exception as exc:
                st.error(f"분석을 완료하지 못했어요: {exc}")
                if image is None:
                    st.info("상품 페이지 접근이 막힌 경우 스크린샷으로 분석해주세요.")

    result = ss.get("latest_analysis")
    if result:
        level = result["risk_level"]
        cls = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high"}[level]
        name = {"LOW": "낮음", "MEDIUM": "주의", "HIGH": "높음"}[level]
        color = {"LOW": "#22B07D", "MEDIUM": "#E9A21B", "HIGH": "#E25555"}[level]
        score = number(result["risk_score"])
        parts = [x.strip() for x in re.split(r"[,，·/]", result["detected"]) if x.strip()]
        no_issue = not parts or parts[0] in ("없음", "확인 필요")
        tags = "".join(f'<span class="tag{"" if no_issue else " warn"}">{safe(x)}</span>'
                       for x in (parts or ["없음"]))
        sec("분석 결과")
        html_block(
            f'<div class="card"><div class="kicker">STEP 1 · 구매 화면 분석</div>'
            f'<div class="result-head">{ring_html(score, str(score), "/ 100", dark=True, color=color)}'
            f'<div><span class="level {cls}">구매 유도 위험 {name}</span>'
            f'<h3>{safe(result["summary"])}</h3></div></div>'
            f'<dl class="kv"><dt>발견된 유도 요소</dt><dd><div class="tags">{tags}</div></dd>'
            f'<dt>구매 전 확인할 점</dt><dd>{safe(result["advice"])}</dd></dl></div>'
        )
        rec = result.get("recommend", "HOLD")
        icon, rec_title = RECOMMEND.get(rec, RECOMMEND["HOLD"])
        rec_img = mascot_img({"BUY": "scan", "HOLD": "wait", "RECONSIDER": "search"}.get(rec, "wait"), "mimg float")
        rec_visual = rec_img or f'<div class="icon">{icon}</div>'
        price_txt = (f"확인된 가격 {money(result['price'])}" if number(result["price"]) > 0
                     else "가격 미확인 · 포기 시 절약 금액 0원으로 기록")
        html_block(
            f'<div class="card"><div class="kicker">STEP 2 · 나에게 맞춘 판단</div>'
            f'<div class="rec {safe(rec)}">{rec_visual}<div><b>{rec_title}</b>'
            f'<span>{safe(result.get("personal"))}</span></div></div>'
            f'{chips_html(result.get("signals", []))}'
            f'<div class="meta" style="margin-top:10px">💳 {safe(price_txt)}</div></div>'
        )
        if st.toggle("🔍 AI가 참고한 내 소비 데이터 보기", key="show_ctx"):
            html_block(f'<div class="ctx">{safe(result.get("context") or "데이터 없음")}</div>')

        sec("어떻게 할까요?", sub="선택 결과는 다음 분석과 리포트에 반영돼요.")
        if ss.get("purchase_action") == "BUY":
            amount = st.number_input("실제로 결제할 금액", min_value=0, step=1000,
                                     value=number(result["price"]), key="latest_buy_amount")
            if st.button("구매 기록 저장", type="primary", use_container_width=True, key="buy_save"):
                if finalize_latest("BUY"):
                    add_expense(ss.get("latest_category", "기타"), result["product_name"], amount)
                    clear_latest()
                    ss["notice"] = "구매 기록을 저장했어요."
                    go("리포트")
                    st.rerun()
            if st.button("이전 선택으로 돌아가기", use_container_width=True, key="buy_back"):
                ss.pop("purchase_action", None)
                st.rerun()
        else:
            if st.button("⏱️ 30분만 생각해볼게요", use_container_width=True, key="act_hold",
                         type="primary" if rec in ("HOLD", "RECONSIDER") else "secondary"):
                if finalize_latest("HOLD"):
                    clear_latest()
                    ss["notice"] = "30분 보류를 시작했어요."
                    go("기록")
                    st.rerun()
            b1, b2 = st.columns(2)
            with b1:
                if st.button("🙅 사지 않기", use_container_width=True, key="act_no"):
                    saved = number(result["price"])
                    if finalize_latest("NOT_BUY", saved):
                        clear_latest()
                        ss["notice"] = f"{money(saved)}을(를) 저금통에 담았어요."
                        go("기록")
                        st.rerun()
            with b2:
                if st.button("🛒 구매하기", use_container_width=True, key="act_buy",
                             type="primary" if rec == "BUY" else "secondary"):
                    ss["purchase_action"] = "BUY"
                    st.rerun()

# ---------------- 리포트 ----------------
elif page == "리포트":
    if p["month_by_cat"]:
        top_cat, top_amt = p["month_by_cat"].most_common(1)[0]
        say = f"이번 달엔 {top_cat}에 가장 많이 썼어요 ({money(top_amt)})"
    else:
        say = "기록이 쌓이면 소비 습관을 분석해드릴게요!"
    page_hero("쌓인 기록으로 분석한", "나의 <em>소비 리포트</em>", "chart", say)

    if not expenses:
        empty("📊", "아직 소비 기록이 없어요.<br>체험용 샘플로 리포트를 미리 볼 수 있어요.", "chart")
        if st.button("✨ 체험용 샘플 소비 넣기", type="primary", use_container_width=True, key="sample"):
            add_sample_data()
            ss["notice"] = "샘플 소비 10건을 넣었어요."
            st.rerun()

    budget_card(p)
    if st.toggle("월 예산 바꾸기", key="budget_toggle"):
        new_budget = st.number_input("월 예산 (원)", min_value=10000, step=50000,
                                     value=int(p["budget"]), key="budget_input")
        if st.button("예산 적용", key="budget_save", use_container_width=True):
            set_setting("cfg_budget", new_budget)
            ss["notice"] = "월 예산을 바꿨어요."
            st.rerun()

    d = p["decisions"]
    tiles([
        ("🛒", "구매", f"{d['BUY']}회", "blue"),
        ("⏱️", "보류 중", f"{d['HOLD']}회", "amber"),
        ("🙅", "포기", f"{d['NOT_BUY']}회", "green"),
    ])
    if p["held_done"]:
        st.caption(f"30분 보류 후 결국 사지 않은 비율 {p['hold_drop'] / p['held_done'] * 100:.0f}% "
                   f"({p['hold_drop']}/{p['held_done']}건)")

    sec("카테고리별 소비", "이번 달")
    if p["month_by_cat"]:
        html_block(bars_html(p["month_by_cat"].most_common()))
    else:
        empty("🗂️", "이번 달 소비 기록이 없어요.")

    sec("구매 시간대", f"심야 {p['late_ratio'] * 100:.0f}%" if p["timed"] else "")
    if p["timed"]:
        slot_items = [(n, p["slots"].get(n, 0)) for n, _, _ in TIME_SLOTS]
        html_block(vbars_html(slot_items, highlight=("새벽", "밤")))
        st.caption("보라색은 심야(밤 10시~새벽 5시) 구매예요.")
    else:
        empty("🕒", "구매 시간 기록이 없어요.")

    sec("반복 구매 · 정기결제")
    items = [("mid", f"최근 90일 '{n}' {c}회 구매") for n, c in p["repeats"][:5]]
    if p["subs_month"]:
        items.append(("info", f"이번 달 정기결제 {len(p['subs_month'])}건 · {money(p['subs_total'])}"))
    html_block(chips_html(items or [("good", "반복 구매나 정기결제 기록이 없어요.")]))

    sec("AI 소비 리포트", "✨ AI")
    if st.button("리포트 생성하기", type="primary", use_container_width=True,
                 disabled=not expenses, key="report_btn"):
        try:
            with st.spinner("소비 패턴을 정리하고 있어요..."):
                ss["ai_report"] = ai_report(p)
        except Exception as exc:
            st.error(f"리포트를 만들지 못했어요: {exc}")
    if ss.get("ai_report"):
        with st.container(border=True):
            st.markdown(ss["ai_report"])

    sec("체키 저금통")
    goal = piggy_card(records)
    if st.toggle("🎯 저금 목표 바꾸기", key="goal_toggle"):
        new_goal = st.number_input("목표 금액 (원)", min_value=1000, step=10000,
                                   value=int(goal), key="goal_input")
        if st.button("목표 적용", key="goal_save", use_container_width=True):
            set_setting("cfg_goal", new_goal)
            ss["notice"] = "저금 목표를 바꿨어요."
            st.rerun()

    sec("최근 소비", f"{len(expenses)}건" if expenses else "")
    if st.toggle("➕ 소비 직접 기록하기", key="add_toggle"):
        e_cat = st.selectbox("카테고리", CATEGORIES, key="e_cat")
        e_name = st.text_input("항목", key="e_name", placeholder="예: 점심, 넷플릭스")
        e_amt = st.number_input("금액 (원)", min_value=0, step=1000, key="e_amt")
        if st.button("기록 추가", key="e_save", use_container_width=True):
            if e_name.strip() and e_amt > 0:
                add_expense(e_cat, e_name.strip(), e_amt)
                ss["notice"] = "소비를 기록했어요."
                st.rerun()
            else:
                st.warning("항목과 금액을 입력해주세요.")
    if expenses:
        rows = []
        for x in expenses[:10]:
            t = expense_time(x)
            cat = x.get("category") or "기타"
            rows.append((CAT_ICON.get(cat, "🛍️"), x.get("item_name") or "상품",
                         f"{cat}{f' · {t:%m.%d %H:%M}' if t else ''}",
                         f'<b>-{money(x.get("amount"))}</b>'))
        html_block(list_html(rows))

# ---------------- 기록 ----------------
elif page == "기록":
    holds = p["decisions"]["HOLD"]
    say = (f"보류 중인 상품이 {holds}개 있어요. 조금만 더 참아봐요!" if holds
           else "사지 않은 만큼 저금통이 채워져요 🐷")
    page_hero("보류 중인 상품과 결정 내역", "나의 <em>체키 기록</em>", "wait", say)
    piggy_card(records)
    if not records:
        empty("🗂️", "아직 체키 기록이 없어요.<br>구매체크를 먼저 해보세요.", "wait")
        if st.button("🔎 구매체크 하러 가기", type="primary", use_container_width=True, key="rec_cta"):
            go("체크")
            st.rerun()
    else:
        order = {"HOLD": 0, "PENDING": 1}
        shown = sorted(records[:30], key=lambda r: order.get(r.get("decision"), 2))
        for idx, record in enumerate(shown):
            rid = record.get("id")
            kid = rid if rid else f"i{idx}"
            decision = str(record.get("decision") or "PENDING")
            product = str(record.get("product_name") or "상품")
            price = number(record.get("product_price"))
            record_row(record)

            if decision == "HOLD":
                until = parse_date(record.get("hold_until"))
                seconds = max(0, int((until - now_kst()).total_seconds())) if until else 0
                if seconds > 0:
                    hold_timer(record.get("hold_until"))
                    if not LIVE_TIMER and st.button("남은 시간 새로고침", key=f"refresh_{kid}"):
                        st.rerun()
                else:
                    html_block('<div class="notice">⏰ 30분이 지났어요. 지금도 꼭 필요한가요?</div>')
                # 타이머 진행 중에도 언제든 결정 가능
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🙅 안 살래요", key=f"no_{kid}", use_container_width=True,
                                 type="primary" if seconds > 0 else "secondary"):
                        if update_record(rid, "NOT_BUY", price):
                            ss.pop("buy_record", None)
                            ss["notice"] = f"{money(price)}을(를) 저금통에 담았어요."
                            st.rerun()
                with col2:
                    if st.button("🛒 살게요", key=f"yes_{kid}", use_container_width=True):
                        ss["buy_record"] = kid
                if ss.get("buy_record") == kid:
                    actual = st.number_input("실제 결제 금액", min_value=0, step=1000,
                                             value=price, key=f"amount_{kid}")
                    if st.button("구매 내역 저장", key=f"save_{kid}", type="primary",
                                 use_container_width=True):
                        if update_record(rid, "BUY"):
                            add_expense(str(record.get("category") or "기타"), product, actual)
                            ss.pop("buy_record", None)
                            ss["notice"] = "구매 내역을 저장했어요."
                            st.rerun()
            elif decision == "NOT_BUY":
                st.caption(f"💚 {money(record.get('saved_amount'))} 절약")
            elif decision == "PENDING":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⏱️ 30분 보류", key=f"pending_hold_{kid}", use_container_width=True):
                        if update_record(rid, "HOLD"):
                            st.rerun()
                with col2:
                    if st.button("🙅 사지 않기", key=f"pending_no_{kid}", use_container_width=True):
                        if update_record(rid, "NOT_BUY", price):
                            st.rerun()

if ss.get("notice"):
    st.toast(ss.pop("notice"))
