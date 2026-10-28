import streamlit as st
from google import genai
from PIL import Image, ImageDraw, ImageFont
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
# CHECKI v5 (참가신청서 기준: 탐지 → 검증 → 개인화 → 판단 지원)
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
CAT_SHARE = {"패션/의류": 20, "뷰티": 8, "식품": 30, "생활용품": 10, "전자기기": 10,
             "가구/인테리어": 5, "취미/여가": 7, "구독서비스": 5, "기타": 5}
# 공정거래위원회·한국소비자원 다크패턴 4유형
PATTERN_TYPES = {
    "편취형": ("#E25555", "소비자도 모르게 비용을 더 내게 해요 (무료체험 후 유료 전환, 추가 옵션 끼워팔기)"),
    "오도형": ("#E9A21B", "착각을 일으켜 다른 선택을 하게 해요 (가짜 후기, 부풀린 정가로 큰 할인처럼 보이기)"),
    "방해형": ("#7B61FF", "거절·해지를 어렵게 만들어요 (작은 해지 버튼, 여러 단계 해지 절차)"),
    "압박형": ("#1689F8", "판단 시간을 줄여 서두르게 해요 (마감 임박, 남은 수량, 타임세일)"),
}
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
.st-key-nav [data-testid="stButtonGroup"] div:has(> button){display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr));width:100%!important;
  background:#FFFFFF;border:1px solid var(--line);border-radius:22px;padding:5px;gap:4px;box-shadow:0 8px 24px #1C5FA41F}
.st-key-nav [data-testid="stButtonGroup"] button{width:100%!important;min-width:0!important;border:0!important;border-radius:17px!important;
  min-height:48px;padding:0 4px!important;background:transparent!important;color:var(--muted)!important;box-shadow:none!important}
