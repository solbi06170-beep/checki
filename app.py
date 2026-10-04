import streamlit as st
from google import genai
from PIL import Image
from datetime import datetime, timedelta, timezone
from supabase import create_client
import uuid
import time
import re


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="체키 | CHECKI",
    page_icon="🔵",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# SUPABASE
# ============================================================

@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )


supabase = get_supabase()


# ============================================================
# 사용자 구분
#
# 처음 접속하면 사용자 ID 생성
# URL ?uid=... 에 저장
# 새로고침해도 같은 사용자로 유지
# ============================================================

def get_user_id():

    try:
        uid = st.query_params.get("uid")
    except:
        uid = None

    if not uid:
        uid = str(uuid.uuid4())
        st.query_params["uid"] = uid

    return str(uid)


USER_ID = get_user_id()


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "result": None,
    "result_product": "",
    "result_price": 0,
    "analysis_saved": False,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# DATABASE HELPERS
# ============================================================

def db_select(table, filters=None):

    try:
        query = supabase.table(table).select("*")

        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)

        response = query.execute()

        return response.data or []

    except Exception:
        return []


def db_insert(table, data):

    try:
        return (
            supabase
            .table(table)
            .insert(data)
            .execute()
        )

    except Exception as e:
        st.error("데이터 저장 중 문제가 발생했어요.")
        with st.expander("오류 정보"):
            st.caption(str(e))
        return None


def db_update(table, data, filters):

    try:
        query = supabase.table(table).update(data)

        for key, value in filters.items():
            query = query.eq(key, value)

        return query.execute()

    except Exception as e:
        st.error("데이터 수정 중 문제가 발생했어요.")
        with st.expander("오류 정보"):
            st.caption(str(e))
        return None


def db_delete(table, filters):

    try:
        query = supabase.table(table).delete()

        for key, value in filters.items():
            query = query.eq(key, value)

        return query.execute()

    except Exception as e:
        st.error("데이터 삭제 중 문제가 발생했어요.")
        with st.expander("오류 정보"):
            st.caption(str(e))
        return None


# ============================================================
# RECORD HELPERS
# ============================================================

def get_records():

    records = db_select(
        "checki_records",
        {"user_id": USER_ID}
    )

    return records


def get_expenses():

    expenses = db_select(
        "checki_expenses",
        {"user_id": USER_ID}
    )

    return expenses


def get_active_hold():

    records = get_records()

    active = []

    now = datetime.now(timezone.utc)

    for record in records:

        if record.get("decision") != "hold":
            continue

        hold_until = record.get("hold_until")

        if not hold_until:
            continue

        try:

            dt = datetime.fromisoformat(
                str(hold_until).replace("Z", "+00:00")
            )

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            if dt > now:
                active.append((record, dt))

        except:
            pass

    if not active:
        return None, None

    active.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return active[0]


def get_stats():

    records = get_records()

    analysis_count = len(records)

    stopped = [
        x for x in records
        if x.get("decision") == "stop"
    ]

    stopped_count = len(stopped)

    saved_money = 0

    for item in stopped:

        try:
            saved_money += int(
                item.get("price") or 0
            )
        except:
            pass

    return (
        analysis_count,
        stopped_count,
        saved_money
    )


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

/* Streamlit 기본 UI */
#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

header {
    background: transparent;
}


/* 전체 화면 */
html,
body,
[data-testid="stAppViewContainer"],
.stApp {
    overflow-x: hidden !important;
}

.stApp {
    background:
        radial-gradient(
            circle at 90% 4%,
            #eaf4ff 0,
            transparent 24%
        ),
        #f8fbff;
}


/* 핵심: 화면 잘림 방지 */
.block-container {

    width: 100% !important;

    max-width: 900px !important;

    margin-left: auto !important;
    margin-right: auto !important;

    padding-top: 24px !important;

    padding-left:
        max(20px, env(safe-area-inset-left))
        !important;

    padding-right:
        max(20px, env(safe-area-inset-right))
        !important;

    padding-bottom: 90px !important;

    box-sizing: border-box !important;
}


* {
    box-sizing: border-box;
}


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


/* 버튼 */

