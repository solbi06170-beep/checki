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
    name = MASCOTS.get(which)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name) if name else ""
    if not path or not os.path.isfile(path):
        path = name or ""
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
# 디자인(CSS)은 같은 폴더의 checki_style.css에서 불러온다 (app.py 길이를 줄여 붙여넣기 잘림 방지)
# 아이콘(Material Symbols) 요소에는 폰트를 덮어쓰지 않는다 → '_arrow_right' 글자 깨짐 방지
APP_DIR = os.path.dirname(os.path.abspath(__file__))


def load_css():
    for path in (os.path.join(APP_DIR, "checki_style.css"), "checki_style.css"):
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except OSError:
            continue
    return ""


st.markdown(f"<style>{load_css()}</style>", unsafe_allow_html=True)

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
        ("전자기기", "무선 이어폰", 42000, 0.30, 1), ("식품", "배달 치킨", 21000, 0.38, 19),
        ("구독서비스", "유튜브 프리미엄", 14900, 0.45, 9), ("패션/의류", "운동화", 69000, 0.55, 19),
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
    before_rows = [("패션/의류", "셔츠", 59000, 10, 21), ("식품", "장보기", 56000, 15, 18),
                   ("패션/의류", "원피스", 89000, 6, 23), ("식품", "배달 치킨", 25000, 8, 23),
                   ("식품", "배달 치킨", 24000, 18, 0), ("전자기기", "무선 충전기", 39000, 20, 1),
                   ("패션/의류", "모자", 45000, 32, 13), ("식품", "배달 피자", 27000, 40, 23)]
    for cat, name, amt, before, hour in before_rows:
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
    lv, lv_icon, lv_name, lv_pct, lv_left = checker_level(total)
    html_block(
        f'<div class="acct"><div class="no">CHECKI 가상 저축계좌 · 1004-28-{tail}</div>'
        f'<div class="nm">체키 저축계좌</div><div class="bal">{money(total)}</div>'
        f'<div class="bar"><i style="width:{pct:.0f}%"></i></div>'
        f'<div class="sub">목표 {money(goal)} · {pct:.0f}% 달성 · 입금 {len(completed)}건</div>'
        f'<div class="em float">🐷</div></div>'
        f'<div class="lv"><div class="badge-lv">{lv_icon}</div><div class="tx"><b>Lv.{lv} {lv_name}</b>'
        f'<span>{"최고 레벨이에요! 정말 멋져요" if lv_left <= 0 else f"다음 레벨까지 {money(lv_left)} 더 모으면 돼요"}</span>'
        f'<div class="pb"><i style="width:{lv_pct:.0f}%"></i></div></div></div>'
        '<div class="mflow"><span>🙅 구매 포기</span>→<span>💰 절약 금액 누적</span>→<span>🏦 가상 저축계좌 반영</span></div>'
    )
    return goal, completed


LEVELS = [(0, "🌱", "새싹 체커"), (30000, "🔍", "똑똑 체커"), (100000, "💎", "알뜰 체커"), (200000, "👑", "마스터 체커")]


def checker_level(saved):
    idx = max(i for i, (need, _, _) in enumerate(LEVELS) if saved >= need)
    _, icon, name = LEVELS[idx]
    if idx + 1 < len(LEVELS):
        nxt = LEVELS[idx + 1][0]
        prev = LEVELS[idx][0]
        return idx + 1, icon, name, (saved - prev) / (nxt - prev) * 100, nxt - saved
    return idx + 1, icon, name, 100, 0


def collect_patterns(records):
    """기록에 저장된 AI 원문에서 지금까지 발견한 다크패턴을 유형별로 모은다 (다크패턴 도감)."""
    found = {k: Counter() for k in PATTERN_TYPES}
    for r in records:
        for x in parse_patterns(str(r.get("ai_result") or "")):
            found[x["type"]][x["name"]] += 1
    return found


