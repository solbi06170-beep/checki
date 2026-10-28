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
# CHECKI v2
# - 기존 Supabase 테이블 2개(checki_expenses, checki_records) 그대로 사용
# - 새 테이블/컬럼 추가 없음
# - AI 분석 = ① 구매 화면 다크패턴 분석 + ② 개인 소비데이터 기반 맞춤 판단
# =============================================================
st.set_page_config(page_title="CHECKI | 체키", page_icon="🔎", layout="wide",
                   initial_sidebar_state="collapsed")

KST = timezone(timedelta(hours=9))
MODEL = "gemini-3.5-flash-lite"
CATEGORIES = ["패션/의류", "뷰티", "식품", "생활용품", "전자기기",
              "가구/인테리어", "취미/여가", "구독서비스", "기타"]
MASCOTS = {
    "scan": "checki_mascot_scan.png",
    "search": "checki_mascot_search.png",
    "wait": "checki_mascot_wait.png",
    "chart": "checki_mascot_chart.png",
}
NAV = ["홈", "구매체크", "소비분석", "MY"]
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


def norm_name(value):
    return re.sub(r"[\s\W_]+", "", str(value or "").lower())


def get_setting(name, default):
    """예산/저금 목표: 새 테이블 없이 URL 파라미터에 저장해 재접속 시에도 유지."""
    if name not in st.session_state:
        value = number(st.query_params.get(name))
        st.session_state[name] = value if value > 0 else default
    return st.session_state[name]


def set_setting(name, value):
    st.session_state[name] = number(value)
    st.query_params[name] = str(number(value))


def mascot(which, width=145):
    path = MASCOTS.get(which)
    if not path or not os.path.isfile(path):
        return
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    st.markdown(
        f'<div class="mascot"><img src="data:image/png;base64,{encoded}" '
        f'style="width:min({width}px,40vw);max-height:160px;object-fit:contain"></div>',
        unsafe_allow_html=True,
    )


def preview_image(image):
    try:
        im = image.copy()
        buf = BytesIO()
        if im.mode == "RGBA":
            im.save(buf, format="PNG")
            mime = "image/png"
        else:
            im.convert("RGB").save(buf, format="JPEG", quality=88)
            mime = "image/jpeg"
        encoded = base64.b64encode(buf.getvalue()).decode()
        st.markdown(f'<div class="preview"><img src="data:{mime};base64,{encoded}"></div>',
                    unsafe_allow_html=True)
    except Exception:
        st.image(image, width=300)


