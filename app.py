import streamlit as st
from google import genai
from PIL import Image
from datetime import datetime, timedelta, timezone
from supabase import create_client
import uuid
import time
import re


# ============================================================
# 1. 기본 설정
# ============================================================

st.set_page_config(
    page_title="체키 | CHECKI",
    page_icon="🔵",
    layout="centered",
    initial_sidebar_state="collapsed"
)


# ============================================================
# 2. CSS
# ============================================================

st.markdown("""
<style>

/* ---------------------------------------------------------
   STREAMLIT 기본 UI 제거
--------------------------------------------------------- */

#MainMenu {
    visibility: hidden !important;
}

footer {
    visibility: hidden !important;
}

header[data-testid="stHeader"] {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
}

[data-testid="stToolbar"] {
    display: none !important;
}

[data-testid="stDecoration"] {
    display: none !important;
}

[data-testid="stStatusWidget"] {
    display: none !important;
}

[data-testid="stAppDeployButton"] {
    display: none !important;
}

.stDeployButton {
    display: none !important;
}

[data-testid="stMainMenu"] {
    display: none !important;
}


/* ---------------------------------------------------------
   전체 페이지
--------------------------------------------------------- */

html,
body {
    margin: 0 !important;
    padding: 0 !important;
    overflow-x: hidden !important;
}

.stApp {
    margin: 0 !important;
    padding: 0 !important;
    overflow-x: hidden !important;

    background:
        radial-gradient(
            circle at 90% 5%,
            #eaf4ff 0,
            transparent 26%
        ),
        #f8fbff;
}

[data-testid="stAppViewContainer"] {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

[data-testid="stAppViewContainer"] > .main {
    margin-top: 0 !important;
    padding-top: 0 !important;
    overflow-x: hidden !important;
}

section[data-testid="stMain"] {
    margin-top: 0 !important;
    padding-top: 0 !important;
}


/* ---------------------------------------------------------
   메인 콘텐츠
--------------------------------------------------------- */

.block-container,
[data-testid="stMainBlockContainer"] {

    width: 100% !important;
    max-width: 760px !important;

    margin-left: auto !important;
    margin-right: auto !important;

    padding-top: 24px !important;
    padding-left: 24px !important;
    padding-right: 24px !important;
    padding-bottom: 100px !important;

    box-sizing: border-box !important;
}


/* ---------------------------------------------------------
   폰트
--------------------------------------------------------- */

html,
body,
[class*="css"] {
    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        "Noto Sans KR",
        sans-serif;
}


/* ---------------------------------------------------------
   버튼
--------------------------------------------------------- */

div.stButton > button {

    width: 100%;
    min-height: 52px;

    border-radius: 15px;

    font-weight: 800;

    border: 1px solid #dce8f6;
}

div.stButton > button[kind="primary"] {

    background:
        linear-gradient(
            135deg,
            #1685ff,
            #2875ef
        );

    color: white;

    border: none;
}


/* ---------------------------------------------------------
   업로더
--------------------------------------------------------- */

div[data-testid="stFileUploader"] {

    background: white;

    border: 1px solid #e2ebf6;

    padding: 12px;

    border-radius: 20px;
}


/* ---------------------------------------------------------
   입력창
--------------------------------------------------------- */

div[data-baseweb="input"] > div {

    border-radius: 14px !important;
}


/* ---------------------------------------------------------
   NAV
--------------------------------------------------------- */

div[data-testid="stRadio"] > div {

    background: white;

    border: 1px solid #e2eaf4;

    border-radius: 18px;

    padding: 6px 8px !important;

    display: flex !important;

    flex-direction: row !important;

    flex-wrap: nowrap !important;

    justify-content: space-between !important;

    gap: 2px !important;

    overflow-x: auto !important;
}

div[data-testid="stRadio"] label {

    margin: 0 !important;

    padding: 3px 4px !important;

    white-space: nowrap !important;

    font-size: 13px !important;
}


/* ---------------------------------------------------------
   로고
--------------------------------------------------------- */

.logo {

    font-size: 30px;

    font-weight: 900;

    color: #1683ff;

    letter-spacing: -2px;
}

.logo-sub {

    font-size: 10px;

    color: #96a2b1;

    letter-spacing: 1px;

    margin-top: 3px;
}


/* ---------------------------------------------------------
   HERO
--------------------------------------------------------- */

.hero {

    padding: 30px 26px;

    background:
        linear-gradient(
            135deg,
            #edf6ff,
            #ffffff 55%,
            #f3efff
        );

    border: 1px solid #e1ebf6;

    border-radius: 28px;

    box-shadow:
        0 12px 35px rgba(50,100,160,.07);

    margin: 26px 0;
}

.hero-badge {

    display: inline-block;

    padding: 7px 12px;

    background: #deefff;

    color: #1683ff;

    border-radius: 30px;

    font-size: 12px;

    font-weight: 800;
}

.hero-title {

    margin-top: 14px;

    font-size: 30px;

    line-height: 1.3;

    font-weight: 900;

    letter-spacing: -1.5px;

    color: #102f5d;
}

.hero-desc {

    margin-top: 12px;

    color: #6e7f93;

    line-height: 1.7;

    font-size: 14px;
}


/* ---------------------------------------------------------
   SECTION
--------------------------------------------------------- */

.section {

    font-size: 21px;

    font-weight: 900;

    color: #112f59;

    margin: 30px 0 13px 0;

    letter-spacing: -.7px;
}


/* ---------------------------------------------------------
   CARD
--------------------------------------------------------- */

.card {

    background: white;

    border: 1px solid #e5edf7;

    border-radius: 22px;

    padding: 20px;

    margin: 11px 0;

    box-shadow:
        0 7px 25px rgba(30,80,140,.05);
}

.card-blue {

    background:
        linear-gradient(
            135deg,
            #edf7ff,
            #f9fcff
        );

    border: 1px solid #d9eaff;

    border-radius: 22px;

    padding: 20px;

    margin: 11px 0;
}

.card-red {

    background:
        linear-gradient(
            135deg,
            #fff0f0,
            #fff8f8
        );

    border: 1px solid #ffdada;

    border-radius: 22px;

    padding: 20px;

    margin: 11px 0;
}

.card-purple {

    background:
        linear-gradient(
            135deg,
            #f5f0ff,
            #fcfaff
        );

    border: 1px solid #e9dfff;

    border-radius: 22px;

    padding: 20px;

    margin: 11px 0;
}

.card-green {

    background:
        linear-gradient(
            135deg,
            #ecfbf4,
            #f8fffb
        );

    border: 1px solid #d4f0e2;

    border-radius: 22px;

    padding: 20px;

    margin: 11px 0;
}

.card-title {

    color: #16365f;

    font-size: 17px;

    font-weight: 900;
}

.card-text {

    margin-top: 7px;

    color: #718095;

    font-size: 14px;

    line-height: 1.65;
}


/* ---------------------------------------------------------
   결과
--------------------------------------------------------- */

.danger-title {

    color: #e24e4e;

    font-size: 17px;

    font-weight: 900;
}

.tag {

    display: inline-block;

    padding: 5px 10px;

    background: #ffe0e0;

    color: #df5050;

    border-radius: 20px;

    font-size: 12px;

    font-weight: 800;

    margin-top: 10px;
}

.result-title {

    font-size: 28px;

    font-weight: 900;

    color: #102e59;

    text-align: center;

    margin: 30px 0 6px 0;
}

.result-sub {

    color: #7d8b9d;

    font-size: 14px;

    text-align: center;

    margin-bottom: 20px;
}

.score {

    font-size: 39px;

    color: #e74f4f;

    font-weight: 900;

    margin-top: 5px;
}


/* ---------------------------------------------------------
   통계
--------------------------------------------------------- */

.stat {

    background: white;

    border: 1px solid #e4edf7;

    border-radius: 19px;

    padding: 18px 5px;

    text-align: center;

    min-height: 82px;
}

.stat-value {

    color: #1683ff;

    font-size: 23px;

    font-weight: 900;
}

.stat-label {

    color: #8a98aa;

    font-size: 11px;

    margin-top: 5px;
}


/* ---------------------------------------------------------
   진행률
--------------------------------------------------------- */

.progress-bg {

    height: 9px;

    background: #e6eff9;

    border-radius: 20px;

    margin-top: 10px;

    overflow: hidden;
}

.progress-fill {

    height: 100%;

    background: #2188ff;

    border-radius: 20px;
}


/* ---------------------------------------------------------
   타이머
--------------------------------------------------------- */

.timer {

    text-align: center;

    color: #1683ff;

    font-size: 42px;

    font-weight: 900;

    padding: 15px 0;
}


/* ---------------------------------------------------------
   EMPTY
--------------------------------------------------------- */

.empty {

    text-align: center;

    padding: 40px 15px;

    color: #8b99aa;

    font-size: 14px;

    line-height: 1.8;
}


/* ---------------------------------------------------------
   FOOTER
--------------------------------------------------------- */

.footer {

    text-align: center;

    color: #a3adba;

    font-size: 10px;

    margin-top: 55px;

    line-height: 1.7;
}


/* ---------------------------------------------------------
   모바일
--------------------------------------------------------- */

@media screen and (max-width: 768px) {

    .block-container,
    [data-testid="stMainBlockContainer"] {

        width: 100% !important;

        max-width: 100% !important;

        margin: 0 auto !important;

        padding-top: 18px !important;

        padding-left: 18px !important;

        padding-right: 18px !important;

        padding-bottom: 85px !important;
    }

    .hero {

        padding: 25px 22px;

        border-radius: 24px;

        margin-top: 22px;
    }

    .hero-title {

        font-size: 27px;
    }

    .hero-desc {

        font-size: 13px;
    }

    .section {

        font-size: 20px;
    }

    div[data-testid="stRadio"] > div {

        padding: 5px 4px !important;

        gap: 0 !important;
    }

    div[data-testid="stRadio"] label {

        font-size: 12px !important;

        padding: 2px !important;
    }
}


/* ---------------------------------------------------------
   작은 휴대폰
--------------------------------------------------------- */

@media screen and (max-width: 480px) {

    .block-container,
    [data-testid="stMainBlockContainer"] {

        padding-top: 14px !important;

        padding-left: 16px !important;

        padding-right: 16px !important;
    }

    .logo {

        font-size: 27px;
    }

    .hero {

        padding: 23px 20px;
    }

    .hero-title {

        font-size: 25px;
    }

    .card,
    .card-blue,
    .card-red,
    .card-purple,
    .card-green {

        padding: 17px;
    }

    div[data-testid="stRadio"] label {

        font-size: 11px !important;
    }
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# 3. HTML HELPER
# ============================================================

def html(content):

    clean = re.sub(
        r"\n\s*",
        "",
        content
    )

    st.markdown(
        clean,
        unsafe_allow_html=True
    )


# ============================================================
# 4. SUPABASE 연결
# ============================================================

@st.cache_resource
def get_supabase():

    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )


try:

    supabase = get_supabase()

except Exception:

    supabase = None


# ============================================================
# 5. 사용자 ID
#
# 로그인 기능 전 MVP 단계이므로
# 브라우저 세션마다 익명 사용자 ID를 생성한다.
# ============================================================

if "user_id" not in st.session_state:

    st.session_state.user_id = str(
        uuid.uuid4()
    )


USER_ID = st.session_state.user_id


# ============================================================
# 6. SESSION STATE
# ============================================================

DEFAULTS = {

    "result": None,

    "result_product": "",

    "result_price": 0
}

for key, value in DEFAULTS.items():

    if key not in st.session_state:

        st.session_state[key] = value


# ============================================================
# 7. DB 함수
# ============================================================

def db_select(
    table,
    order_column=None,
    desc=True
):

    if supabase is None:
        return []

    try:

        query = (
            supabase
            .table(table)
            .select("*")
            .eq("user_id", USER_ID)
        )

        if order_column:

            query = query.order(
                order_column,
                desc=desc
            )

        result = query.execute()

        return result.data or []

    except Exception:

        return []


def add_expense(
    category,
    item,
    amount
):

    if supabase is None:
        return False

    try:

        supabase.table(
            "checki_expenses"
        ).insert({

            "user_id": USER_ID,

            "category": category,

            "item_name": item,

            "amount": int(amount),

            "created_at":
                datetime.now(
                    timezone.utc
                ).isoformat()

        }).execute()

        return True

    except Exception:

        return False


def delete_expense(row_id):

    if supabase is None:
        return

    try:

        supabase.table(
            "checki_expenses"
        ).delete().eq(
            "id",
            row_id
        ).execute()

    except Exception:

        pass


def get_budget():

    rows = db_select(
        "checki_budgets"
    )

    result = {}

    for row in rows:

        result[row["category"]] = int(
            row.get("budget", 0)
        )

    return result


def save_budget(
    category,
    amount
):

    if supabase is None:
        return False

    try:

        existing = (
            supabase
            .table("checki_budgets")
            .select("*")
            .eq("user_id", USER_ID)
            .eq("category", category)
            .execute()
        )

        if existing.data:

            supabase.table(
                "checki_budgets"
            ).update({

                "budget": int(amount)

            }).eq(
                "id",
                existing.data[0]["id"]
            ).execute()

        else:

            supabase.table(
                "checki_budgets"
            ).insert({

                "user_id": USER_ID,

                "category": category,

                "budget": int(amount)

            }).execute()

        return True

    except Exception:

        return False


def add_record(
    action,
    amount=0,
    product=""
):

    if supabase is None:
        return False

    try:

        supabase.table(
            "checki_records"
        ).insert({

            "user_id": USER_ID,

            "action": action,

            "amount": int(amount),

            "product_name": product,

            "created_at":
                datetime.now(
                    timezone.utc
                ).isoformat()

        }).execute()

        return True

    except Exception:

        return False


def save_hold(
    product,
    price
):

    if supabase is None:
        return False

    try:

        end_time = (
            datetime.now(
                timezone.utc
            )
            + timedelta(
                minutes=30
            )
        )

        supabase.table(
            "checki_holds"
        ).insert({

            "user_id": USER_ID,

            "product_name":
                product,

            "price":
                int(price),

            "hold_until":
                end_time.isoformat(),

            "status":
                "holding",

            "created_at":
                datetime.now(
                    timezone.utc
                ).isoformat()

        }).execute()

        return True

    except Exception:

        return False


def get_active_hold():

    if supabase is None:
        return None

    try:

        result = (
            supabase
            .table("checki_holds")
            .select("*")
            .eq(
                "user_id",
                USER_ID
            )
            .eq(
                "status",
                "holding"
            )
            .order(
                "created_at",
                desc=True
            )
            .limit(1)
            .execute()
        )

        if result.data:

            return result.data[0]

    except Exception:

        pass

    return None


def close_hold(
    row_id,
    status
):

    if supabase is None:
        return

    try:

        supabase.table(
            "checki_holds"
        ).update({

            "status": status

        }).eq(
            "id",
            row_id
        ).execute()

    except Exception:

        pass


# ============================================================
# 8. 실제 통계 계산
# ============================================================

def get_stats():

    records = db_select(
        "checki_records"
    )

    analysis_count = 0

    stopped_count = 0

    saved_money = 0

    for row in records:

        action = row.get(
            "action",
            ""
        )

        if action == "analysis":

            analysis_count += 1

        elif action == "stopped":

            stopped_count += 1

            saved_money += int(
                row.get(
                    "amount",
                    0
                )
                or 0
            )

    return (
        analysis_count,
        stopped_count,
        saved_money
    )


# ============================================================
# 9. 로고
# ============================================================

html("""
<div style="
display:flex;
justify-content:space-between;
align-items:center;
width:100%;
">

<div>

<div class="logo">
체키
</div>

<div class="logo-sub">
CHECK BEFORE YOU BUY
</div>

</div>

<div style="
font-size:25px;
color:#1683ff;
font-weight:900;
">
✓
</div>

</div>
""")


# ============================================================
# 10. NAV
# ============================================================

nav = st.radio(

    "navigation",

    [
        "🏠 홈",
        "✓ 구매체크",
        "📊 소비분석",
        "👤 MY"
    ],

    horizontal=True,

    label_visibility="collapsed"
)

page = nav.split(
    " ",
    1
)[1]


# ============================================================
# 11. 통계
# ============================================================

analysis_count, stopped_count, saved_money = (
    get_stats()
)


# ============================================================
# 12. HOME
# ============================================================

if page == "홈":

    html("""
    <div class="hero">

    <div class="hero-badge">
    AI 소비 방어 도우미
    </div>

    <div class="hero-title">
    구매 전,<br>
    한 번 더 체키해 보세요.
    </div>

    <div class="hero-desc">
    쇼핑 화면 속 구매 유도 요소를 확인하고,
    실제 나의 소비 기록과 함께 살펴보며
    지금 필요한 소비인지 한 번 더 생각할 수 있도록 도와드려요.
    </div>

    </div>
    """)

    html(
        '<div class="section">'
        '나의 체키'
        '</div>'
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        html(
            f"""
            <div class="stat">

            <div class="stat-value">
            {analysis_count}
            </div>

            <div class="stat-label">
            구매 체크
            </div>

            </div>
            """
        )

    with c2:

        html(
            f"""
            <div class="stat">

            <div class="stat-value">
            {stopped_count}
            </div>

            <div class="stat-label">
            구매 포기
            </div>

            </div>
            """
        )

    with c3:

        html(
            f"""
            <div class="stat">

            <div class="stat-value">
            {saved_money:,}
            </div>

            <div class="stat-label">
            방어 금액(원)
            </div>

            </div>
            """
        )

    html(
        '<div class="section">'
        '체키는 이렇게 도와드려요'
        '</div>'
    )

    html("""
    <div class="card">

    <div class="card-title">
    🔎 구매 유도 요소 확인
    </div>

    <div class="card-text">
    타이머, 재고 부족, 과도한 할인 강조처럼
    구매를 서두르게 만드는 요소를 AI가 확인해요.
    </div>

    </div>
    """)

    html("""
    <div class="card-blue">

    <div class="card-title">
    📊 실제 내 소비상황과 비교
    </div>

    <div class="card-text">
    직접 등록한 예산과 소비내역을 바탕으로
    현재 소비상황을 확인해요.
    </div>

    </div>
    """)

    html("""
    <div class="card-purple">

    <div class="card-title">
    ⏸ 잠시 보류하기
    </div>

    <div class="card-text">
    바로 결제하지 않고 30분 동안 구매를 보류해
    충동적인 결정을 다시 생각할 시간을 만들어요.
    </div>

    </div>
    """)


# ============================================================
# 13. 구매체크
# ============================================================

elif page == "구매체크":

    html(
        '<div class="section">'
        '구매 전, 한 번 더 체크해 보세요'
        '</div>'
    )

    html("""
    <div class="card-blue">

    <div class="card-title">
    📸 쇼핑 화면을 올려주세요
    </div>

    <div class="card-text">
    체키가 구매를 서두르게 하는 요소가 있는지
    AI로 확인해드려요.
    </div>

    </div>
    """)

    uploaded_file = st.file_uploader(

        "쇼핑 화면 업로드",

        type=[
            "png",
            "jpg",
            "jpeg"
        ]
    )

    product = st.text_input(

        "상품명",

        placeholder=
            "예: 러닝화"
    )

    price = st.number_input(

        "상품 가격",

        min_value=0,

        step=1000,

        format="%d"
    )

    if uploaded_file is not None:

        image = Image.open(
            uploaded_file
        )

        st.image(
            image,
            caption=
                "체키가 확인할 구매 화면",
            width="stretch"
        )

        if st.button(
            "🔎 체키로 확인하기",
            type="primary",
            width="stretch"
        ):

            progress = st.progress(5)

            message = st.empty()

            try:

                message.info(
                    "① 구매 화면을 확인하고 있어요."
                )

                progress.progress(20)

                client = genai.Client(
                    api_key=
                        st.secrets[
                            "GEMINI_API_KEY"
                        ]
                )

                prompt = """
너는 AI 소비자 보호 서비스 '체키(CHECKI)'다.

사용자가 업로드한 온라인 쇼핑 화면을 분석하라.

목표는 구매를 무조건 막는 것이 아니다.

소비자의 구매 결정을 서두르게 만들거나
합리적인 판단을 방해할 가능성이 있는
화면 구성과 표현을 객관적으로 알려주는 것이다.

다음 요소를 확인하라.

1. 긴급성
오늘만, 곧 종료, 카운트다운 등

2. 희소성
재고 부족, 몇 개 남음, 품절 임박 등

3. 사회적 압박
몇 명이 보는 중, 판매량 강조 등

4. 가격 프레이밍
과도한 할인율, 기준가격 강조 등

5. 사전 선택
추가 상품이나 옵션 자동 선택

6. 구독 또는 자동결제

7. 취소 또는 거절을 어렵게 만드는 구조

8. 구매 버튼의 과도한 시각적 강조

9. 기타 소비자의 합리적 판단을 방해할 수 있는 요소

이미지에서 실제로 확인되는 내용만 사용하라.

확실하지 않은 내용은 추측하지 마라.

다크패턴이 명확하지 않다면
억지로 다크패턴이라고 판단하지 마라.

반드시 아래 형식 그대로 출력하라.

RISK: 낮음 또는 주의 또는 높음
SCORE: 0부터 100 사이 숫자
SUMMARY: 가장 중요한 결과 한 문장
TYPES: 핵심 유형 최대 3개
EVIDENCE: 화면에서 실제 확인한 근거
ACTION: 결제 전에 사용자가 확인할 내용
"""

                response_text = None

                last_error = None

                for attempt in range(3):

                    try:

                        message.info(
                            "② 구매 유도 요소를 확인하고 있어요."
                        )

                        progress.progress(45)

                        response = (
                            client.models
                            .generate_content(
                                model=
                                    "gemini-2.5-flash",
                                contents=[
                                    prompt,
                                    image
                                ]
                            )
                        )

                        response_text = (
                            response.text
                        )

                        break

                    except Exception as e:

                        last_error = e

                        if (
                            "503" in str(e)
                            or
                            "UNAVAILABLE"
                            in str(e)
                        ):

                            if attempt < 2:

                                message.info(
                                    "AI 요청이 많아 자동으로 다시 확인하고 있어요."
                                )

                                time.sleep(
                                    2 * (
                                        attempt + 1
                                    )
                                )

                                continue

                        raise e

                if response_text is None:

                    raise last_error

                message.info(
                    "③ 분석 결과를 정리하고 있어요."
                )

                progress.progress(80)

                def extract(
                    label,
                    default
                ):

                    match = re.search(
                        rf"{label}:\s*(.+)",
                        response_text
                    )

                    if match:

                        return (
                            match
                            .group(1)
                            .strip()
                        )

                    return default

                risk = extract(
                    "RISK",
                    "주의"
                )

                score_match = re.search(
                    r"SCORE:\s*(\d+)",
                    response_text
                )

                if score_match:

                    score = int(
                        score_match.group(1)
                    )

                else:

                    score = 50

                score = max(
                    0,
                    min(
                        score,
                        100
                    )
                )

                summary = extract(
                    "SUMMARY",
                    "구매 전에 한 번 더 확인해보세요."
                )

                types = extract(
                    "TYPES",
                    "구매 유도 요소"
                )

                evidence = extract(
                    "EVIDENCE",
                    "구매 화면의 표현을 다시 확인해보세요."
                )

                action = extract(
                    "ACTION",
                    "최종 결제 조건을 확인해보세요."
                )

                st.session_state.result = {

                    "risk": risk,

                    "score": score,

                    "summary": summary,

                    "types": types,

                    "evidence": evidence,

                    "action": action
                }

                st.session_state.result_product = (
                    product
                    if product
                    else
                    "구매 예정 상품"
                )

                st.session_state.result_price = int(
                    price
                )

                add_record(
                    "analysis",
                    int(price),
                    product
                )

                progress.progress(100)

                time.sleep(.2)

                progress.empty()

                message.empty()

            except Exception as e:

                progress.empty()

                message.empty()

                st.error(
                    "분석 중 문제가 발생했어요."
                )

                with st.expander(
                    "오류 정보"
                ):

                    st.caption(
                        str(e)
                    )


    # --------------------------------------------------------
    # 분석 결과
    # --------------------------------------------------------

    if st.session_state.result is not None:

        r = st.session_state.result

        html("""
        <div class="result-title">
        체키가 확인했어요!
        </div>

        <div class="result-sub">
        구매 전에 아래 내용을 한 번 확인해 보세요.
        </div>
        """)

        html(
            f"""
            <div class="card-red">

            <div class="danger-title">
            ⚠️ AI 화면 분석
            </div>

            <div class="card-text">
            <b>{r["summary"]}</b>
            </div>

            <div class="tag">
            {r["types"]}
            </div>

            <div class="card-text">
            {r["evidence"]}
            </div>

            </div>
            """
        )


        # ----------------------------------------------------
        # 실제 소비데이터
        # ----------------------------------------------------

        expenses = db_select(
            "checki_expenses",
            "created_at"
        )

        total_spent = sum(
            int(
                x.get(
                    "amount",
                    0
                )
                or 0
            )
            for x in expenses
        )

        if expenses:

            html(
                f"""
                <div class="card-purple">

                <div class="card-title">
                💳 나의 소비상황
                </div>

                <div class="card-text">
                현재 체키에 등록된 소비는
                <b>{total_spent:,}원</b>이에요.<br>

                등록된 소비내역은
                <b>{len(expenses)}건</b>이에요.
                </div>

                </div>
                """
            )

        else:

            html("""
            <div class="card-purple">

            <div class="card-title">
            💳 아직 소비 기록이 없어요
            </div>

            <div class="card-text">
            소비분석 메뉴에서 실제 소비내역을 등록하면
            다음 구매부터 내 소비상황과 함께 확인할 수 있어요.
            </div>

            </div>
            """)

        html(
            f"""
            <div class="card">

            <div class="card-title">
            🛡️ 결제 전 CHECK
            </div>

            <div class="card-text">
            {r["action"]}
            </div>

            <div class="card-text">
            소비 유도 위험도 · {r["risk"]}
            </div>

            <div class="score">
            {r["score"]}
            <span style="
            font-size:14px;
            color:#8996a8;
            ">
            / 100
            </span>
            </div>

            </div>
            """
        )

        html(
            '<div class="section">'
            '구매를 계속할까요?'
            '</div>'
        )

        if st.button(
            "구매 계속하기",
            type="primary",
            width="stretch"
        ):

            st.info(
                "체키가 확인한 내용을 참고해 신중하게 결정해주세요."
            )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "⏸ 30분 보류",
                width="stretch"
            ):

                success = save_hold(
                    st.session_state.result_product,
                    st.session_state.result_price
                )

                if success:

                    st.success(
                        "30분 동안 구매를 보류했어요. MY에서 다시 확인할 수 있어요."
                    )

                else:

                    st.error(
                        "보류 정보를 저장하지 못했어요."
                    )

        with c2:

            if st.button(
                "구매하지 않기",
                width="stretch"
            ):

                p = (
                    st.session_state
                    .result_price
                )

                add_record(
                    "stopped",
                    p,
                    st.session_state
                    .result_product
                )

                st.session_state.result = None

                if p > 0:

                    st.success(
                        f"🎉 {p:,}원의 소비를 다시 생각했어요!"
                    )

                else:

                    st.success(
                        "🎉 이번 구매를 다시 생각하기로 했어요!"
                    )

                time.sleep(.5)

                st.rerun()


# ============================================================
# 14. 소비분석
# ============================================================

elif page == "소비분석":

    html(
        '<div class="section">'
        '소비분석'
        '</div>'
    )

    html("""
    <div class="card-blue">

    <div class="card-title">
    📊 내 소비 데이터를 직접 만들어보세요
    </div>

    <div class="card-text">
    처음 이용하는 사용자는 0원부터 시작합니다.
    실제 소비내역과 예산을 등록하면
    체키가 그 데이터를 바탕으로 소비상황을 보여드려요.
    </div>

    </div>
    """)


    # --------------------------------------------------------
    # 소비내역 입력
    # --------------------------------------------------------

    with st.expander(
        "＋ 소비내역 추가하기",
        expanded=False
    ):

        expense_category = st.selectbox(
            "카테고리",
            [
                "의류",
                "식비",
                "뷰티",
                "생활용품",
                "교통",
                "취미",
                "전자제품",
                "기타"
            ]
        )

        expense_name = st.text_input(
            "구매한 상품 또는 지출명",
            placeholder=
                "예: 러닝화"
        )

        expense_amount = st.number_input(
            "지출 금액",
            min_value=0,
            step=1000,
            format="%d"
        )

        if st.button(
            "소비내역 저장",
            type="primary",
            width="stretch"
        ):

            if expense_amount <= 0:

                st.warning(
                    "지출 금액을 입력해주세요."
                )

            else:

                success = add_expense(
                    expense_category,
                    expense_name
                    if expense_name
                    else expense_category,
                    expense_amount
                )

                if success:

                    st.success(
                        "소비내역을 저장했어요."
                    )

                    time.sleep(.3)

                    st.rerun()

                else:

                    st.error(
                        "소비내역을 저장하지 못했어요."
                    )


    # --------------------------------------------------------
    # 예산 입력
    # --------------------------------------------------------

    with st.expander(
        "＋ 월 예산 설정하기",
        expanded=False
    ):

        budget_category = st.selectbox(
            "예산 카테고리",
            [
                "의류",
                "식비",
                "뷰티",
                "생활용품",
                "교통",
                "취미",
                "전자제품",
                "기타"
            ],
            key="budget_category"
        )

        budget_amount = st.number_input(
            "월 예산",
            min_value=0,
            step=10000,
            format="%d"
        )

        if st.button(
            "예산 저장",
            width="stretch"
        ):

            if save_budget(
                budget_category,
                budget_amount
            ):

                st.success(
                    "예산을 저장했어요."
                )

                time.sleep(.3)

                st.rerun()

            else:

                st.error(
                    "예산을 저장하지 못했어요."
                )


    # --------------------------------------------------------
    # 데이터 조회
    # --------------------------------------------------------

    expenses = db_select(
        "checki_expenses",
        "created_at"
    )

    budgets = get_budget()

    total_spent = sum(
        int(
            row.get(
                "amount",
                0
            )
            or 0
        )
        for row in expenses
    )

    total_budget = sum(
        budgets.values()
    )


    # --------------------------------------------------------
    # 요약
    # --------------------------------------------------------

    html(
        '<div class="section">'
        '이번 달 소비 현황'
        '</div>'
    )

    c1, c2 = st.columns(2)

    with c1:

        html(
            f"""
            <div class="stat">

            <div class="stat-value">
            {total_spent:,}
            </div>

            <div class="stat-label">
            총 지출(원)
            </div>

            </div>
            """
        )

    with c2:

        html(
            f"""
            <div class="stat">

            <div class="stat-value">
            {total_budget:,}
            </div>

            <div class="stat-label">
            설정 예산(원)
            </div>

            </div>
            """
        )


    # --------------------------------------------------------
    # 카테고리
    # --------------------------------------------------------

    if not expenses:

        html("""
        <div class="empty">

        아직 등록된 소비내역이 없어요.<br>

        위의 <b>＋ 소비내역 추가하기</b>를 눌러<br>

        첫 소비 기록을 등록해보세요.

        </div>
        """)

    else:

        category_totals = {}

        for row in expenses:

            category = row.get(
                "category",
                "기타"
            )

            amount = int(
                row.get(
                    "amount",
                    0
                )
                or 0
            )

            category_totals[
                category
            ] = (
                category_totals.get(
                    category,
                    0
                )
                + amount
            )

        html(
            '<div class="section">'
            '카테고리별 지출'
            '</div>'
        )

        for (
            category,
            amount
        ) in category_totals.items():

            budget = budgets.get(
                category,
                0
            )

            if budget > 0:

                percent = int(
                    amount
                    / budget
                    * 100
                )

                visual_percent = min(
                    percent,
                    100
                )

                budget_text = (
                    f"{amount:,}원 / "
                    f"{budget:,}원"
                )

            else:

                percent = 0

                visual_percent = 0

                budget_text = (
                    f"{amount:,}원 · "
                    "예산 미설정"
                )

            html(
                f"""
                <div class="card">

                <div class="card-title">
                {category}

                <span style="
                float:right;
                ">
                {amount:,}원
                </span>

                </div>

                <div class="card-text">
                {budget_text}
                </div>

                <div class="progress-bg">

                <div
                class="progress-fill"
                style="
                width:{visual_percent}%;
                ">
                </div>

                </div>

                {
                    f'<div class="card-text" style="text-align:right;">예산의 {percent}%</div>'
                    if budget > 0
                    else ""
                }

                </div>
                """
            )


        # ----------------------------------------------------
        # 소비 패턴
        # ----------------------------------------------------

        if total_budget > 0:

            total_percent = int(
                total_spent
                / total_budget
                * 100
            )

            if total_percent >= 100:

                message = (
                    "설정한 전체 예산을 초과했어요. "
                    "추가 구매 전 현재 소비내역을 다시 확인해보세요."
                )

            elif total_percent >= 80:

                message = (
                    "전체 예산의 80% 이상을 사용했어요. "
                    "추가 구매는 조금 더 신중하게 확인해보는 것을 추천해요."
                )

            elif total_percent >= 50:

                message = (
                    "전체 예산의 절반 이상을 사용했어요. "
                    "남은 예산을 확인하며 소비해보세요."
                )

            else:

                message = (
                    "현재까지 등록된 지출은 설정한 예산 범위 안에 있어요."
                )

            html(
                f"""
                <div class="card-blue">

                <div class="card-title">
                💡 체키 소비 체크
                </div>

                <div class="card-text">
                {message}
                </div>

                </div>
                """
            )


        # ----------------------------------------------------
        # 최근 내역
        # ----------------------------------------------------

        html(
            '<div class="section">'
            '최근 소비내역'
            '</div>'
        )

        for row in expenses[:10]:

            name = row.get(
                "item_name",
                "소비"
            )

            category = row.get(
                "category",
                "기타"
            )

            amount = int(
                row.get(
                    "amount",
                    0
                )
                or 0
            )

            html(
                f"""
                <div class="card">

                <div class="card-title">
                {name}

                <span style="
                float:right;
                ">
                {amount:,}원
                </span>

                </div>

                <div class="card-text">
                {category}
                </div>

                </div>
                """
            )

            if st.button(
                f"삭제 · {name}",
                key=
                    f'delete_{row["id"]}',
                width="stretch"
            ):

                delete_expense(
                    row["id"]
                )

                st.rerun()


# ============================================================
# 15. MY
# ============================================================

elif page == "MY":

    html(
        '<div class="section">'
        'MY 체키'
        '</div>'
    )

    analysis_count, stopped_count, saved_money = (
        get_stats()
    )

    c1, c2 = st.columns(2)

    with c1:

        st.metric(
            "구매 체크",
            f"{analysis_count}회"
        )

    with c2:

        st.metric(
            "구매 포기",
            f"{stopped_count}회"
        )

    st.metric(
        "다시 생각한 소비",
        f"{saved_money:,}원"
    )


    # --------------------------------------------------------
    # 보류
    # --------------------------------------------------------

    hold = get_active_hold()

    if hold:

        try:

            hold_until = (
                datetime
                .fromisoformat(
                    hold[
                        "hold_until"
                    ].replace(
                        "Z",
                        "+00:00"
                    )
                )
            )

            now = datetime.now(
                timezone.utc
            )

            remaining = (
                hold_until
                - now
            )

            seconds = max(
                0,
                int(
                    remaining
                    .total_seconds()
                )
            )

        except Exception:

            seconds = 0

        if seconds <= 0:

            close_hold(
                hold["id"],
                "expired"
            )

            html("""
            <div class="card-green">

            <div class="card-title">
            ✓ 고민 시간이 끝났어요
            </div>

            <div class="card-text">
            지금도 이 상품이 필요한지
            다시 한 번 생각해보세요.
            </div>

            </div>
            """)

        else:

            hours = (
                seconds // 3600
            )

            minutes = (
                seconds % 3600
            ) // 60

            secs = (
                seconds % 60
            )

            product_name = (
                hold.get(
                    "product_name",
                    "구매 예정 상품"
                )
            )

            hold_price = int(
                hold.get(
                    "price",
                    0
                )
                or 0
            )

            html(
                '<div class="section">'
                '구매 보류 중'
                '</div>'
            )

            html(
                f"""
                <div class="card-blue">

                <div class="card-title">
                🔒 {product_name}
                </div>

                <div class="card-text">
                {hold_price:,}원
                </div>

                <div class="timer">
                {hours:02d}:{minutes:02d}:{secs:02d}
                </div>

                <div
                class="card-text"
                style="text-align:center;"
                >
                남은 고민 시간
                </div>

                </div>
                """
            )

            st.caption(
                "새로고침하면 남은 시간이 갱신됩니다."
            )

            c1, c2 = st.columns(2)

            with c1:

                if st.button(
                    "구매하지 않기",
                    type="primary",
                    width="stretch"
                ):

                    add_record(
                        "stopped",
                        hold_price,
                        product_name
                    )

                    close_hold(
                        hold["id"],
                        "stopped"
                    )

                    st.rerun()

            with c2:

                if st.button(
                    "보류 종료",
                    width="stretch"
                ):

                    close_hold(
                        hold["id"],
                        "ended"
                    )

                    st.rerun()

    else:

        html("""
        <div class="card-blue">

        <div class="card-title">
        ⏸ 현재 보류 중인 구매가 없어요
        </div>

        <div class="card-text">
        고민되는 상품은 구매체크에서
        30분 동안 잠시 보류할 수 있어요.
        </div>

        </div>
        """)

    if stopped_count > 0:

        html(
            f"""
            <div class="card-green">

            <div class="card-title">
            🎉 체키 효과
            </div>

            <div class="card-text">

            지금까지
            <b>{stopped_count}번</b>의 구매를 다시 생각했고,

            <b>{saved_money:,}원</b>의
            소비를 재검토했어요.

            </div>

            </div>
            """
        )


# ============================================================
# 16. FOOTER
# ============================================================

html("""
<div class="footer">

CHECKI · AI 소비자 보호 서비스 MVP
<br>

AI 분석 결과는 소비자의 판단을 돕기 위한 참고 정보입니다.
<br>

소비 데이터는 사용자가 직접 등록한 데이터를 기반으로 표시됩니다.

</div>
""")