def compare_months(p, records):
    """체키 이용 전·후 비교: 지난달 전체 vs 이번 달(지금까지)."""
    now = p["now"]
    cur_key = (now.year, now.month)
    prev_key = p["months"][-2]
    cur_spend = sum(p["hist"][cur_key].values())
    prev_spend = sum(p["hist"][prev_key].values())
    late = {cur_key: 0, prev_key: 0}
    for t, _ in p["purchases"]:
        k = (t.year, t.month)
        if k in late and t.hour in LATE_NIGHT:
            late[k] += 1
    saved_cur = 0
    for r in records:
        t = parse_date(r.get("decided_at")) or parse_date(r.get("created_at"))
        if r.get("decision") == "NOT_BUY" and t and (t.year, t.month) == cur_key:
            saved_cur += number(r.get("saved_amount"))
    return {"prev_label": f"{prev_key[1]}월", "cur_label": f"{cur_key[1]}월",
            "prev_spend": prev_spend, "cur_spend": cur_spend,
            "prev_late": late[prev_key], "cur_late": late[cur_key], "saved_cur": saved_cur}


def delta_html(prev, cur, fmt, lower_is_better=True):
    diff = cur - prev
    if diff == 0:
        return '<span class="dt same">변화 없음</span>'
    good = (diff < 0) == lower_is_better
    arrow = "▼" if diff < 0 else "▲"
    return f'<span class="dt {"good" if good else "bad"}">{arrow} {fmt(abs(diff))}</span>'


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
        sec("체키 이용 전·후 비교", sub="지난달 전체와 이번 달 지금까지를 비교해요.")
        cmp = compare_months(p, records)
        html_block(
            '<div class="list">'
            f'<div class="cmp"><span class="k">💳 지출</span><span class="v">{money(cmp["prev_spend"])} → <b>{money(cmp["cur_spend"])}</b></span>'
            f'{delta_html(cmp["prev_spend"], cmp["cur_spend"], money)}</div>'
            f'<div class="cmp"><span class="k">🌙 심야 구매</span><span class="v">{cmp["prev_late"]}회 → <b>{cmp["cur_late"]}회</b></span>'
            f'{delta_html(cmp["prev_late"], cmp["cur_late"], lambda v: f"{v}회")}</div>'
            f'<div class="cmp"><span class="k">🐷 체키로 아낀 돈</span><span class="v"><b>{money(cmp["saved_cur"])}</b></span>'
            f'<span class="dt good">이번 달</span></div></div>'
        )
        if cmp["prev_spend"] > cmp["cur_spend"]:
            talk("chart", "체키의 칭찬", f"{cmp['prev_label']}보다 {money(cmp['prev_spend'] - cmp['cur_spend'])} 덜 썼어요. 체키와 함께한 효과예요!")

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
            monthly = sum(r["amount"] for r in p["recurring"])
            html_block(
                f'<div class="subsum"><div><span>정기결제 {len(p["recurring"])}건 · 매달</span><b>{money(monthly)}</b></div>'
                f'<div><span>1년이면</span><b>{money(monthly * 12)}</b></div></div>'
            )
            st.caption("쓰지 않는 구독은 다음 결제일 전에 해지 조건을 확인해보세요.")
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
    found = collect_patterns(records)
    total_found = sum(sum(c.values()) for c in found.values())
    sec("다크패턴 도감", f"{sum(1 for c in found.values() if c)}/4 유형 발견",
        sub="체키가 지금까지 찾아낸 구매 유도 유형이에요.")
    cells = []
    for k, (color, desc) in PATTERN_TYPES.items():
        cnt = sum(found[k].values())
        top = ", ".join(n for n, _ in found[k].most_common(2))
        cells.append(f'<div class="dex{" on" if cnt else ""}" style="--c:{color}"><div class="dn">{cnt}</div>'
                     f'<b>{k}</b><span>{safe(top) if cnt else "아직 발견하지 못했어요"}</span></div>')
    html_block(f'<div class="dexgrid">{"".join(cells)}</div>')
    if not total_found:
        st.caption("구매체크를 할수록 도감이 채워져요.")
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