# ---------------- 스타일 ----------------
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css');
:root{--blue:#1689F8;--navy:#172C3F;--muted:#74889C;--line:#DFEAF3}
html,body,[class*="st-"],button,input,textarea{font-family:"Pretendard Variable",sans-serif!important}
.stApp{background:linear-gradient(165deg,#EEF8FF 0%,#F8FCFF 43%,#FFFFFF 100%);color:var(--navy)}
header[data-testid="stHeader"],#MainMenu,footer{display:none!important}
.block-container{max-width:860px!important;padding-top:.5rem!important;padding-bottom:5rem!important}
.brand{text-align:center;padding:14px 0 2px}
.brand strong{font-size:31px;letter-spacing:-2px;font-weight:900;color:var(--blue)}
.brand b{font-size:27px;letter-spacing:-2px;font-weight:900;color:var(--navy)}
.brand small{display:block;font-size:9px;letter-spacing:3px;font-weight:800;color:#8CA0B1;margin-top:4px}

/* 상단 메뉴: 세그먼트 탭 스타일 */
div[role="radiogroup"]{justify-content:center;gap:4px;flex-wrap:wrap}
div[role="radiogroup"] label{background:#fff;border:1px solid var(--line);border-radius:24px;
  padding:6px 14px!important;margin:0!important;font-weight:750;transition:all .15s}
div[role="radiogroup"] label > div:first-child{display:none}
div[role="radiogroup"] label:has(input:checked){background:var(--blue);border-color:var(--blue);
  box-shadow:0 4px 12px #1689F833}
div[role="radiogroup"] label:has(input:checked) p{color:#fff!important}

.hero{text-align:center;padding:24px 5px 8px}
.hero h1{font-size:29px;line-height:1.35;font-weight:900;letter-spacing:-1.6px;color:var(--navy);margin:0}
.hero h1 em{font-style:normal;color:var(--blue)}
.hero p{color:var(--muted);font-size:14px;line-height:1.7;margin-top:8px}
.mascot{text-align:center;margin:4px auto 12px}
.kicker{color:var(--blue);font-size:11.5px;font-weight:850;letter-spacing:1px;margin-bottom:6px}
.section{font-size:17px;font-weight:850;color:#18354A;margin:26px 0 8px;letter-spacing:-.5px}
.section small{display:block;font-size:12.5px;font-weight:600;color:var(--muted);margin-top:2px;letter-spacing:0}

.card{background:#fff;border:1px solid var(--line);border-radius:20px;padding:18px 20px;margin:10px 0;box-shadow:0 9px 28px #1C6AA40C}
.card h3{margin:0 0 6px;font-size:16.5px;font-weight:850;color:#18354A}
.card p{margin:0;color:#6C8396;line-height:1.6;font-size:13.5px}

.stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}
.stat{background:#fff;border:1px solid var(--line);border-radius:16px;padding:13px 8px;text-align:center}
.stat b{display:block;font-size:18px;font-weight:900;color:var(--navy);letter-spacing:-.5px}
.stat span{font-size:11.5px;color:var(--muted);font-weight:700}
.stat.blue b{color:var(--blue)} .stat.green b{color:#0E8F6E} .stat.red b{color:#D24646}

.flow{display:flex;flex-direction:column;gap:8px;margin:8px 0}
.flow-step{display:flex;gap:12px;align-items:flex-start;background:#fff;border:1px solid var(--line);border-radius:16px;padding:13px 14px}
.flow-step .n{flex:0 0 28px;height:28px;border-radius:50%;background:#E5F2FF;color:var(--blue);font-weight:900;
  display:flex;align-items:center;justify-content:center;font-size:13px}
.flow-step b{font-size:14.5px;color:var(--navy)}
.flow-step p{margin:2px 0 0;font-size:12.5px;color:var(--muted);line-height:1.5}

.result{background:#fff;border:1px solid var(--line);border-radius:22px;padding:20px;margin:12px 0;box-shadow:0 9px 28px #1C6AA410}
.result-head{display:flex;gap:16px;align-items:center}
.result-head h3{margin:8px 0 0;font-size:16px;line-height:1.5;font-weight:800;color:var(--navy)}
.gauge{width:86px;height:86px;border-radius:50%;flex:0 0 86px;display:flex;align-items:center;justify-content:center;
  background:conic-gradient(var(--c) calc(var(--p) * 1%),#E8F0F6 0)}
.gauge span{width:66px;height:66px;border-radius:50%;background:#fff;display:flex;flex-direction:column;
  align-items:center;justify-content:center;font-weight:900;font-size:23px;color:var(--navy);line-height:1.1}
.gauge small{font-size:10px;color:var(--muted);font-weight:700}
.level{display:inline-block;padding:4px 11px;border-radius:20px;font-size:12.5px;font-weight:850}
.level.low{background:#E3F7EE;color:#14855A}.level.medium{background:#FFF4D6;color:#A86E00}.level.high{background:#FFE6E6;color:#C23B3B}
.kv{margin:14px 0 0}
.kv dt{font-size:12px;font-weight:850;color:var(--muted);margin-top:12px}
.kv dd{margin:4px 0 0;font-size:14.5px;line-height:1.6;color:var(--navy)}
.tags{display:flex;flex-wrap:wrap;gap:6px}
.tag{background:#F1F6FA;border:1px solid var(--line);border-radius:20px;padding:3px 10px;font-size:12.5px;font-weight:700;color:#4A6378}
.tag.warn{background:#FFF1F1;border-color:#F4D2D2;color:#B03C3C}

.rec{display:flex;align-items:center;gap:12px;border-radius:16px;padding:14px 15px}
.rec.BUY{background:#EAF8F1}.rec.HOLD{background:#EEF6FF}.rec.RECONSIDER{background:#FFF0F0}
.rec .icon{font-size:28px}
.rec b{font-size:16.5px;color:var(--navy);display:block}
.rec span{font-size:13.5px;color:#4E6578;line-height:1.55}
.chips{display:flex;flex-direction:column;gap:7px;margin-top:12px}
.chip{border-radius:13px;padding:10px 12px;font-size:13.5px;line-height:1.5;font-weight:600}
.chip.high{background:#FFF0F0;color:#A23636}.chip.mid{background:#FFF8E6;color:#8A5B00}
.chip.info{background:#EEF6FF;color:#245A8A}.chip.good{background:#EAF8F1;color:#1E7A52}

.bars{background:#fff;border:1px solid var(--line);border-radius:18px;padding:14px 16px;margin:8px 0}
.bar-row{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:13px}
.bar-row .lb{flex:0 0 82px;color:#4A6378;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar-row .tr{flex:1;height:10px;background:#EDF3F8;border-radius:10px;overflow:hidden}
.bar-row .fl{height:100%;background:linear-gradient(90deg,#4DAEFF,#1689F8);border-radius:10px}
.bar-row .fl.late{background:linear-gradient(90deg,#9A8CFF,#6A5CF0)}
.bar-row .vl{flex:0 0 auto;min-width:62px;text-align:right;font-weight:800;color:var(--navy)}

.budget{background:#fff;border:1px solid var(--line);border-radius:20px;padding:18px;margin:8px 0}
.budget .top{display:flex;justify-content:space-between;align-items:flex-end}
.budget .top b{font-size:22px;font-weight:900;color:var(--navy)}
.budget .top span{font-size:12.5px;color:var(--muted);font-weight:700}
.progress-bg{height:12px;border-radius:20px;background:#E3EDF3;overflow:hidden;margin:12px 0 6px}
.progress-fill{height:100%;background:linear-gradient(90deg,#25BFA4,#1689F8);border-radius:20px}
.progress-fill.over{background:linear-gradient(90deg,#FF9A7A,#E25555)}

.rcard{background:#fff;border:1px solid var(--line);border-radius:18px;padding:15px 16px;margin:10px 0 6px}
.rtop{display:flex;justify-content:space-between;gap:8px;align-items:center}
.rtop b{font-size:15.5px;color:var(--navy);font-weight:850}
.rmeta{font-size:12.5px;color:var(--muted);margin-top:4px}
.rsum{font-size:13px;color:#4E6578;margin-top:8px;line-height:1.5}
.badge{flex:0 0 auto;display:inline-block;padding:3px 10px;border-radius:20px;font-size:11.5px;font-weight:850}
.badge.HOLD{background:#E5F2FF;color:#1468C2}.badge.BUY{background:#EEF1F4;color:#55687A}
.badge.NOT_BUY{background:#E3F7EE;color:#14855A}.badge.PENDING{background:#FFF4D6;color:#A86E00}

.pig{border-radius:24px;padding:24px;background:linear-gradient(130deg,#DFF9F1,#E8F6FF);border:1px solid #CBEDE9;text-align:center;margin:10px 0}
.pig .amount{font-size:38px;font-weight:900;color:#087E75;letter-spacing:-2px}
.pig .sub{font-size:13px;color:#527E80}
.pig .emoji{font-size:42px}
.hold{background:#EFF7FF;border:1px solid #D4E9FC;border-radius:17px;padding:15px;margin:6px 0;text-align:center}
.hold .clock{font-size:32px;font-weight:900;color:var(--blue);font-variant-numeric:tabular-nums}
.hold small{color:var(--muted)}
.alert{background:#FFF8E6;border:1px solid #F3E2B0;border-radius:16px;padding:13px 15px;font-size:14px;font-weight:700;color:#7A5300;margin:10px 0}

.preview{text-align:center;margin:12px 0}
.preview img{max-width:min(320px,88vw);max-height:400px;border-radius:16px;border:1px solid var(--line);box-shadow:0 8px 22px #1C6AA416}
.stButton>button{border-radius:13px!important;min-height:46px;font-weight:750!important}
.stButton>button[kind="primary"]{background:linear-gradient(120deg,#1689F8,#4DAEFF)!important;border:0!important}
.stTextInput input,.stNumberInput input{border-radius:12px!important}
[data-testid="stFileUploaderDropzone"]{border-radius:15px;background:#F8FBFE}
[data-testid="stExpander"]{border-radius:16px!important;background:#fff}
@media(max-width:768px){
.block-container{padding:0 .85rem 4rem!important}
.brand strong{font-size:27px}.brand b{font-size:24px}
.hero{padding-top:18px}.hero h1{font-size:24px}
.stat b{font-size:15.5px}.stat span{font-size:10.5px}
.gauge{width:76px;height:76px;flex-basis:76px}.gauge span{width:58px;height:58px;font-size:20px}
.pig .amount{font-size:31px}
.preview img{max-width:240px;max-height:320px}
}
</style>
""", unsafe_allow_html=True)

# ---------------- 연결 (기존 Secrets 이름 유지) ----------------
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("Streamlit Secrets에 GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY가 필요합니다.")
    st.stop()


@st.cache_resource
def get_clients(gemini_key, supabase_url, supabase_key):
    return genai.Client(api_key=gemini_key), create_client(supabase_url, supabase_key)


try:
    gemini, supabase = get_clients(GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY)
except Exception as exc:
    st.error(f"서비스 연결 실패: {exc}")
    st.stop()

if "user_id" not in st.session_state:
    try:
        uid = st.query_params.get("uid")
        if isinstance(uid, list):
            uid = uid[0]
        if uid:
            uuid.UUID(str(uid))
            st.session_state.user_id = str(uid)
        else:
            st.session_state.user_id = str(uuid.uuid4())
            st.query_params["uid"] = st.session_state.user_id
    except Exception:
        st.session_state.user_id = str(uuid.uuid4())
user_id = st.session_state.user_id


# ---------------- DB (기존 테이블 2개만 사용) ----------------
def get_expenses():
    try:
        response = (supabase.table("checki_expenses").select("*")
                    .eq("user_id", user_id).order("created_at", desc=True).execute())
        return response.data or []
    except Exception as exc:
        st.warning(f"소비 기록을 불러오지 못했어요: {exc}")
        return []


def get_records():
    try:
        response = (supabase.table("checki_records").select("*")
                    .eq("user_id", user_id).order("created_at", desc=True).execute())
        return response.data or []
    except Exception as exc:
        st.warning(f"체키 기록을 불러오지 못했어요: {exc}")
        return []


def add_expense(category, item_name, amount):
    try:
        data = {
            "user_id": user_id, "category": category, "item_name": item_name,
            "amount": number(amount), "purchased_at": now_kst().date().isoformat(),
            "created_at": iso_now(),
        }
        supabase.table("checki_expenses").insert(data).execute()
        return True
    except Exception as exc:
        st.error(f"소비 기록 저장 실패: {exc}")
        return False


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
    try:
        response = supabase.table("checki_records").insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as exc:
        if decision != "PENDING":
            st.error(f"체키 기록 저장 실패: {exc}")
        return None


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
    try:
        supabase.table("checki_records").update(data).eq("id", record_id).eq("user_id", user_id).execute()
        return True
    except Exception as exc:
        st.error(f"체키 기록 변경 실패: {exc}")
        return False


def finalize_latest(decision, saved_amount=0):
    result = st.session_state.get("latest_analysis")
    if not result:
        return False
    category = st.session_state.get("latest_category", "기타")
    existing = st.session_state.get("latest_record")
    if existing and existing.get("id"):
        return update_record(existing["id"], decision, saved_amount)
    return insert_record(result, category, decision, saved_amount) is not None


def clear_latest():
    for key in ("latest_analysis", "latest_record", "latest_category",
                "purchase_action", "latest_buy_amount"):
        st.session_state.pop(key, None)


def go(page):
    """버튼 처리 후 페이지 이동 (위젯 생성 후 nav 직접 변경 오류 방지)."""
    st.session_state["pending_nav"] = page


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
    match = re.search(rf"(?m)^\s*\**{re.escape(field)}\**\s*:\s*(.*)$", text, re.I)
    return match.group(1).strip() if match else default


def parse_price(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else 0


def call_gemini(contents):
    response = gemini.models.generate_content(
        model=MODEL, contents=contents,
        config={"thinking_config": {"thinking_level": "minimal"}},
    )
    raw = getattr(response, "text", None)
    if not raw:
        raise RuntimeError("AI 응답이 비어 있습니다.")
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
아래 형식을 정확히 지키고, 한 줄당 한 항목으로 답하라.
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
    if level not in ("LOW", "MEDIUM", "HIGH"):
        level = "MEDIUM"
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
def hero(title, description):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{description}</p></div>',
                unsafe_allow_html=True)


def section(title, sub=""):
    sub_html = f"<small>{safe(sub)}</small>" if sub else ""
    st.markdown(f'<div class="section">{safe(title)}{sub_html}</div>', unsafe_allow_html=True)


def card(title, description):
    st.markdown(f'<div class="card"><h3>{safe(title)}</h3><p>{safe(description)}</p></div>',
                unsafe_allow_html=True)


def stat_grid(items):
    cells = "".join(f'<div class="stat {cls}"><b>{safe(v)}</b><span>{safe(k)}</span></div>'
                    for k, v, cls in items)
    st.markdown(f'<div class="stat-grid">{cells}</div>', unsafe_allow_html=True)


def chips_html(signals):
    icons = {"high": "⚠️", "mid": "💡", "info": "📊", "good": "✅"}
    return '<div class="chips">' + "".join(
        f'<div class="chip {lv}">{icons.get(lv, "•")} {safe(t)}</div>' for lv, t in signals) + "</div>"


def bars_html(items, fmt=money, highlight=()):
    if not items:
        return ""
    mx = max(v for _, v in items) or 1
    rows = "".join(
        f'<div class="bar-row"><div class="lb">{safe(k)}</div><div class="tr">'
        f'<div class="fl{" late" if k in highlight else ""}" style="width:{v / mx * 100:.1f}%"></div></div>'
        f'<div class="vl">{fmt(v)}</div></div>' for k, v in items)
    return f'<div class="bars">{rows}</div>'


def budget_box(p):
    budget, spent = p["budget"], p["month_spent"]
    pct = spent / budget * 100 if budget else 0
    left = budget - spent
    left_txt = f"남은 예산 {money(left)}" if left >= 0 else f"{money(-left)} 초과"
    st.markdown(
        f'<div class="budget"><div class="kicker">{p["now"].month}월 예산</div>'
        f'<div class="top"><b>{money(spent)}</b><span>/ {money(budget)}</span></div>'
        f'<div class="progress-bg"><div class="progress-fill{" over" if pct > 100 else ""}" '
        f'style="width:{min(100, pct):.1f}%"></div></div>'
        f'<div class="rmeta">{pct:.0f}% 사용 · {left_txt}</div></div>',
        unsafe_allow_html=True,
    )


def piggy_bank(records, compact=False):
    completed = [r for r in records if r.get("decision") == "NOT_BUY"]
    total = sum(number(r.get("saved_amount")) for r in completed)
    goal = max(1, get_setting("cfg_goal", DEFAULT_GOAL))
    pct = min(100, total / goal * 100)
    st.markdown(
        f'<div class="pig"><div class="emoji">🐷</div><div class="kicker">CHECKI SAVINGS</div>'
        f'<div class="amount">{money(total)}</div>'
        f'<div class="sub">구매하지 않기로 결정한 금액 · {len(completed)}건</div>'
        f'<div class="progress-bg"><div class="progress-fill" style="width:{pct:.1f}%"></div></div>'
        f'<div class="sub">저금 목표 {money(goal)} · 달성률 {pct:.1f}%</div></div>',
        unsafe_allow_html=True,
    )
    if compact:
        return
    with st.expander("🎯 저금 목표 설정"):
        new_goal = st.number_input("목표 금액 (원)", min_value=1000, step=10000,
                                   value=int(goal), key="goal_input")
        if st.button("목표 적용", key="goal_save"):
            set_setting("cfg_goal", new_goal)
            st.rerun()
    st.caption("실제 계좌 잔액이 아니라, 구매 포기 금액을 합산한 가상 저금통입니다.")
    for r in completed[:5]:
        card(f"💚 {r.get('product_name') or '상품'} · +{money(r.get('saved_amount'))}",
             "구매하지 않기로 결정했어요")


def record_card(r):
    decision = str(r.get("decision") or "PENDING")
    created = parse_date(r.get("created_at"))
    when = f"{created:%m.%d %H:%M}" if created else ""
    meta = " · ".join(x for x in [r.get("category") or "기타", money(r.get("product_price")),
                                  f"위험도 {r.get('risk_level') or '미확인'}", when] if x)
    summary = r.get("one_line_summary")
    st.markdown(
        f'<div class="rcard"><div class="rtop"><b>{safe(r.get("product_name") or "상품")}</b>'
        f'<span class="badge {decision}">{DECISION_BADGE.get(decision, decision)}</span></div>'
        f'<div class="rmeta">{safe(meta)}</div>'
        + (f'<div class="rsum">{safe(summary)}</div>' if summary else "") + "</div>",
        unsafe_allow_html=True,
    )


def _hold_timer_body(until_iso):
    until = parse_date(until_iso)
    secs = max(0, int((until - now_kst()).total_seconds())) if until else 0
    if secs <= 0:
        st.rerun()
    st.markdown(
        f'<div class="hold"><div>⏱️ 구매 보류 중</div>'
        f'<div class="clock">{secs // 60:02d}:{secs % 60:02d}</div>'
        f'<small>타이머가 끝나면 구매 여부를 결정할 수 있어요.</small></div>',
        unsafe_allow_html=True,
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
st.markdown('<div class="brand"><strong>CHECKI</strong> &nbsp; <b>| 체키</b>'
            '<small>CHECK BEFORE YOU BUY</small></div>', unsafe_allow_html=True)

if "pending_nav" in st.session_state:
    st.session_state["nav"] = st.session_state.pop("pending_nav")
if st.session_state.get("nav") not in NAV:
    st.session_state["nav"] = "홈"
page = st.radio("메뉴", NAV, horizontal=True, label_visibility="collapsed", key="nav")

expenses, records = get_expenses(), get_records()
profile = build_profile(expenses, records)

# ---------------- 홈 ----------------
if page == "홈":
    hero('사기 전에, <em>체키</em> 해보세요.',
         "쇼핑 화면 속 구매 유도 요소와 <b>나의 소비 패턴</b>을 함께 분석해<br>"
         "지금 사도 괜찮은지 알려드려요.")
    mascot("scan", 140)

    if profile["has_data"]:
        stat_grid([
            ("이번 달 소비", money(profile["month_spent"]), "blue"),
            ("아낀 금액", money(profile["saved"]), "green"),
            ("보류 중", f"{profile['decisions']['HOLD']}건", ""),
        ])
        ready = [r for r in records if r.get("decision") == "HOLD"
                 and (parse_date(r.get("hold_until")) or now_kst()) <= now_kst()]
        if ready:
            st.markdown(f'<div class="alert">⏰ 30분이 지난 보류 상품이 {len(ready)}개 있어요. '
                        f'MY에서 결정해주세요.</div>', unsafe_allow_html=True)

    if st.button("🔎 지금 구매체크 시작하기", type="primary", use_container_width=True):
        go("구매체크")
        st.rerun()

    section("체키는 이렇게 판단해요", "AI 소비 분석 흐름")
    steps = [
        ("소비 데이터 수집", "체크한 상품의 가격·카테고리, 구매 금액과 시간을 기록해요."),
        ("분류·축적", "카테고리·시간대·구매/보류/포기 결과별로 차곡차곡 쌓아요."),
        ("개인 소비 패턴 분석", "예산 대비 소비, 반복 구매, 심야 구매 습관을 찾아요."),
        ("구매 직전 맞춤 판단", "화면 속 유도 요소 + 내 소비 패턴으로 지금 사도 될지 알려줘요."),
        ("결과 반영·소비 리포트", "선택 결과가 다음 판단과 AI 소비 리포트에 반영돼요."),
    ]
    st.markdown('<div class="flow">' + "".join(
        f'<div class="flow-step"><div class="n">{i}</div><div><b>{t}</b><p>{d}</p></div></div>'
        for i, (t, d) in enumerate(steps, 1)) + "</div>", unsafe_allow_html=True)

# ---------------- 구매체크 ----------------
elif page == "구매체크":
    hero('구매 전 <em>체키</em>', "쇼핑 화면을 캡처하거나 상품 링크를 넣어주세요.")

    product_name = st.text_input("상품명", placeholder="예: 무선 이어폰")
    c1, c2 = st.columns(2)
    with c1:
        category = st.selectbox("카테고리", CATEGORIES)
    with c2:
        user_price = st.number_input("가격 (선택)", min_value=0, step=1000, value=0,
                                     help="화면에서 가격을 못 읽을 때 사용해요.")
    input_type = st.radio("분석 방법", ["스크린샷", "상품 링크"], horizontal=True)
    image, product_url = None, None
    if input_type == "스크린샷":
        uploaded_file = st.file_uploader("쇼핑 화면 업로드", type=["png", "jpg", "jpeg", "webp"])
        if uploaded_file:
            try:
                image = Image.open(uploaded_file)
                preview_image(image)
            except Exception:
                st.warning("이미지 파일을 열지 못했어요.")
    else:
        product_url = st.text_input("상품 링크", placeholder="https://...")

    cat_spent = profile["month_by_cat"].get(category, 0)
    st.caption(f"📊 함께 반영할 내 데이터 · 이번 달 {category} {money(cat_spent)} · "
               f"남은 예산 {money(profile['budget_left'])} · 지금 {time_slot(profile['now'].hour)} 시간대")

    if st.button("체키로 분석하기", type="primary", use_container_width=True):
        if not product_name.strip():
            st.warning("상품명을 입력해주세요.")
        elif input_type == "스크린샷" and image is None:
            st.warning("쇼핑 화면을 올려주세요.")
        elif input_type == "상품 링크" and not (product_url or "").strip():
            st.warning("상품 링크를 입력해주세요.")
        else:
            try:
                page_text = None
                if input_type == "상품 링크":
                    with st.spinner("상품 페이지를 확인하고 있어요..."):
                        page_text = read_url(product_url.strip())
                pre_signals = personal_signals(profile, product_name, category, number(user_price))
                context = profile_to_text(profile, category, number(user_price), pre_signals)
                with st.spinner("구매 화면과 내 소비 패턴을 함께 분석하고 있어요..."):
                    result = analyze_product(product_name, category, image, page_text,
                                             number(user_price), context)
                result["signals"] = personal_signals(profile, result["product_name"],
                                                     category, number(result["price"]))
                st.session_state["latest_analysis"] = result
                st.session_state["latest_category"] = category
                st.session_state["latest_record"] = insert_record(result, category, "PENDING")
                st.session_state.pop("purchase_action", None)
            except Exception as exc:
                st.error(f"분석을 완료하지 못했어요: {exc}")
                if input_type == "상품 링크":
                    st.info("상품 페이지 접근이 차단된 경우 스크린샷 분석을 이용해주세요.")

    result = st.session_state.get("latest_analysis")
    if result:
        mascot("search", 120)
        level = result["risk_level"]
        cls = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high"}[level]
        name = {"LOW": "낮음", "MEDIUM": "주의", "HIGH": "높음"}[level]
        color = {"LOW": "#22B07D", "MEDIUM": "#F0A500", "HIGH": "#E25555"}[level]
        score = number(result["risk_score"])
        parts = [x.strip() for x in re.split(r"[,，·/]", result["detected"]) if x.strip()]
        no_issue = not parts or parts[0] in ("없음", "확인 필요")
        tags = "".join(f'<span class="tag{"" if no_issue else " warn"}">{safe(x)}</span>'
                       for x in (parts or ["없음"]))
        st.markdown(
            f'<div class="result"><div class="kicker">STEP 1 · 구매 화면 분석</div>'
            f'<div class="result-head"><div class="gauge" style="--p:{score};--c:{color}">'
            f'<span>{score}<small>/ 100</small></span></div>'
            f'<div><span class="level {cls}">구매 유도 위험 {name}</span>'
            f'<h3>{safe(result["summary"])}</h3></div></div>'
            f'<dl class="kv"><dt>발견된 유도 요소</dt><dd><div class="tags">{tags}</div></dd>'
            f'<dt>구매 전 확인할 점</dt><dd>{safe(result["advice"])}</dd></dl></div>',
            unsafe_allow_html=True,
        )
        rec = result.get("recommend", "HOLD")
        icon, rec_title = RECOMMEND[rec]
        st.markdown(
            f'<div class="result"><div class="kicker">STEP 2 · 나에게 맞춘 판단</div>'
            f'<div class="rec {rec}"><div class="icon">{icon}</div><div><b>{rec_title}</b>'
            f'<span>{safe(result.get("personal"))}</span></div></div>'
            f'{chips_html(result.get("signals", []))}</div>',
            unsafe_allow_html=True,
        )
        with st.expander("🔍 AI가 참고한 내 소비 데이터"):
            st.code(result.get("context") or "데이터 없음", language=None)

        if number(result["price"]) > 0:
            st.info(f"확인된 상품 가격: **{money(result['price'])}**")
        else:
            st.info("가격을 확인하지 못했어요. 구매 포기 시 절약 금액은 0원으로 기록됩니다.")

        section("어떻게 할까요?", "선택 결과는 다음 분석과 소비 리포트에 반영돼요.")
        if st.session_state.get("purchase_action") == "BUY":
            amount = st.number_input("실제로 결제할 금액", min_value=0, step=1000,
                                     value=number(result["price"]), key="latest_buy_amount")
            if st.button("구매 기록 저장", type="primary", use_container_width=True):
                if finalize_latest("BUY"):
                    if add_expense(st.session_state.get("latest_category", "기타"),
                                   result["product_name"], amount):
                        clear_latest()
                        st.session_state["notice"] = "구매 기록을 저장했어요."
                        go("소비분석")
                        st.rerun()
                    else:
                        st.warning("체키 기록은 구매 완료로 변경됐지만 소비 내역 저장에 실패했어요.")
            if st.button("이전 선택으로 돌아가기", use_container_width=True):
                st.session_state.pop("purchase_action", None)
                st.rerun()
        else:
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("⏱️ 30분 보류", use_container_width=True,
                             type="primary" if rec == "HOLD" else "secondary"):
                    if finalize_latest("HOLD"):
                        clear_latest()
                        st.session_state["notice"] = "30분 보류를 시작했어요."
                        go("MY")
                        st.rerun()
            with b2:
                if st.button("🙅 사지 않기", use_container_width=True,
                             type="primary" if rec == "RECONSIDER" else "secondary"):
                    saved = number(result["price"])
                    if finalize_latest("NOT_BUY", saved):
                        clear_latest()
                        st.session_state["notice"] = f"{money(saved)}을(를) 저금통에 기록했어요."
                        go("MY")
                        st.rerun()
            with b3:
                if st.button("🛒 구매하기", use_container_width=True,
                             type="primary" if rec == "BUY" else "secondary"):
                    st.session_state["purchase_action"] = "BUY"
                    st.rerun()

# ---------------- 소비분석 ----------------
elif page == "소비분석":
    hero('나의 <em>소비 리포트</em>', "쌓인 기록으로 나의 소비 패턴을 분석해요.")
    mascot("chart", 120)
    p = profile
    left = p["budget_left"]
    stat_grid([
        ("이번 달 소비", money(p["month_spent"]), "blue"),
        ("남은 예산" if left >= 0 else "예산 초과", money(abs(left)), "" if left >= 0 else "red"),
        ("아낀 금액", money(p["saved"]), "green"),
    ])

    section("💰 예산")
    budget_box(p)
    with st.expander("월 예산 설정"):
        new_budget = st.number_input("월 예산 (원)", min_value=10000, step=50000,
                                     value=int(p["budget"]), key="budget_input")
        if st.button("예산 적용", key="budget_save"):
            set_setting("cfg_budget", new_budget)
            st.rerun()

    section("🗂️ 카테고리별 소비", "이번 달")
    if p["month_by_cat"]:
        st.markdown(bars_html(p["month_by_cat"].most_common()), unsafe_allow_html=True)
    else:
        st.info("이번 달 소비 기록이 없어요.")

    section("🕒 구매 시간대", "전체 구매 기준")
    if p["timed"]:
        slot_items = [(n, p["slots"].get(n, 0)) for n, _, _ in TIME_SLOTS]
        st.markdown(bars_html(slot_items, fmt=lambda v: f"{v}회", highlight=("새벽", "밤")),
                    unsafe_allow_html=True)
        st.caption(f"심야(밤 10시~새벽 5시) 구매 비율 {p['late_ratio'] * 100:.0f}%")
    else:
        st.info("구매 시간 기록이 없어요.")

    section("🧠 구매 결정 습관")
    d = p["decisions"]
    stat_grid([("구매", f"{d['BUY']}회", ""), ("보류 중", f"{d['HOLD']}회", "blue"),
               ("포기", f"{d['NOT_BUY']}회", "green")])
    if p["held_done"]:
        st.caption(f"30분 보류 후 결국 사지 않은 비율 {p['hold_drop'] / p['held_done'] * 100:.0f}% "
                   f"({p['hold_drop']}/{p['held_done']}건)")

    section("🔁 반복 구매 · 정기결제")
    items = [("mid", f"최근 90일 '{n}' {c}회 구매") for n, c in p["repeats"][:5]]
    if p["subs_month"]:
        items.append(("info", f"이번 달 정기결제 {len(p['subs_month'])}건 · {money(p['subs_total'])}"))
    st.markdown(chips_html(items or [("good", "반복 구매나 정기결제 기록이 없어요.")]),
                unsafe_allow_html=True)

    section("✨ AI 소비 리포트", "위 데이터를 바탕으로 AI가 요약해요.")
    if st.button("리포트 생성하기", type="primary", use_container_width=True,
                 disabled=not expenses):
        try:
            with st.spinner("소비 패턴을 정리하고 있어요..."):
                st.session_state["ai_report"] = ai_report(p)
        except Exception as exc:
            st.error(f"리포트를 만들지 못했어요: {exc}")
    if not expenses:
        st.caption("소비 기록이 있어야 리포트를 만들 수 있어요.")
    if st.session_state.get("ai_report"):
        with st.container(border=True):
            st.markdown(st.session_state["ai_report"])

    section("🐷 체키 저금통")
    piggy_bank(records, compact=False)

    section("🧾 최근 소비")
    with st.expander("➕ 소비 직접 기록하기"):
        e_cat = st.selectbox("카테고리", CATEGORIES, key="e_cat")
        e_name = st.text_input("항목", key="e_name", placeholder="예: 점심, 넷플릭스")
        e_amt = st.number_input("금액 (원)", min_value=0, step=1000, key="e_amt")
        if st.button("기록 추가", key="e_save", use_container_width=True):
            if e_name.strip() and e_amt > 0:
                if add_expense(e_cat, e_name.strip(), e_amt):
                    st.session_state["notice"] = "소비를 기록했어요."
                    st.rerun()
            else:
                st.warning("항목과 금액을 입력해주세요.")
    if not expenses:
        st.info("아직 등록된 소비가 없어요.")
    for x in expenses[:10]:
        t = expense_time(x)
        when = f" · {t:%m.%d %H:%M}" if t else ""
        card(str(x.get("item_name") or "상품"),
             f"{x.get('category') or '기타'} · {money(x.get('amount'))}{when}")

# ---------------- MY ----------------
elif page == "MY":
    hero('나의 <em>체키 기록</em>', "보류 중인 상품과 구매 결정 내역을 확인해보세요.")
    if not records:
        mascot("wait", 110)
        st.info("아직 체키 기록이 없어요. 구매체크를 먼저 해보세요.")
    else:
        # 보류 중 → 선택 대기 → 결정 완료 순서
        order = {"HOLD": 0, "PENDING": 1}
        shown = sorted(records[:30], key=lambda r: order.get(r.get("decision"), 2))
        for record in shown:
            rid = record.get("id")
            decision = str(record.get("decision") or "PENDING")
            product = str(record.get("product_name") or "상품")
            price = number(record.get("product_price"))
            record_card(record)

            if decision == "HOLD":
                until = parse_date(record.get("hold_until"))
                seconds = max(0, int((until - now_kst()).total_seconds())) if until else 0
                if seconds > 0:
                    hold_timer(record.get("hold_until"))
                    if not LIVE_TIMER and st.button("남은 시간 새로고침", key=f"refresh_{rid}"):
                        st.rerun()
                else:
                    st.success("30분이 지났어요. 지금도 꼭 필요한가요?")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🙅 사지 않았어요", key=f"no_{rid}", use_container_width=True):
                            if update_record(rid, "NOT_BUY", price):
                                st.session_state["notice"] = f"{money(price)}을(를) 저금통에 기록했어요."
                                st.rerun()
                    with col2:
                        if st.button("🛒 구매했어요", key=f"yes_{rid}", use_container_width=True):
                            st.session_state["buy_record"] = rid
                    if st.session_state.get("buy_record") == rid:
                        actual = st.number_input("실제 결제 금액", min_value=0, step=1000,
                                                 value=price, key=f"amount_{rid}")
                        if st.button("구매 내역 저장", key=f"save_{rid}", type="primary",
                                     use_container_width=True):
                            if update_record(rid, "BUY"):
                                if add_expense(str(record.get("category") or "기타"), product, actual):
                                    st.session_state.pop("buy_record", None)
                                    st.session_state["notice"] = "구매 내역을 저장했어요."
                                    st.rerun()
            elif decision == "NOT_BUY":
                st.caption(f"💚 {money(record.get('saved_amount'))} 절약")
            elif decision == "PENDING":
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⏱️ 30분 보류", key=f"pending_hold_{rid}", use_container_width=True):
                        if update_record(rid, "HOLD"):
                            st.rerun()
                with col2:
                    if st.button("🙅 사지 않기", key=f"pending_no_{rid}", use_container_width=True):
                        if update_record(rid, "NOT_BUY", price):
                            st.rerun()
    section("🐷 체키 저금통")
    piggy_bank(records, compact=True)

if st.session_state.get("notice"):
    st.toast(st.session_state.pop("notice"))