div.stButton > button {

    width: 100%;

    min-height: 50px;

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


/* 입력창 */

div[data-testid="stFileUploader"] {

    background: white;

    border: 1px solid #e2ebf6;

    padding: 12px;

    border-radius: 20px;
}


div[data-testid="stMetric"] {

    background: white;

    border: 1px solid #e4edf7;

    border-radius: 18px;

    padding: 15px;
}


/* 네비 */

div[data-testid="stRadio"] > div {

    background: white;

    border: 1px solid #e2eaf4;

    border-radius: 18px;

    padding: 5px;

    overflow-x: auto;
}


/* LOGO */

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
}


/* HERO */

.hero {

    width: 100%;

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
        0 12px 35px
        rgba(50,100,160,.07);

    margin: 22px 0;

    overflow: hidden;
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

    font-size: clamp(25px, 5vw, 32px);

    line-height: 1.3;

    font-weight: 900;

    letter-spacing: -1.5px;

    color: #102f5d;

    word-break: keep-all;
}


.hero-desc {

    margin-top: 12px;

    color: #6e7f93;

    line-height: 1.7;

    font-size: 14px;

    word-break: keep-all;
}


/* SECTION */

.section {

    font-size: 21px;

    font-weight: 900;

    color: #112f59;

    margin: 28px 0 12px;

    letter-spacing: -.7px;
}


/* CARD */

.card,
.card-blue,
.card-red,
.card-purple,
.card-green {

    width: 100%;

    border-radius: 22px;

    padding: 20px;

    margin: 11px 0;

    overflow: hidden;

    word-break: keep-all;
}


.card {

    background: white;

    border: 1px solid #e5edf7;

    box-shadow:
        0 7px 25px
        rgba(30,80,140,.05);
}


.card-blue {

    background:
        linear-gradient(
            135deg,
            #edf7ff,
            #f9fcff
        );

    border: 1px solid #d9eaff;
}


.card-red {

    background:
        linear-gradient(
            135deg,
            #fff0f0,
            #fff8f8
        );

    border: 1px solid #ffdada;
}


.card-purple {

    background:
        linear-gradient(
            135deg,
            #f5f0ff,
            #fcfaff
        );

    border: 1px solid #e9dfff;
}