.st-key-nav [data-testid="stButtonGroup"] button *{white-space:nowrap!important;overflow:visible!important;text-overflow:clip!important;max-width:none!important}
.st-key-nav [data-testid="stButtonGroup"] button p{font-size:13px!important;font-weight:800!important;color:inherit!important;margin:0!important}
.st-key-nav [data-testid="stButtonGroup"] button[kind*="Active"],.st-key-nav [data-testid="stButtonGroup"] button[aria-checked="true"],
.st-key-nav [data-testid="stButtonGroup"] button[aria-pressed="true"]{background:linear-gradient(135deg,var(--blue2),var(--blue))!important;
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
.say{display:flex;align-items:flex-start;gap:7px;width:fit-content;max-width:100%;margin-top:12px;background:#fff;
  border:1px solid var(--line);border-radius:18px 18px 18px 6px;padding:10px 13px;box-shadow:0 6px 14px #1C5FA414;animation:pop .5s ease-out;
  text-align:left;word-break:keep-all;overflow-wrap:anywhere}
.say .si{flex:0 0 auto;font-size:14px;line-height:1.5}
.say .st{font-size:12.5px;font-weight:700;color:#35506A;line-height:1.5}
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
/* 기간 선택 버튼그룹 */
.st-key-period,.st-key-period > div,.st-key-period [data-testid="stButtonGroup"]{width:100%!important}
.st-key-period [data-testid="stButtonGroup"] div:has(> button){display:flex!important;gap:4px;background:#E6EFF8;border-radius:16px;padding:4px;width:100%!important}
.st-key-period [data-testid="stButtonGroup"] button{flex:1 1 0!important;min-height:38px;border:0!important;border-radius:12px!important;
  background:transparent!important;color:var(--muted)!important;box-shadow:none!important}
.st-key-period [data-testid="stButtonGroup"] button p{font-weight:800!important;font-size:13px!important;color:inherit!important}
.st-key-period [data-testid="stButtonGroup"] button[kind*="Active"],.st-key-period [data-testid="stButtonGroup"] button[aria-checked="true"],
.st-key-period [data-testid="stButtonGroup"] button[aria-pressed="true"]{background:#fff!important;color:var(--blue)!important;box-shadow:0 4px 10px #1C5FA41A!important}
.mhero h1{color:#fff;font-size:24px;font-weight:900;letter-spacing:-1px;line-height:1.32;margin:10px 0 6px;padding:0}
.mhero p{color:#DDEEFF;font-size:12.5px;line-height:1.55;margin:0}
/* 분석 로딩 */
.loader{background:var(--card);border:1px solid var(--line);border-radius:26px;padding:20px;text-align:center;box-shadow:0 12px 30px #1C5FA41A;margin:10px 0}
.loader img{width:112px;height:112px;object-fit:contain}
.loader .em{font-size:64px}
.loader h3{font-size:17px;font-weight:900;color:var(--navy);margin:6px 0 4px;padding:0}
.loader p{font-size:12.5px;color:var(--muted);margin:0 0 12px;line-height:1.5}
.lbar{height:8px;background:#E6EEF6;border-radius:10px;overflow:hidden;margin:6px 0 14px}
.lbar i{display:block;height:100%;background:linear-gradient(90deg,var(--blue2),var(--blue));border-radius:10px}
.lsteps{text-align:left;display:flex;flex-direction:column;gap:8px}
.lsteps div{font-size:13px;font-weight:700;color:#A9B8C7;display:flex;gap:8px;align-items:center}
.lsteps div.done{color:var(--navy)}.lsteps div.now{color:var(--blue)}
.lsteps b{width:20px;height:20px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:11px;background:#E6EEF6;color:#fff}
.lsteps .done b{background:var(--blue)}.lsteps .now b{background:#fff;border:2px dashed var(--blue)}
/* 결과: 체키가 확인했어요 */
.done-head{display:flex;gap:10px;align-items:center;border-radius:26px;padding:14px;margin:14px 0 8px;
  background:linear-gradient(145deg,#FFFFFF,#E5F1FF);border:1px solid #D9E9F8;box-shadow:0 12px 30px #1C5FA41A}
.done-head .m{flex:0 0 78px;text-align:center}
.done-head .m img{width:78px;height:78px;object-fit:contain}
.done-head .m .em{font-size:48px}
.done-head .tx{flex:1;min-width:0}
.done-head h3{font-size:18px;font-weight:900;color:var(--navy);margin:0;padding:0;line-height:1.3}
.done-head p{font-size:11.5px;color:var(--muted);margin:2px 0 0;line-height:1.45}
.done-head .ring{width:78px;height:78px;flex:0 0 78px}
.done-head .ring .val b{font-size:18px}.done-head .ring .val small{font-size:8.5px}
.need{display:inline-block;margin-top:6px;padding:4px 10px;border-radius:20px;font-size:11.5px;font-weight:850}
.need.hi{background:#FFE6E6;color:#C23B3B}.need.mid{background:#FFF4D6;color:#A86E00}.need.lo{background:#E3F7EE;color:#14855A}
.ccard{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:15px;margin:9px 0;box-shadow:0 6px 18px #1C5FA40D}
.ccard .hd{display:flex;gap:10px;align-items:center}
.ccard .ic{width:38px;height:38px;border-radius:13px;display:flex;align-items:center;justify-content:center;font-size:18px;flex:0 0 38px}
.ccard .ic.red{background:#FFE9E9}.ccard .ic.blue{background:#E6F2FF}.ccard .ic.violet{background:#EFEAFF}.ccard .ic.green{background:#E2F7EF}
.ccard .hd b{font-size:14.5px;font-weight:850;color:var(--navy);display:block}
.ccard .hd span{font-size:11.5px;color:var(--muted)}
.ccard .bd{margin-top:10px;font-size:13px;line-height:1.6;color:#3D566C}
.ccard .bd .tags{margin-top:8px}
.pat{border:1px solid var(--line);border-radius:16px;padding:10px 12px;margin-top:8px;background:var(--surface)}
.pat .t{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.ptype{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:850;color:#fff}
.pname{font-size:13px;font-weight:800;color:var(--navy)}
.pnum{width:20px;height:20px;border-radius:50%;background:#E25555;color:#fff;font-size:11px;font-weight:900;display:inline-flex;align-items:center;justify-content:center}
.pat q{display:block;font-size:12.5px;color:#B03C3C;font-weight:700;margin-top:6px}
.pat p{font-size:12px;color:var(--muted);margin:4px 0 0;line-height:1.5}
.legend4{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:4px 0 8px}
.legend4 div{font-size:11.5px;color:#4A6378;background:#fff;border:1px solid var(--line);border-radius:14px;padding:9px 10px;line-height:1.45}
.legend4 b{display:block;font-size:13px;margin-bottom:2px}
.annot{text-align:center;margin:4px 0 8px}
.annot img{max-width:100%;max-height:440px;border-radius:16px;border:1px solid var(--line);box-shadow:0 8px 22px #1C5FA41F}
/* 카테고리 예산 */
.catbig{display:flex;align-items:center;gap:12px}
.catbig .ic{width:46px;height:46px;border-radius:16px;background:var(--soft);display:flex;align-items:center;justify-content:center;font-size:22px;flex:0 0 46px}
.catbig .tx{flex:1;min-width:0}.catbig .tx b{font-size:15px;color:var(--navy);display:block}.catbig .tx span{font-size:12px;color:var(--muted)}
.catbig .pc{font-size:24px;font-weight:900;color:var(--blue)}
.cbrow{padding:11px 0;border-bottom:1px solid #EEF3F8}.cbrow:last-child{border-bottom:0}
.cbrow .top{display:flex;align-items:center;gap:10px;font-size:13px}
.cbrow .top .ic{font-size:16px;width:32px;height:32px;border-radius:11px;background:var(--soft);display:flex;align-items:center;justify-content:center;flex:0 0 32px}
.cbrow .top b{flex:1;color:var(--navy);font-weight:800;white-space:nowrap}
.cbrow .top span{color:var(--muted);font-size:11.5px;white-space:nowrap}
.cbrow .top em{font-style:normal;font-weight:900;color:var(--navy);min-width:38px;text-align:right}
.cbrow .pb{height:7px;background:#EDF3F8;border-radius:10px;overflow:hidden;margin:7px 0 0 42px}
.cbrow .pb i{display:block;height:100%;border-radius:10px;background:linear-gradient(90deg,var(--blue2),var(--blue))}
.cbrow .pb i.warn{background:linear-gradient(90deg,#FFC06B,#E9A21B)}.cbrow .pb i.over{background:linear-gradient(90deg,#FF9A7A,#E25555)}
.donut-row{display:flex;align-items:center;gap:18px}
.donut-row .ring{width:118px;height:118px;flex:0 0 118px}
.lg{display:flex;flex-direction:column;gap:10px;font-size:12px}
.lg div{display:flex;gap:8px;align-items:flex-start;color:var(--muted)}
.lg i{width:10px;height:10px;border-radius:50%;margin-top:4px;flex:0 0 10px}
.lg b{display:block;color:var(--navy);font-size:15px}
.vbar .col.hl{background:linear-gradient(180deg,#3E9BFF,#0F6BDB)}
.dday{display:inline-block;padding:3px 9px;border-radius:20px;font-size:11px;font-weight:850;background:#EFEAFF;color:#5B45D6}
.dday.soon{background:#FFE6E6;color:#C23B3B}
.premium{display:inline-flex;gap:6px;align-items:center;background:linear-gradient(120deg,#1B2B44,#3B4F72);color:#FFE7A3;border-radius:20px;padding:5px 12px;font-size:11.5px;font-weight:850;margin:8px 0 0}
/* 가상 저축계좌 */
.acct{position:relative;overflow:hidden;border-radius:26px;padding:18px;color:#fff;margin:4px 0 8px;min-height:150px;
  background:linear-gradient(135deg,#21C3A0 0%,#13A6B8 50%,#1689F8 100%);box-shadow:0 16px 32px #13A6B83D}
.acct:after{content:"";position:absolute;right:-50px;top:-50px;width:180px;height:180px;border-radius:50%;background:#FFFFFF1A}
.acct .no{font-size:11px;color:#DFFBF4;font-weight:700;letter-spacing:.4px;position:relative;z-index:1}
.acct .nm{font-size:13px;font-weight:800;margin-top:2px;position:relative;z-index:1}
.acct .bal{font-size:30px;font-weight:900;letter-spacing:-1px;margin:10px 0 2px;position:relative;z-index:1}
.acct .bar{height:7px;background:#FFFFFF40;border-radius:10px;overflow:hidden;margin:8px 0 5px;max-width:70%;position:relative;z-index:1}
.acct .bar i{display:block;height:100%;background:#fff;border-radius:10px}
.acct .sub{font-size:11.5px;color:#E3FBF6;position:relative;z-index:1}
.acct .em{position:absolute;right:16px;bottom:12px;font-size:52px;z-index:1;filter:drop-shadow(0 8px 10px #00000030)}
.mflow{display:flex;align-items:center;gap:5px;font-size:11px;font-weight:700;color:#4A6378;margin:4px 0 8px;flex-wrap:wrap}
.mflow span{background:#fff;border:1px solid var(--line);border-radius:20px;padding:5px 9px}
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
    """발표·체험용 샘플 소비 내역 — 금융 거래 내역 연결을 가정한 데모 데이터.
    이번 달 항목은 날짜와 상관없이 항상 이번 달 안에 들어가도록 배치한다.
    (기본 예산 50만 원 기준: 패션/의류·구독서비스만 초과, 전자기기는 주의, 나머지는 여유)"""
    now = now_kst()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    span = max(0, now.day - 1)
    # (카테고리, 항목, 금액, 이번 달 경과 비율, 시각)
    current = [
        ("식품", "배달 치킨", 23000, 0.05, 23), ("구독서비스", "넷플릭스", 17000, 0.10, 10),
        ("패션/의류", "후드티", 39000, 0.15, 0), ("뷰티", "선크림", 18000, 0.22, 14),
        ("전자기기", "무선 이어폰", 42000, 0.30, 1), ("식품", "배달 치킨", 21000, 0.38, 22),
        ("구독서비스", "유튜브 프리미엄", 14900, 0.45, 9), ("패션/의류", "운동화", 69000, 0.55, 23),
        ("생활용품", "세제", 12000, 0.62, 16), ("취미/여가", "보드게임", 18000, 0.80, 20),
    ]
    rows = []
    for cat, name, amt, frac, hour in current:
        days = int(round(frac * span))
        when = (now - timedelta(days=days)).replace(hour=hour, minute=15, second=0, microsecond=0)
        if when > now:
            when = now - timedelta(minutes=10 + days)
        rows.append((cat, name, amt, when))
        if cat == "구독서비스":  # 지난달 같은 날 결제 → 정기결제로 감지
            rows.append((cat, name, amt, when - timedelta(days=30)))
    # 지난달 이전 소비 (월별 추이용)
    for cat, name, amt, before, hour in [("패션/의류", "셔츠", 59000, 10, 21), ("식품", "장보기", 56000, 15, 18),
                                         ("패션/의류", "모자", 45000, 32, 13), ("식품", "배달 피자", 27000, 40, 23)]:
        rows.append((cat, name, amt, (month_start - timedelta(days=before)).replace(hour=hour, minute=15)))
    for cat, name, amt, when in rows:
        add_expense(cat, name, amt, when)


# ---------------- 개인 소비 패턴 분석 ----------------
def expense_time(x):
    return parse_date(x.get("created_at")) or parse_date(x.get("purchased_at"))


def get_cat_budgets(total):
    """카테고리별 예산: 사용자가 정한 값(URL 저장) 또는 월 예산 기본 비율."""
    if "cfg_cb" not in ss:
        custom = {}
        raw = str(st.query_params.get("cb") or "")
        for part in raw.split(","):
            if ":" in part:
                i, v = part.split(":", 1)
                if i.isdigit() and int(i) < len(CATEGORIES) and number(v) > 0:
                    custom[CATEGORIES[int(i)]] = number(v)
        ss["cfg_cb"] = custom
    custom = ss["cfg_cb"]
    return {c: custom.get(c, int(round(total * CAT_SHARE.get(c, 5) / 100, -3))) for c in CATEGORIES}


def set_cat_budget(cat, value):
    custom = dict(ss.get("cfg_cb", {}))
    custom[cat] = number(value)
    ss["cfg_cb"] = custom
    st.query_params["cb"] = ",".join(f"{CATEGORIES.index(c)}:{v}" for c, v in custom.items() if c in CATEGORIES)


def detect_recurring(expenses, now):
    """구독서비스 카테고리이거나 약 한 달 간격으로 반복된 결제 → 다음 결제 예정일 추정."""
    groups = {}
    for x in expenses:
        t = expense_time(x)
        key = norm_name(x.get("item_name"))
        if t and key:
            groups.setdefault(key, []).append((t, x))
    out = []
    for items in groups.values():
        items.sort(key=lambda a: a[0])
        last_t, last_x = items[-1]
        cat = last_x.get("category") or "기타"
        monthly = any(25 <= (items[i][0] - items[i - 1][0]).days <= 35 for i in range(1, len(items)))
        if cat == "구독서비스" or monthly:
            nxt = last_t + timedelta(days=30)
            while nxt < now:
                nxt += timedelta(days=30)
            out.append({"name": str(last_x.get("item_name") or "정기결제"), "amount": number(last_x.get("amount")),
                        "cat": cat, "next": nxt, "days": (nxt.date() - now.date()).days})
    return sorted(out, key=lambda r: r["next"])


def build_profile(expenses, records):
    """축적된 소비/결정 기록 → 개인 소비 프로필."""
    now = now_kst()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    recent90 = now - timedelta(days=90)
    recent30 = now - timedelta(days=30)
    months = []
    for i in range(3, -1, -1):
        yy, mm = now.year, now.month - i
        while mm <= 0:
            mm += 12
            yy -= 1
        months.append((yy, mm))
    hist = {k: Counter() for k in months}
    month_by_cat, by_cat_3m, by_cat_all = Counter(), Counter(), Counter()
    slots, name_count = Counter(), Counter()
    cat_amounts, name_display = {}, {}
    recent_items, subs_month, purchases = [], [], []
    late = timed = 0

    for x in expenses:
        cat = x.get("category") or "기타"
        amt = number(x.get("amount"))
        t = expense_time(x)
        cat_amounts.setdefault(cat, []).append(amt)
        by_cat_all[cat] += amt
        if not t:
            continue
        purchases.append((t, x))
        timed += 1
        slots[time_slot(t.hour)] += 1
        if t.hour in LATE_NIGHT:
            late += 1
        if (t.year, t.month) in hist:
            hist[(t.year, t.month)][cat] += amt
        if t >= month_start:
            month_by_cat[cat] += amt
            if cat == "구독서비스":
                subs_month.append(x)
        if t >= recent90:
            by_cat_3m[cat] += amt
            key = norm_name(x.get("item_name"))
            if key:
                name_count[key] += 1
                name_display.setdefault(key, str(x.get("item_name")))
        if t >= recent30:
            recent_items.append((str(x.get("item_name") or ""), max(0, (now - t).days)))

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
    purchases.sort(key=lambda a: a[0], reverse=True)
    return {
        "now": now, "budget": budget, "month_spent": month_spent,
        "budget_left": budget - month_spent, "cat_budgets": get_cat_budgets(budget),
        "month_by_cat": month_by_cat, "by_cat_3m": by_cat_3m, "by_cat_all": by_cat_all,
        "hist": hist, "months": months,
        "cat_amounts": cat_amounts, "slots": slots,
        "late": late, "timed": timed, "late_ratio": late / timed if timed else 0,
        "decisions": decisions, "cat_decisions": cat_decisions,
        "held_done": len(held_done), "hold_drop": hold_drop,
        "repeats": [(name_display[k], c) for k, c in name_count.most_common() if c >= 2],
        "recent_items": recent_items, "purchases": purchases,
        "recurring": detect_recurring(expenses, now),
        "subs_month": subs_month,
        "subs_total": sum(number(x.get("amount")) for x in subs_month),
        "saved": sum(number(r.get("saved_amount")) for r in records if r.get("decision") == "NOT_BUY"),
        "has_data": bool(expenses or records),
    }


def personal_signals(p, product_name, category, price, subscription=False):
    """구매 직전, 개인 소비상황과 이번 상품을 비교한 신호 (level, 문장)."""
    s = []
    left = p["budget_left"]
    if price > 0:
        if left <= 0:
            s.append(("high", f"이번 달 전체 예산을 이미 {money(-left)} 초과했어요."))
        elif price > left:
            s.append(("high", f"사면 이번 달 예산을 {money(price - left)} 초과해요. (남은 예산 {money(left)})"))
        elif price >= left * 0.3:
            s.append(("mid", f"남은 예산 {money(left)} 중 {price / left * 100:.0f}%를 쓰게 돼요."))
    cb = p["cat_budgets"].get(category, 0)
    used = p["month_by_cat"].get(category, 0)
    if cb > 0:
        pct_now, pct_after = used / cb * 100, (used + max(price, 0)) / cb * 100
        if price > 0 and pct_after >= 80:
            s.append(("high" if pct_after > 100 else "mid",
                      f"이번 달 {category} 지출이 설정한 예산에 가까워졌어요. 사면 예산의 {pct_after:.0f}%를 쓰게 돼요."))
        elif used > 0:
            s.append(("info", f"이번 달 {category} 예산의 {pct_now:.0f}%({money(used)})를 사용했어요."))
    key = norm_name(product_name)
    if len(key) >= 2:
        for item, days in p["recent_items"]:
            k2 = norm_name(item)
            if len(k2) >= 2 and (key in k2 or k2 in key):
                when = "오늘" if days == 0 else f"{days}일 전"
                s.append(("high", f"최근 30일 안에 유사한 구매가 있었어요. ({when} '{item}')"))
                break
    amounts = p["cat_amounts"].get(category, [])
    if price > 0 and len(amounts) >= 2:
        avg = sum(amounts) / len(amounts)
        if avg > 0 and price >= avg * 1.5:
            s.append(("mid", f"평소 {category} 구매 평균({money(avg)})보다 {price / avg:.1f}배 비싸요."))
    if category == "구독서비스" or subscription:
        s.append(("mid", "다음 결제일부터 자동으로 비용이 청구될 수 있어요. 해지 조건을 꼭 확인하세요."))
        if p["subs_month"]:
            s.append(("info", f"이번 달 이미 정기결제 {len(p['subs_month'])}건({money(p['subs_total'])})을 이용 중이에요."))
    if p["now"].hour in LATE_NIGHT:
        s.append(("mid", "지금은 밤 10시~새벽 5시 심야 시간대예요. 피곤할 때는 충동구매가 늘어나기 쉬워요."))
    if p["timed"] >= 3 and p["late_ratio"] >= 0.3:
        s.append(("info", f"지금까지 구매의 {p['late_ratio'] * 100:.0f}%가 심야에 이뤄졌어요."))
    cd = p["cat_decisions"].get(category)
    if cd:
        decided = cd["BUY"] + cd["NOT_BUY"]
        if decided >= 2 and cd["NOT_BUY"] / decided >= 0.5:
            s.append(("info", f"{category} 상품은 체크 후 {cd['NOT_BUY'] / decided * 100:.0f}%를 사지 않기로 했어요."))
    if p["held_done"] >= 2 and p["hold_drop"] / p["held_done"] >= 0.4:
        s.append(("info", f"잠시 보류했던 상품의 {p['hold_drop'] / p['held_done'] * 100:.0f}%는 결국 사지 않았어요."))
    if not s:
        if p["has_data"]:
            s.append(("good", "지금까지의 소비 기록에서 특별히 걸리는 패턴은 없어요."))
        else:
            s.append(("info", "아직 소비 기록이 적어요. 기록이 쌓일수록 체키의 판단이 더 정확해져요."))
    return s


def need_score(risk_score, signals):
    """개인 맞춤형 확인 필요도 = 화면 유도 위험(55%) + 개인 소비상황 신호(45%)."""
    weight = {"high": 28, "mid": 14, "info": 5, "good": 0}
    personal = min(100, sum(weight.get(lv, 0) for lv, _ in signals))
    return int(round(number(risk_score) * 0.55 + personal * 0.45))


def need_label(score):
    if score >= 65:
        return "hi", "꼭 확인해요"
    if score >= 35:
        return "mid", "한 번 더 확인해요"
    return "lo", "가볍게 확인해요"


def profile_to_text(p, category, price, signals):
    """AI 프롬프트에 넣을 개인 소비데이터 요약."""
    now = p["now"]
    slot_txt = ", ".join(f"{k} {v}회" for k, v in p["slots"].most_common()) or "기록 없음"
    amounts = p["cat_amounts"].get(category, [])
    avg_txt = money(sum(amounts) / len(amounts)) if amounts else "기록 없음"
    d = p["decisions"]
    hold_rate = f"{p['hold_drop'] / p['held_done'] * 100:.0f}%" if p["held_done"] else "기록 없음"
    rep = ", ".join(f"{n}({c}회)" for n, c in p["repeats"][:5]) or "없음"
    rec = ", ".join(f"{r['name']} {money(r['amount'])}(D-{r['days']})" for r in p["recurring"][:5]) or "없음"
    cb = p["cat_budgets"].get(category, 0)
    lines = [
        "[사용자 소비 데이터 요약]",
        f"- 현재 시각: {now:%Y-%m-%d %H:%M} ({time_slot(now.hour)}{', 심야' if now.hour in LATE_NIGHT else ''})",
        f"- 확인 중인 상품 가격: {money(price) if price else '미확인'}",
        f"- 이번 달 총 소비: {money(p['month_spent'])} / 월 예산 {money(p['budget'])} (남은 예산 {money(p['budget_left'])})",
        f"- 이번 달 {category} 소비: {money(p['month_by_cat'].get(category, 0))} / {category} 예산 {money(cb)}",
        f"- {category} 평균 구매가: {avg_txt}",
        f"- 구매 시간대 분포: {slot_txt}",
        f"- 체키 결정 기록: 구매 {d['BUY']}회, 보류 중 {d['HOLD']}회, 포기 {d['NOT_BUY']}회, 보류 후 포기율 {hold_rate}",
        f"- 최근 90일 반복 구매: {rep}",
        f"- 정기결제 예정: {rec}",
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


def parse_lines(text, field):
    return [m.group(1).strip() for m in
            re.finditer(rf"(?m)^\s*[-*]*\s*\**{re.escape(field)}\**\s*:\s*\**\s*(.+)$", text, re.I)]


def parse_patterns(raw):
    out = []
    for line in parse_lines(raw, "PATTERN"):
        parts = [x.strip().strip("\"'“”") for x in line.split("|")]
        if len(parts) < 2 or not parts[1] or parts[1] in ("없음", "-"):
            continue
        ptype = next((k for k in PATTERN_TYPES if k in parts[0]), "압박형")
        out.append({"type": ptype, "name": parts[1][:30],
                    "quote": parts[2][:60] if len(parts) > 2 else "",
                    "desc": parts[3][:120] if len(parts) > 3 else ""})
    return out[:6]


def parse_boxes(raw):
    out = []
    for line in parse_lines(raw, "BOX"):
        label = line.split("|")[0].strip()
        nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", line.split("|")[-1])]
        if len(nums) >= 4:
            y1, x1, y2, x2 = nums[:4]
            if 0 <= y1 < y2 <= 1000 and 0 <= x1 < x2 <= 1000:
                out.append({"label": label, "y1": y1, "x1": x1, "y2": y2, "x2": x2})
    return out[:6]


def annotate_image(image, boxes):
    """스크린샷 위에 유도 요소 위치를 번호 박스로 표시 (한글 폰트 없이 번호만 그림)."""
    if image is None or not boxes:
        return None
    try:
        im = image.convert("RGB").copy()
        im.thumbnail((900, 900))
        w, h = im.size
        draw = ImageDraw.Draw(im)
        line = max(3, w // 180)
        r = max(12, w // 40)
        try:
            font = ImageFont.load_default(size=int(r * 1.2))
        except Exception:
            font = ImageFont.load_default()
        for i, b in enumerate(boxes, 1):
            x1, y1 = b["x1"] / 1000 * w, b["y1"] / 1000 * h
            x2, y2 = b["x2"] / 1000 * w, b["y2"] / 1000 * h
            draw.rounded_rectangle([x1, y1, x2, y2], radius=8, outline=(226, 85, 85), width=line)
            cx, cy = max(r, x1), max(r, y1)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(226, 85, 85))
            try:
                draw.text((cx, cy), str(i), fill="white", font=font, anchor="mm")
            except Exception:
                draw.text((cx - r / 3, cy - r / 2), str(i), fill="white", font=font)
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception:
        return None


def analyze_product(product_name, category, image=None, page_text=None, user_price=0, context=""):
    types_txt = "\n".join(f"- {k}: {v[1]}" for k, v in PATTERN_TYPES.items())
    prompt = f"""
너는 소비자를 보호하는 AI 서비스 '체키(CHECKI)'다. 구매를 막지 않고, 소비자가 결제 전에 스스로 판단하도록 돕는다.
아래 4단계로 판단한다.

1) 다크패턴 탐지: 제공된 쇼핑 화면 또는 페이지의 문구, 가격, 버튼, 선택 옵션, 화면 배치에서
   실제로 확인 가능한 구매 유도 요소만 찾는다. 확실하지 않으면 단정하지 않는다.
   유형(공정거래위원회·한국소비자원 분류):
{types_txt}
2) 구매정보 검증: 화면 안에서 확인 가능한 범위로 사실 여부를 확인한다.
   (정가 대비 실제 할인율 계산, 1+1·묶음 상품의 개당 단가, 결제 단계에서 추가되는 비용, 자동결제·해지 조건)
3) 소비상황 개인화: 아래 사용자 소비 데이터와 연결해 '이 사용자에게 어떤 구매인지' 판단한다.
   데이터가 부족하면 부족하다고 말한다. 데이터에 없는 사실을 만들지 않는다.
4) 판단 지원: 추천만 하고 결정은 사용자에게 맡긴다.
   RECOMMEND 기준: BUY=뚜렷한 문제 없음, HOLD=충동구매 신호나 유도 요소가 있음, RECONSIDER=예산 초과·반복 구매 등 뚜렷한 문제.

상품명: {product_name}
카테고리: {category}
사용자가 입력한 가격: {user_price if user_price else '미입력'}

{context}

판매 가격을 확실히 확인할 수 없으면 PRICE: 0 (사용자가 입력한 가격이 있으면 그 값).
위험도는 LOW/MEDIUM/HIGH, 점수는 0~100 (화면의 구매 유도 요소 기준).
아래 형식을 정확히 지키고, 한 줄당 한 항목으로 답하라. 마크다운 기호는 쓰지 마라.
PRODUCT_NAME: 상품명
PRICE: 숫자만
RISK_LEVEL: LOW 또는 MEDIUM 또는 HIGH
RISK_SCORE: 숫자
SUMMARY: 화면에 대한 쉬운 한국어 한 문장
DETECTED: 실제 확인된 요소 이름을 쉼표로 구분. 없으면 없음
PATTERN: 유형 | 요소 이름 | 화면 속 문구 그대로 | 소비자에게 미치는 영향 한 문장
(PATTERN은 발견된 요소마다 한 줄씩 최대 5줄. 유형은 편취형/오도형/방해형/압박형 중 하나. 없으면 PATTERN 줄을 쓰지 마라)
BOX: 요소 이름 | ymin,xmin,ymax,xmax
(BOX는 스크린샷이 있을 때만, PATTERN과 같은 순서로 해당 요소가 보이는 위치. 이미지 크기를 0~1000으로 정규화한 좌표)
VERIFY: 화면에서 확인한 가격·조건 검증 결과 한두 문장 (계산 근거 포함. 확인할 수 없으면 확인할 수 없다고 말함)
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
    patterns = parse_patterns(raw)
    detected = parse_field(raw, "DETECTED", "")
    if not detected or detected in ("없음", "-"):
        detected = ", ".join(x["name"] for x in patterns) or "없음"
    subscription = any(k in (x["name"] + x["quote"] + x["desc"]) for x in patterns
                       for k in ("구독", "자동결제", "자동 결제", "정기결제", "무료체험", "유료 전환"))
    boxes = parse_boxes(raw) if image is not None else []
    return {
        "product_name": parse_field(raw, "PRODUCT_NAME", product_name) or product_name,
        "price": price,
        "risk_level": level,
        "risk_score": min(100, max(0, parse_price(parse_field(raw, "RISK_SCORE", "50")))),
        "summary": parse_field(raw, "SUMMARY", "구매 전 다시 확인해보세요."),
        "detected": detected,
        "patterns": patterns,
        "subscription": subscription,
        "verify": parse_field(raw, "VERIFY", "화면에서 가격·조건을 충분히 확인하지 못했어요. 결제 단계의 최종 금액을 꼭 확인하세요."),
        "advice": parse_field(raw, "ADVICE", "필요성과 가격을 확인하세요."),
        "recommend": rec,
        "personal": parse_field(raw, "PERSONAL", "소비 기록이 쌓이면 더 구체적인 조언을 드릴게요."),
        "annotated": annotate_image(image, boxes),
        "box_labels": [b["label"] for b in boxes],
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
SPARKS = ('<span class="spark" style="right:30%;top:14px">✦</span>'
          '<span class="spark" style="right:6%;top:12px;animation-delay:.8s">✦</span>'
          '<span class="spark" style="right:31%;bottom:16px;animation-delay:1.5s;font-size:10px">✦</span>')
MASCOT_FALLBACK = {"scan": "🤖", "search": "🔍", "wait": "⏳", "chart": "📊"}


def mascot_or_emoji(which):
    img = mascot_img(which, "float")
    return img or f'<div class="em float">{MASCOT_FALLBACK.get(which, "🤖")}</div>'


def app_head(small, title):
    html_block(f'<div class="app-head"><div>{BRAND}<div class="hi">{safe(small)}</div><h2>{title}</h2></div></div>')


def page_hero(small, title, which, say):
    html_block(
        f'<div class="phero">{SPARKS}<div class="tx">{BRAND}<div class="hi">{safe(small)}</div><h2>{title}</h2>'
        f'<div class="say"><span class="si">💬</span><span class="st">{safe(say)}</span></div></div><div class="m">{mascot_or_emoji(which)}</div></div>'
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


def short_money(v):
    v = number(v)
    if v >= 10000:
        return f"{v / 10000:.1f}만".replace(".0만", "만")
    return f"{v:,}"


def vbars_html(items, highlight=(), fmt=str, hl_last=False):
    mx = max([v for _, v in items] + [1])
    cols = []
    for i, (k, v) in enumerate(items):
        cls = " zero" if v == 0 else (" hl" if hl_last and i == len(items) - 1 else (" late" if k in highlight else ""))
        cols.append(f'<div class="vbar"><small>{safe(fmt(v))}</small>'
                    f'<div class="col{cls}" style="height:{max(4, v / mx * 86):.0f}%"></div><span>{safe(k)}</span></div>')
    return f'<div class="bars"><div class="vbars">{"".join(cols)}</div></div>'


LOADER_STEPS = ["구매 화면 분석", "구매 유도 요소 확인", "가격 정보 확인", "내 소비내역 확인"]


def loader_html(done):
    steps = "".join(
        f'<div class="{"done" if i < done else ("now" if i == done else "")}"><b>{"✓" if i < done else ""}</b>'
        f'{s}{" 중" if i == done else ""}</div>' for i, s in enumerate(LOADER_STEPS))
    return (f'<div class="loader">{mascot_or_emoji("search")}<h3>체키가 구매 화면을 분석하고 있어요</h3>'
            f'<p>잠시만 기다려 주세요. 구매를 서두르게 하는 요소와 내 소비 정보를 확인하고 있어요.</p>'
            f'<div class="lbar"><i style="width:{done / len(LOADER_STEPS) * 100:.0f}%"></i></div>'
            f'<div class="lsteps">{steps}</div>'
            f'<div class="meta" style="margin-top:8px;text-align:right">{done}/{len(LOADER_STEPS)}</div></div>')


def account_card(p, records):
    completed = [r for r in records if r.get("decision") == "NOT_BUY"]
    total = sum(number(r.get("saved_amount")) for r in completed)
    goal = max(1, get_setting("cfg_goal", DEFAULT_GOAL))
    pct = min(100, total / goal * 100)
    tail = re.sub(r"\D", "", user_id)[-4:].rjust(4, "0")
    html_block(
        f'<div class="acct"><div class="no">CHECKI 가상 저축계좌 · 1004-28-{tail}</div>'
        f'<div class="nm">체키 저축계좌</div><div class="bal">{money(total)}</div>'
        f'<div class="bar"><i style="width:{pct:.0f}%"></i></div>'
        f'<div class="sub">목표 {money(goal)} · {pct:.0f}% 달성 · 입금 {len(completed)}건</div>'
        f'<div class="em float">🐷</div></div>'
        '<div class="mflow"><span>🙅 구매 포기</span>→<span>💰 절약 금액 누적</span>→<span>🏦 가상 저축계좌 반영</span></div>'
    )
    return goal, completed


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
    onboarded = ss.get("onboarded") or str(st.query_params.get("ob") or "") == "1"
    if not onboarded and not p["has_data"]:
        # 첫 실행 온보딩: 예산 설정 + 소비데이터 연결 동의 (AI 소비 분석 흐름의 '수집' 단계)
        app_head("처음 오셨군요 👋", "체키와 <em>시작</em>해볼까요?")
        html_block(
            f'<div class="mhero">{SPARKS}<div class="tx"><span class="pill">AI 구매 판단 도우미</span>'
            '<h1>사기 전에,<br>체키 해보세요</h1>'
            '<p>구매를 막지 않아요.<br>결제 전에 꼭 필요한 정보만 보여드려요.</p></div>'
            f'<div class="m">{mascot_or_emoji("scan")}</div></div>'
        )
        step(1, "한 달 예산을 알려주세요")
        ob_budget = st.number_input("월 예산 (원)", min_value=10000, step=50000,
                                    value=int(p["budget"]), key="ob_budget")
        step(2, "소비 데이터 연결에 동의해주세요")
        ob_consent = st.toggle("금융 거래 내역 불러오기에 동의해요", value=True, key="ob_consent")
        st.caption("동의한 거래 내역과 직접 입력한 예산으로 나만의 소비 기준을 만들어요. "
                   "MVP에서는 체험용 샘플 내역을 불러와요.")
        if st.button("체키 시작하기", type="primary", use_container_width=True, key="ob_start"):
            set_setting("cfg_budget", ob_budget)
            if ob_consent:
                add_sample_data()
            ss["onboarded"] = True
            st.query_params["ob"] = "1"
            ss["notice"] = "체키가 내 소비 기준을 만들었어요!"
            st.rerun()
        if st.button("둘러보기만 할게요", use_container_width=True, key="ob_skip"):
            ss["onboarded"] = True
            st.query_params["ob"] = "1"
            st.rerun()
    else:
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
            ("🏦", "저축계좌", money(p["saved"]), "green"),
            ("⏱️", "보류 중", f"{p['decisions']['HOLD']}건", "amber"),
        ])
        ready = [r for r in records if r.get("decision") == "HOLD"
                 and (parse_date(r.get("hold_until")) or now_kst()) <= now_kst()]
        soon = [r for r in p["recurring"] if r["days"] <= 7]
        if ready:
            tip = (f"30분이 지난 보류 상품이 {len(ready)}개 있어요. 지금도 꼭 필요한지 같이 생각해봐요!", "wait")
        elif soon:
            tip = (f"{soon[0]['days']}일 뒤 '{soon[0]['name']}' {money(soon[0]['amount'])}이 자동으로 결제될 수 있어요.", "search")
        elif p["now"].hour in LATE_NIGHT:
            tip = ("지금은 심야 시간이에요. 피곤할 땐 충동구매가 늘어나니 내일 다시 볼까요?", "wait")
        elif pct >= 80:
            tip = (f"이번 달 예산을 {pct:.0f}% 썼어요. 남은 기간은 조금만 아껴봐요!", "chart")
        elif p["saved"] > 0:
            tip = (f"지금까지 {money(p['saved'])}을 저축계좌에 모았어요. 정말 멋져요!", "chart")
        else:
            tip = ("사기 전에 잠깐만 멈춰도 충동구매가 확 줄어들어요. 저랑 같이 체크해봐요!", "search")
        talk(tip[1], "체키의 한마디", tip[0])
        if ready and st.button("결정하러 가기", use_container_width=True, key="home_ready"):
            go("기록")
            st.rerun()

        if p["recurring"]:
            sec("다가오는 정기결제", f"{len(p['recurring'])}건")
            rows = [(CAT_ICON.get(r["cat"], "🔁"), r["name"], f"{r['next']:%m월 %d일} 결제 예정 · {money(r['amount'])}",
                     f'<span class="dday{" soon" if r["days"] <= 7 else ""}">D-{r["days"]}</span>')
                    for r in p["recurring"][:3]]
            html_block(list_html(rows))

        sec("체키는 이렇게 도와요", "옆으로 넘기기 →")
        flow = [
            ("다크패턴 탐지", "문구·가격·버튼·옵션에서 구매 유도 요소를 찾아요"),
            ("구매정보 검증", "할인율·묶음 단가·추가 비용이 사실인지 확인해요"),
            ("소비상황 개인화", "예산·최근 구매와 비교해 '나에게 어떤 구매인지' 봐요"),
            ("구매 직전 판단 지원", "최종 선택은 내가! 계속·보류·포기 중 골라요"),
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
    product_name = st.text_input("상품명", placeholder="예: Balance 러닝화", key="in_name")
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

    cb = p["cat_budgets"].get(category, 0)
    used = p["month_by_cat"].get(category, 0)
    html_block('<div class="data-chip">'
               f'<span>{CAT_ICON.get(category, "")} {safe(category)} 예산 {used / cb * 100 if cb else 0:.0f}% 사용</span>'
               f'<span>💰 남은 예산 {money(p["budget_left"])}</span>'
               f'<span>🕒 지금 {time_slot(p["now"].hour)}</span></div>')

    if st.button("체키로 분석하기", type="primary", use_container_width=True, key="analyze"):
        url = (product_url or "").strip()
        if not product_name.strip():
            st.warning("상품명을 입력해주세요.")
        elif image is None and not url:
            st.warning("스크린샷을 올리거나 상품 링크를 넣어주세요.")
        else:
            box = st.empty()
            try:
                box.markdown(loader_html(0), unsafe_allow_html=True)
                page_text = None
                if image is None and url:
                    page_text = read_url(url)
                box.markdown(loader_html(1), unsafe_allow_html=True)
                pre_signals = personal_signals(p, product_name, category, number(user_price))
                context = profile_to_text(p, category, number(user_price), pre_signals)
                box.markdown(loader_html(2), unsafe_allow_html=True)
                result = analyze_product(product_name.strip(), category, image, page_text,
                                         number(user_price), context)
                box.markdown(loader_html(3), unsafe_allow_html=True)
                result["signals"] = personal_signals(p, result["product_name"], category,
                                                     number(result["price"]), result.get("subscription", False))
                result["need"] = need_score(result["risk_score"], result["signals"])
                box.markdown(loader_html(4), unsafe_allow_html=True)
                ss["latest_analysis"] = result
                ss["latest_category"] = category
                ss["latest_record"] = insert_record(result, category, "PENDING")
                ss.pop("purchase_action", None)
                box.empty()
            except Exception as exc:
                box.empty()
                st.error(f"분석을 완료하지 못했어요: {exc}")
                if image is None:
                    st.info("상품 페이지 접근이 막힌 경우 스크린샷으로 분석해주세요.")

    result = ss.get("latest_analysis")
    if result:
        cat_now = ss.get("latest_category", "기타")
        signals = result.get("signals", [])
        need = result.get("need", need_score(result["risk_score"], signals))
        ncls, ntxt = need_label(need)
        ncolor = {"hi": "#E25555", "mid": "#E9A21B", "lo": "#22B07D"}[ncls]
        head_img = mascot_img("scan", "float") or '<div class="em">🤖</div>'
        html_block(
            f'<div class="done-head"><div class="m">{head_img}</div><div class="tx">'
            f'<div class="kicker">AI 분석 완료</div><h3>체키가 확인했어요!</h3>'
            f'<p>구매 전에 아래 내용을 한 번 더 확인해 보세요.</p>'
            f'<span class="need {ncls}">확인 필요도 · {ntxt}</span></div>'
            f'{ring_html(need, str(need), "확인 필요도", dark=True, color=ncolor)}</div>'
        )

        # ① 다크패턴 탐지
        pats = result.get("patterns") or []
        labels = result.get("box_labels") or []
        score = number(result["risk_score"])
        if pats:
            items = []
            for i, x in enumerate(pats, 1):
                color = PATTERN_TYPES.get(x["type"], ("#1689F8", ""))[0]
                num = f'<span class="pnum">{i}</span>' if i <= len(labels) else ""
                quote = f'<q>{safe(x["quote"])}</q>' if x["quote"] else ""
                desc = f'<p>{safe(x["desc"])}</p>' if x["desc"] else ""
                items.append(f'<div class="pat"><div class="t">{num}<span class="ptype" style="background:{color}">'
                             f'{safe(x["type"])}</span><span class="pname">{safe(x["name"])}</span></div>{quote}{desc}</div>')
            body = "".join(items)
            title, ic = "구매 유도 요소가 발견됐어요", "red"
        else:
            parts = [t.strip() for t in re.split(r"[,，·/]", result["detected"]) if t.strip()]
            found = [t for t in parts if t not in ("없음", "확인 필요")]
            body = ('<div class="tags">' + "".join(f'<span class="tag warn">{safe(t)}</span>' for t in found) + "</div>"
                    if found else "")
            title, ic = ("구매 유도 요소가 발견됐어요", "red") if found else ("뚜렷한 구매 유도 요소는 없어요", "green")
        html_block(
            f'<div class="ccard"><div class="hd"><div class="ic {ic}">{"⚠️" if ic == "red" else "✅"}</div>'
            f'<div><b>{title}</b><span>화면 유도 위험 {score}점 · {len(pats) or "-"}개 요소</span></div></div>'
            f'<div class="bd">{safe(result["summary"])}{body}</div></div>'
        )
        if result.get("annotated"):
            if st.toggle("📍 화면에서 위치 보기", key="show_annot"):
                enc = base64.b64encode(result["annotated"]).decode()
                html_block(f'<div class="annot"><img src="data:image/jpeg;base64,{enc}"></div>')
        if st.toggle("📚 다크패턴 4가지 유형 알아보기", key="show_types"):
            html_block('<div class="legend4">' + "".join(
                f'<div><b style="color:{c}">{k}</b>{d}</div>' for k, (c, d) in PATTERN_TYPES.items()) + "</div>")

        # ② 구매정보 검증
        price_txt = (f"확인된 가격 {money(result['price'])}" if number(result["price"]) > 0
                     else "가격 미확인 · 포기 시 절약 금액 0원으로 기록")
        html_block(
            f'<div class="ccard"><div class="hd"><div class="ic blue">📊</div>'
            f'<div><b>가격·조건을 확인했어요</b><span>{safe(price_txt)}</span></div></div>'
            f'<div class="bd">{safe(result.get("verify"))}<br><span class="meta">💡 {safe(result["advice"])}</span></div></div>'
        )

        # ③ 소비상황 개인화
        rec = result.get("recommend", "HOLD")
        icon, rec_title = RECOMMEND.get(rec, RECOMMEND["HOLD"])
        rec_img = mascot_img({"BUY": "scan", "HOLD": "wait", "RECONSIDER": "search"}.get(rec, "wait"), "mimg float")
        rec_visual = rec_img or f'<div class="icon">{icon}</div>'
        cbx = p["cat_budgets"].get(cat_now, 0)
        usedx = p["month_by_cat"].get(cat_now, 0)
        html_block(
            f'<div class="ccard"><div class="hd"><div class="ic violet">👛</div>'
            f'<div><b>나의 소비상황과 비교했어요</b>'
            f'<span>{safe(cat_now)} 예산 {usedx / cbx * 100 if cbx else 0:.0f}% 사용 · 남은 예산 {money(p["budget_left"])}</span></div></div>'
            f'<div class="rec {safe(rec)}" style="margin-top:10px">{rec_visual}<div><b>{rec_title}</b>'
            f'<span>{safe(result.get("personal"))}</span></div></div>{chips_html(signals)}</div>'
        )
        if st.toggle("🔍 AI가 참고한 내 소비 데이터 보기", key="show_ctx"):
            html_block(f'<div class="ctx">{safe(result.get("context") or "데이터 없음")}</div>')

        # ④ 구매 직전 판단 지원
        sec("구매 전, 한 번 더 체크해 보세요", sub="체키는 구매를 막지 않아요. 최종 선택은 언제나 내가 해요.")
        if ss.get("purchase_action") == "BUY":
            amount = st.number_input("실제로 결제할 금액", min_value=0, step=1000,
                                     value=number(result["price"]), key="latest_buy_amount")
            if st.button("구매 기록 저장", type="primary", use_container_width=True, key="buy_save"):
                if finalize_latest("BUY"):
                    add_expense(cat_now, result["product_name"], amount)
                    clear_latest()
                    ss["notice"] = "구매 기록을 저장했어요."
                    go("리포트")
                    st.rerun()
            if st.button("이전 선택으로 돌아가기", use_container_width=True, key="buy_back"):
                ss.pop("purchase_action", None)
                st.rerun()
        else:
            if st.button("구매 계속하기", type="primary", use_container_width=True, key="act_buy"):
                ss["purchase_action"] = "BUY"
                st.rerun()
            b1, b2 = st.columns(2)
            with b1:
                if st.button("⏱️ 잠시 보류하기", use_container_width=True, key="act_hold"):
                    if finalize_latest("HOLD"):
                        clear_latest()
                        ss["notice"] = "30분 보류를 시작했어요."
                        go("기록")
                        st.rerun()
            with b2:
                if st.button("🙅 구매하지 않기", use_container_width=True, key="act_no"):
                    saved = number(result["price"])
                    if finalize_latest("NOT_BUY", saved):
                        clear_latest()
                        ss["notice"] = f"{money(saved)}을(를) 저축계좌에 담았어요."
                        go("기록")
                        st.rerun()

# ---------------- 리포트 ----------------
elif page == "리포트":
    cbs = p["cat_budgets"]
    usage = [(c, p["month_by_cat"].get(c, 0), cbs.get(c, 0)) for c in CATEGORIES if p["month_by_cat"].get(c, 0) > 0]
    usage.sort(key=lambda r: (r[1] / r[2]) if r[2] else 0, reverse=True)
    say = (f"이번 달 {usage[0][0]} 예산의 {usage[0][1] / usage[0][2] * 100:.0f}%를 사용했어요"
           if usage and usage[0][2] else "기록이 쌓이면 소비 습관을 분석해드릴게요!")
    page_hero("이번 달", "내 <em>소비상황</em>을 확인해볼까요?", "chart", say)

    if not expenses:
        empty("📊", "아직 소비 기록이 없어요.<br>체험용 샘플 내역으로 리포트를 미리 볼 수 있어요.", "chart")
        if st.button("✨ 체험용 샘플 내역 불러오기", type="primary", use_container_width=True, key="sample"):
            add_sample_data()
            ss["notice"] = "샘플 소비 내역을 불러왔어요."
            st.rerun()

    tab1, tab2, tab3 = st.tabs(["지출 현황", "최근 구매", "소비 패턴"])

    with tab1:
        periods = ["이번 달", "최근 3개월", "전체"]
        if ss.get("period") not in periods:
            ss["period"] = periods[0]
        if hasattr(st, "segmented_control"):
            period = st.segmented_control("기간", periods, key="period", label_visibility="collapsed")
            if period not in periods:
                period = periods[0]
        else:
            period = st.radio("기간", periods, key="period", horizontal=True, label_visibility="collapsed")
        by_cat = {"이번 달": p["month_by_cat"], "최근 3개월": p["by_cat_3m"]}.get(period, p["by_cat_all"])

        if period == "이번 달":
            budget_card(p)
            if usage:
                c, u, b = usage[0]
                pc = u / b * 100 if b else 0
                html_block(
                    f'<div class="card"><div class="catbig"><div class="ic">{CAT_ICON.get(c, "🛍️")}</div>'
                    f'<div class="tx"><b>{safe(c)}</b><span>{money(u)} / {money(b)}</span></div>'
                    f'<div class="pc">{pc:.0f}%</div></div>'
                    f'<div class="progress-bg"><div class="progress-fill" style="width:{min(100, pc):.0f}%"></div></div></div>'
                )
                html_block(f'<div class="notice" style="background:#EEF6FF;border-color:#D4E7FB;color:#245A8A">'
                           f'💡 이번 달 {safe(c)} 예산의 {pc:.0f}%를 사용했어요.</div>')

        sec("카테고리별 지출", period)
        total = sum(by_cat.values())
        if by_cat:
            rows = []
            for c, u in sorted(by_cat.items(), key=lambda r: r[1], reverse=True):
                if period == "이번 달" and cbs.get(c):
                    pc = u / cbs[c] * 100
                    sub, right = f"{money(u)} / {money(cbs[c])}", f"{pc:.0f}%"
                else:
                    pc = u / total * 100 if total else 0
                    sub, right = money(u), f"{pc:.0f}%"
                bar_cls = " over" if pc > 100 and period == "이번 달" else (" warn" if pc >= 80 and period == "이번 달" else "")
                rows.append(f'<div class="cbrow"><div class="top"><div class="ic">{CAT_ICON.get(c, "🛍️")}</div>'
                            f'<b>{safe(c)}</b><span>{safe(sub)}</span><em>{right}</em></div>'
                            f'<div class="pb"><i class="{bar_cls.strip()}" style="width:{min(100, pc):.0f}%"></i></div></div>')
            html_block(f'<div class="list">{"".join(rows)}</div>')
        else:
            empty("🗂️", f"{period} 지출 기록이 없어요.")

        sec("카테고리 상세")
        default_idx = CATEGORIES.index(usage[0][0]) if usage else 0
        detail = st.selectbox("카테고리 선택", CATEGORIES, index=default_idx, key="detail_cat",
                              label_visibility="collapsed")
        d_used, d_budget = p["month_by_cat"].get(detail, 0), cbs.get(detail, 0)
        d_pct = d_used / d_budget * 100 if d_budget else 0
        d_color = "#E25555" if d_pct > 100 else ("#E9A21B" if d_pct >= 80 else "#1689F8")
        html_block(
            f'<div class="card"><div class="kicker">{CAT_ICON.get(detail, "")} {safe(detail)} 지출 현황</div>'
            f'<div class="donut-row">{ring_html(d_pct, f"{d_pct:.0f}%", "사용", dark=True, color=d_color)}'
            f'<div class="lg"><div><i style="background:{d_color}"></i><span>사용한 금액<b>{money(d_used)}</b></span></div>'
            f'<div><i style="background:#E6EEF6"></i><span>남은 금액<b>{money(max(0, d_budget - d_used))}</b></span></div>'
            f'</div></div></div>'
        )
        trend = [(f"{m}월", p["hist"][(y, m)].get(detail, 0)) for y, m in p["months"]]
        html_block(vbars_html(trend, fmt=short_money, hl_last=True))
        prev, cur = trend[-2][1], trend[-1][1]
        if prev or cur:
            diff = cur - prev
            msg = (f"지난달보다 {detail} 지출이 {money(abs(diff))} {'늘었어요' if diff > 0 else '줄었어요'}."
                   if diff else f"지난달과 {detail} 지출이 같아요.")
            st.caption(f"📈 {msg}")

        if st.toggle("⚙️ 예산 설정", key="budget_toggle"):
            new_budget = st.number_input("월 예산 (원)", min_value=10000, step=50000,
                                         value=int(p["budget"]), key="budget_input")
            if st.button("월 예산 적용", key="budget_save", use_container_width=True):
                set_setting("cfg_budget", new_budget)
                ss.pop("cfg_cb", None)
                ss["notice"] = "월 예산을 바꿨어요."
                st.rerun()
            cb_cat = st.selectbox("카테고리 예산", CATEGORIES, key="cb_cat")
            cb_amt = st.number_input("카테고리 예산 (원)", min_value=0, step=10000,
                                     value=int(cbs.get(cb_cat, 0)), key=f"cb_amt_{CATEGORIES.index(cb_cat)}")
            if st.button("카테고리 예산 적용", key="cb_save", use_container_width=True):
                set_cat_budget(cb_cat, cb_amt)
                ss["notice"] = f"{cb_cat} 예산을 바꿨어요."
                st.rerun()

    with tab2:
        sec("최근 구매한 상품", f"{len(expenses)}건" if expenses else "")
        if p["purchases"]:
            rows = []
            for t, x in p["purchases"][:10]:
                days = max(0, (p["now"].date() - t.date()).days)
                cat = x.get("category") or "기타"
                rows.append((CAT_ICON.get(cat, "🛍️"), x.get("item_name") or "상품",
                             f"{cat} · {'오늘' if days == 0 else f'{days}일 전'}",
                             f'<b>{money(x.get("amount"))}</b>'))
            html_block(list_html(rows))
        else:
            empty("🧾", "아직 구매 기록이 없어요.")
        if p["repeats"]:
            n, c = p["repeats"][0]
            talk("search", "체키의 발견", f"최근 90일 동안 '{n}'을(를) {c}번 샀어요. 비슷한 상품을 최근에 구매했는지 확인해보세요.")
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

    with tab3:
        html_block('<span class="premium">👑 PREMIUM · 1개월 무료 체험 중</span>')
        sec("구매 시간대", f"심야 {p['late_ratio'] * 100:.0f}%" if p["timed"] else "")
        if p["timed"]:
            slot_items = [(n, p["slots"].get(n, 0)) for n, _, _ in TIME_SLOTS]
            html_block(vbars_html(slot_items, highlight=("새벽", "밤")))
            st.caption("보라색은 심야(밤 10시~새벽 5시) 구매예요.")
        else:
            empty("🕒", "구매 시간 기록이 없어요.")

        sec("구매 결정 습관")
        d = p["decisions"]
        tiles([
            ("🛒", "구매 계속", f"{d['BUY']}회", "blue"),
            ("⏱️", "보류 중", f"{d['HOLD']}회", "amber"),
            ("🙅", "구매 포기", f"{d['NOT_BUY']}회", "green"),
        ])
        if p["held_done"]:
            st.caption(f"잠시 보류 후 결국 사지 않은 비율 {p['hold_drop'] / p['held_done'] * 100:.0f}% "
                       f"({p['hold_drop']}/{p['held_done']}건)")

        sec("정기결제 · 반복구매")
        if p["recurring"]:
            rows = [(CAT_ICON.get(r["cat"], "🔁"), r["name"], f"{r['next']:%m월 %d일} 결제 예정 · {money(r['amount'])}",
                     f'<span class="dday{" soon" if r["days"] <= 7 else ""}">D-{r["days"]}</span>')
                    for r in p["recurring"]]
            html_block(list_html(rows))
        items = [("mid", f"최근 90일 '{n}' {c}회 구매") for n, c in p["repeats"][:5]]
        if items or not p["recurring"]:
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

# ---------------- 기록 ----------------
elif page == "기록":
    holds = p["decisions"]["HOLD"]
    say = (f"보류 중인 상품이 {holds}개 있어요. 언제든 결정할 수 있어요!" if holds
           else "사지 않은 만큼 저축계좌가 채워져요 🐷")
    page_hero("보류 중인 상품과 결정 내역", "나의 <em>체키 기록</em>", "wait", say)

    goal, completed = account_card(p, records)
    if st.toggle("🎯 저축 목표 바꾸기", key="goal_toggle"):
        new_goal = st.number_input("목표 금액 (원)", min_value=1000, step=10000,
                                   value=int(goal), key="goal_input")
        if st.button("목표 적용", key="goal_save", use_container_width=True):
            set_setting("cfg_goal", new_goal)
            ss["notice"] = "저축 목표를 바꿨어요."
            st.rerun()
    if completed:
        sec("입금 내역", f"{len(completed)}건")
        rows = []
        for r in completed[:5]:
            t = parse_date(r.get("decided_at")) or parse_date(r.get("created_at"))
            rows.append(("💰", r.get("product_name") or "상품",
                         f"구매 포기{f' · {t:%m.%d %H:%M}' if t else ''}",
                         f'<b style="color:#0E8F6E">+{money(r.get("saved_amount"))}</b>'))
        html_block(list_html(rows))

    sec("체키 기록", f"{len(records)}건" if records else "")
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
                            ss["notice"] = f"{money(price)}을(를) 저축계좌에 담았어요."
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
                st.caption(f"💚 {money(record.get('saved_amount'))} 저축계좌 입금")
            elif decision == "PENDING":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⏱️ 잠시 보류", key=f"pending_hold_{kid}", use_container_width=True):
                        if update_record(rid, "HOLD"):
                            st.rerun()
                with col2:
                    if st.button("🙅 구매하지 않기", key=f"pending_no_{kid}", use_container_width=True):
                        if update_record(rid, "NOT_BUY", price):
                            st.rerun()

if ss.get("notice"):
    st.toast(ss.pop("notice"))