.card-green {

    background:
        linear-gradient(
            135deg,
            #ecfbf4,
            #f8fffb
        );

    border: 1px solid #d4f0e2;
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


/* RESULT */

.result-title {

    font-size: 28px;

    font-weight: 900;

    color: #102e59;

    text-align: center;

    margin: 30px 0 6px;
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


/* STATS */

.stat {

    background: white;

    border: 1px solid #e4edf7;

    border-radius: 19px;

    padding: 18px 5px;

    text-align: center;

    height: 100%;
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


/* PROGRESS */

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


/* TIMER */

.timer {

    text-align: center;

    color: #1683ff;

    font-size: clamp(32px, 7vw, 45px);

    font-weight: 900;

    padding: 15px 0;
}


/* EMPTY */

.empty {

    text-align: center;

    padding: 35px 20px;

    color: #8392a5;
}


.empty-icon {

    font-size: 38px;

    margin-bottom: 10px;
}


/* FOOTER */

.footer {

    text-align: center;

    color: #a3adba;

    font-size: 10px;

    margin-top: 55px;

    line-height: 1.7;
}


/* 태블릿 / 모바일 */

@media (max-width: 700px) {

    .block-container {

        padding-left: 14px !important;

        padding-right: 14px !important;

        padding-top: 15px !important;
    }

    .hero {

        padding: 24px 20px;
    }

    .card,
    .card-blue,
    .card-red,
    .card-purple,
    .card-green {

        padding: 17px;
    }

    .section {

        font-size: 19px;
    }
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# HTML HELPER
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
# HEADER
# ============================================================

html("""
<div style="
display:flex;
justify-content:space-between;
align-items:center;
width:100%;
">
    <div>
        <div class="logo">체키</div>
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
# NAVIGATION
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

page = nav.split(" ", 1)[1]


# ============================================================
# STATS
# ============================================================

analysis_count, stopped_count, saved_money = get_stats()


# ============================================================
# HOME
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
            지금 필요한 소비인지 한 번 더
            생각할 수 있도록 도와드려요.
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
            🔎 AI 구매 화면 분석
        </div>

        <div class="card-text">
            타이머, 재고 부족, 할인 강조 등
            소비자의 구매 결정을 서두르게 할 수 있는
            요소를 AI가 확인해요.
        </div>

    </div>
    """)

    html("""
    <div class="card-blue">

        <div class="card-title">
            📊 내 실제 소비 기록 확인
        </div>

        <div class="card-text">
            직접 기록한 소비내역을 바탕으로
            카테고리별 소비상황을 확인할 수 있어요.
        </div>

    </div>
    """)

    html("""
    <div class="card-purple">

        <div class="card-title">
            ⏸ 30분 고민하기
        </div>

        <div class="card-text">
            바로 결제하지 않고 구매를 잠시 보류해
            충동적인 결정을 다시 생각할 시간을 만들어요.
        </div>

    </div>
    """)


# ============================================================
# 구매 체크
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
        placeholder="예: 러닝화"
    )

    price = st.number_input(
        "상품 가격",
        min_value=0,
        step=1000,
        format="%d"
    )

    if uploaded_file is not None:

        image = Image.open(uploaded_file)

        st.image(
            image,
            caption="체키가 확인할 구매 화면",
            width="stretch"
        )

        if st.button(
            "🔎 체키로 확인하기",
            type="primary",
            use_container_width=True
        ):

            progress = st.progress(5)

            message = st.empty()

            try:

                message.info(
                    "① 구매 화면을 확인하고 있어요."
                )

                progress.progress(20)

                client = genai.Client(
                    api_key=st.secrets[
                        "GEMINI_API_KEY"
                    ]
                )

                prompt = """
너는 AI 소비자 보호 서비스
'체키(CHECKI)'다.

사용자가 업로드한 온라인 쇼핑 화면을
분석하라.

목표는 구매를 무조건 막는 것이 아니라
소비자의 구매 결정을 서두르게 만들 수 있는
요소를 객관적으로 알려주는 것이다.

다음 요소를 확인한다.

- 긴급성 표현
- 카운트다운
- 오늘만 할인
- 품절 임박
- 재고 부족
- 사회적 압박
- 판매량 강조
- 현재 보고 있는 사람 수
- 과도한 할인 강조
- 기준가격 프레이밍
- 자동 선택 옵션
- 구독 및 자동결제
- 취소나 거절을 어렵게 하는 구조
- 구매 버튼의 과도한 시각적 강조
- 기타 다크패턴 가능성이 있는 요소

이미지에서 실제 확인되는 내용만 사용한다.

보이지 않는 정보는 절대 추측하지 않는다.

다크패턴이 명확하지 않으면
그 사실도 명확하게 말한다.

반드시 다음 형식으로 출력한다.

RISK: 낮음 또는 주의 또는 높음
SCORE: 0부터 100 사이 정수
SUMMARY: 가장 중요한 분석 결과 한 문장
TYPES: 핵심 유형 최대 3개
EVIDENCE: 화면에서 직접 확인한 근거
ACTION: 결제 전에 확인할 내용 한 문장
"""

                response_text = None

                last_error = None

                for attempt in range(3):

                    try:

                        message.info(
                            "② 구매 유도 요소를 "
                            "AI가 확인하고 있어요."
                        )

                        progress.progress(50)

                        response = (
                            client.models.generate_content(
                                model="gemini-2.5-flash",
                                contents=[
                                    prompt,
                                    image
                                ]
                            )
                        )

                        response_text = response.text

                        break

                    except Exception as e:

                        last_error = e

                        if (
                            "503" in str(e)
                            or
                            "UNAVAILABLE" in str(e)
                        ):

                            if attempt < 2:

                                message.info(
                                    "AI 요청이 많아 "
                                    "자동으로 다시 시도하고 있어요."
                                )

                                time.sleep(
                                    2 * (attempt + 1)
                                )

                                continue

                        raise e

                if response_text is None:
                    raise last_error

                message.info(
                    "③ 결과를 정리하고 있어요."
                )

                progress.progress(80)

                def extract(label, default):

                    match = re.search(
                        rf"{label}:\s*(.+)",
                        response_text
                    )

                    if match:
                        return match.group(1).strip()

                    return default

                risk = extract(
                    "RISK",
                    "주의"
                )

                try:

                    score_match = re.search(
                        r"SCORE:\s*(\d+)",
                        response_text
                    )

                    score = int(
                        score_match.group(1)
                    )

                except:
                    score = 50

                score = max(
                    0,
                    min(score, 100)
                )

                summary = extract(
                    "SUMMARY",
                    "구매 전에 한 번 더 "
                    "확인해보세요."
                )

                types = extract(
                    "TYPES",
                    "구매 유도 요소"
                )

                evidence = extract(
                    "EVIDENCE",
                    "화면의 구매 관련 표현을 "
                    "확인해보세요."
                )

                action = extract(
                    "ACTION",
                    "최종 결제 조건을 "
                    "확인해보세요."
                )

                progress.progress(100)

                time.sleep(.2)

                progress.empty()
                message.empty()

                st.session_state.result = {
                    "risk": risk,
                    "score": score,
                    "summary": summary,
                    "types": types,
                    "evidence": evidence,
                    "action": action
                }

                st.session_state.result_product = (
                    product.strip()
                    if product.strip()
                    else
                    "구매 예정 상품"
                )

                st.session_state.result_price = int(
                    price
                )

                st.session_state.analysis_saved = False

            except Exception as e:

                progress.empty()
                message.empty()

                st.error(
                    "AI 분석 중 문제가 생겼어요."
                )

                with st.expander(
                    "오류 정보"
                ):
                    st.caption(str(e))


    # ========================================================
    # RESULT
    # ========================================================

    if st.session_state.result is not None:

        r = st.session_state.result

        html("""
        <div class="result-title">
            체키가 확인했어요!
        </div>

        <div class="result-sub">
            구매 전에 아래 내용을
            한 번 확인해 보세요.
        </div>
        """)

        risk_class = (
            "card-red"
            if r["risk"] in ["주의", "높음"]
            else
            "card-green"
        )

        html(
            f"""
            <div class="{risk_class}">

                <div class="danger-title">
                    ⚠️ AI 구매 화면 분석
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

        expenses = get_expenses()

        total_spending = 0

        for expense in expenses:

            try:
                total_spending += int(
                    expense.get("amount") or 0
                )
            except:
                pass

        html(
            f"""
            <div class="card-blue">

                <div class="card-title">
                    📊 나의 소비 기록
                </div>

                <div class="card-text">
                    현재 체키에 기록한 총 소비금액은
                    <b>{total_spending:,}원</b>이에요.
                    <br>
                    소비분석에서 직접 입력한 실제 기록을
                    기준으로 표시합니다.
                </div>

            </div>
            """
        )

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
                    소비 유도 위험도 ·
                    <b>{r["risk"]}</b>
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
            use_container_width=True
        ):

            db_insert(
                "checki_records",
                {
                    "user_id": USER_ID,
                    "product_name":
                        st.session_state.result_product,
                    "price":
                        st.session_state.result_price,
                    "risk":
                        r["risk"],
                    "score":
                        r["score"],
                    "summary":
                        r["summary"],
                    "decision":
                        "continue",
                    "hold_until":
                        None
                }
            )

            st.session_state.result = None

            st.success(
                "구매 계속으로 기록했어요."
            )

            time.sleep(.7)

            st.rerun()

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "⏸ 30분 보류",
                use_container_width=True
            ):

                hold_until = (
                    datetime.now(timezone.utc)
                    +
                    timedelta(minutes=30)
                )

                db_insert(
                    "checki_records",
                    {
                        "user_id":
                            USER_ID,

                        "product_name":
                            st.session_state.result_product,

                        "price":
                            st.session_state.result_price,

                        "risk":
                            r["risk"],

                        "score":
                            r["score"],

                        "summary":
                            r["summary"],

                        "decision":
                            "hold",

                        "hold_until":
                            hold_until.isoformat()
                    }
                )

                st.session_state.result = None

                st.success(
                    "30분 보류했어요. "
                    "MY에서 확인할 수 있어요."
                )

                time.sleep(.7)

                st.rerun()

        with c2:

            if st.button(
                "구매하지 않기",
                use_container_width=True
            ):

                db_insert(
                    "checki_records",
                    {
                        "user_id":
                            USER_ID,

                        "product_name":
                            st.session_state.result_product,

                        "price":
                            st.session_state.result_price,

                        "risk":
                            r["risk"],

                        "score":
                            r["score"],

                        "summary":
                            r["summary"],

                        "decision":
                            "stop",

                        "hold_until":
                            None
                    }
                )

                amount = (
                    st.session_state.result_price
                )

                st.session_state.result = None

                if amount > 0:

                    st.success(
                        f"🎉 {amount:,}원의 소비를 "
                        "다시 생각했어요!"
                    )

                else:

                    st.success(
                        "🎉 이번 구매를 "
                        "다시 생각하기로 했어요!"
                    )

                time.sleep(.7)

                st.rerun()


# ============================================================
# 소비 분석
# ============================================================

elif page == "소비분석":

    html(
        '<div class="section">'
        '소비분석'
        '</div>'
    )

    html("""
    <div class="hero">

        <div class="hero-badge">
            나의 소비 기록
        </div>

        <div class="hero-title">
            내가 쓴 돈을<br>
            직접 확인해 보세요.
        </div>

        <div class="hero-desc">
            체키에 입력한 실제 소비내역을 바탕으로
            소비 패턴을 확인할 수 있어요.
        </div>

    </div>
    """)

    # --------------------------------------------------------
    # 소비 추가
    # --------------------------------------------------------

    with st.expander(
        "＋ 소비내역 추가하기",
        expanded=False
    ):

        expense_name = st.text_input(
            "구매한 상품",
            placeholder="예: 운동화",
            key="expense_name"
        )

        expense_category = st.selectbox(
            "카테고리",
            [
                "의류",
                "식비",
                "뷰티",
                "생활용품",
                "교통",
                "문화/여가",
                "전자기기",
                "기타"
            ]
        )

        expense_amount = st.number_input(
            "결제 금액",
            min_value=0,
            step=1000,
            format="%d",
            key="expense_amount"
        )

        expense_date = st.date_input(
            "구매 날짜"
        )

        if st.button(
            "소비내역 저장",
            type="primary",
            use_container_width=True
        ):

            if not expense_name.strip():

                st.warning(
                    "상품명을 입력해주세요."
                )

            elif expense_amount <= 0:

                st.warning(
                    "결제 금액을 입력해주세요."
                )

            else:

                result = db_insert(
                    "checki_expenses",
                    {
                        "user_id":
                            USER_ID,

                        "product_name":
                            expense_name.strip(),

                        "category":
                            expense_category,

                        "amount":
                            int(expense_amount),

                        "expense_date":
                            expense_date.isoformat()
                    }
                )

                if result is not None:

                    st.success(
                        "소비내역을 저장했어요."
                    )

                    time.sleep(.5)

                    st.rerun()


    # --------------------------------------------------------
    # 실제 데이터
    # --------------------------------------------------------

    expenses = get_expenses()

    total = 0

    for item in expenses:

        try:
            total += int(
                item.get("amount") or 0
            )
        except:
            pass

    c1, c2 = st.columns(2)

    with c1:

        st.metric(
            "기록한 소비",
            f"{total:,}원"
        )

    with c2:

        st.metric(
            "구매 건수",
            f"{len(expenses)}건"
        )


    # --------------------------------------------------------
    # EMPTY
    # --------------------------------------------------------

    if len(expenses) == 0:

        html("""
        <div class="card-blue">

            <div class="empty">

                <div class="empty-icon">
                    📊
                </div>

                <div class="card-title">
                    아직 소비내역이 없어요
                </div>

                <div class="card-text">
                    위의 '소비내역 추가하기'에서
                    첫 소비를 기록하면
                    체키가 소비분석을 시작해요.
                </div>

            </div>

        </div>
        """)

    else:

        # ----------------------------------------------------
        # CATEGORY
        # ----------------------------------------------------

        category_totals = {}

        for item in expenses:

            category = (
                item.get("category")
                or
                "기타"
            )

            try:
                amount = int(
                    item.get("amount") or 0
                )
            except:
                amount = 0

            category_totals[category] = (
                category_totals.get(
                    category,
                    0
                )
                +
                amount
            )

        html(
            '<div class="section">'
            '카테고리별 소비'
            '</div>'
        )

        max_amount = max(
            category_totals.values()
        )

        for category, amount in sorted(
            category_totals.items(),
            key=lambda x: x[1],
            reverse=True
        ):

            if max_amount > 0:

                percent = int(
                    amount
                    /
                    max_amount
                    *
                    100
                )

            else:
                percent = 0

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

                    <div class="progress-bg">

                        <div
                        class="progress-fill"
                        style="
                        width:{percent}%;
                        ">
                        </div>

                    </div>

                </div>
                """
            )


        # ----------------------------------------------------
        # 가장 많이 쓴 카테고리
        # ----------------------------------------------------

        biggest_category = max(
            category_totals,
            key=category_totals.get
        )

        biggest_amount = (
            category_totals[
                biggest_category
            ]
        )

        html("""
        <div class="section">
            체키 소비 인사이트
        </div>
        """)

        html(
            f"""
            <div class="card-purple">

                <div class="card-title">
                    💡 가장 많은 소비
                </div>

                <div class="card-text">
                    현재 기록에서는
                    <b>{biggest_category}</b> 카테고리의
                    소비가 가장 많아요.

                    지금까지
                    <b>{biggest_amount:,}원</b>을
                    기록했어요.
                </div>

            </div>
            """
        )


        # ----------------------------------------------------
        # 최근 소비
        # ----------------------------------------------------

        html(
            '<div class="section">'
            '최근 소비내역'
            '</div>'
        )

        def expense_sort_key(x):

            return str(
                x.get("expense_date")
                or
                x.get("created_at")
                or
                ""
            )

        sorted_expenses = sorted(
            expenses,
            key=expense_sort_key,
            reverse=True
        )

        for item in sorted_expenses[:10]:

            name = (
                item.get("product_name")
                or
                "상품"
            )

            category = (
                item.get("category")
                or
                "기타"
            )

            amount = int(
                item.get("amount")
                or
                0
            )

            date = (
                item.get("expense_date")
                or
                ""
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
                        {category} · {date}
                    </div>

                </div>
                """
            )


# ============================================================
# MY
# ============================================================

elif page == "MY":

    # 새로 DB에서 통계 읽음

    analysis_count, stopped_count, saved_money = (
        get_stats()
    )

    html(
        '<div class="section">'
        'MY 체키'
        '</div>'
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
    # HOLD
    # --------------------------------------------------------

    hold_record, hold_datetime = (
        get_active_hold()
    )

    if hold_record is not None:

        now = datetime.now(
            timezone.utc
        )

        remaining = (
            hold_datetime - now
        )

        seconds = max(
            0,
            int(
                remaining.total_seconds()
            )
        )

        hours = seconds // 3600

        minutes = (
            seconds % 3600
        ) // 60

        secs = seconds % 60

        product_name = (
            hold_record.get(
                "product_name"
            )
            or
            "구매 예정 상품"
        )

        price = int(
            hold_record.get(
                "price"
            )
            or
            0
        )

        record_id = hold_record.get(
            "id"
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
                    {price:,}원
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
            "새로고침해도 보류 기록은 유지돼요."
        )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "구매하지 않기",
                type="primary",
                use_container_width=True
            ):

                db_update(
                    "checki_records",
                    {
                        "decision": "stop",
                        "hold_until": None
                    },
                    {
                        "id": record_id
                    }
                )

                st.success(
                    "구매하지 않기로 결정했어요."
                )

                time.sleep(.5)

                st.rerun()

        with c2:

            if st.button(
                "구매 계속하기",
                use_container_width=True
            ):

                db_update(
                    "checki_records",
                    {
                        "decision":
                            "continue",

                        "hold_until":
                            None
                    },
                    {
                        "id":
                            record_id
                    }
                )

                st.success(
                    "구매 계속으로 기록했어요."
                )

                time.sleep(.5)

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


    # --------------------------------------------------------
    # 효과
    # --------------------------------------------------------

    if stopped_count > 0:

        html(
            f"""
            <div class="card-green">

                <div class="card-title">
                    🎉 체키 효과
                </div>

                <div class="card-text">

                    지금까지

                    <b>{stopped_count}번</b>의 구매를
                    다시 생각했고,

                    <b>{saved_money:,}원</b>의 소비를
                    재검토했어요.

                </div>

            </div>
            """
        )


    # --------------------------------------------------------
    # 내 소비 데이터
    # --------------------------------------------------------

    expenses = get_expenses()

    total_expense = sum(
        int(x.get("amount") or 0)
        for x in expenses
    )

    html(
        '<div class="section">'
        '내 소비 데이터'
        '</div>'
    )

    html(
        f"""
        <div class="card">

            <div class="card-title">
                📊 기록된 소비
            </div>

            <div class="card-text">

                소비내역
                <b>{len(expenses)}건</b>

                <br>

                총
                <b>{total_expense:,}원</b>이
                기록되어 있어요.

            </div>

        </div>
        """
    )


# ============================================================
# FOOTER
# ============================================================

html("""
<div class="footer">

    CHECKI · AI 소비자 보호 서비스 MVP

    <br>

    AI 분석 결과는 소비자의 판단을 돕기 위한
    참고 정보입니다.

    <br>

    소비분석은 사용자가 직접 입력한 데이터를
    기준으로 제공됩니다.

</div>
""")
