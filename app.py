import streamlit as st
from google import genai
from PIL import Image
from supabase import create_client
from datetime import datetime, timedelta, timezone
import uuid
import requests
from bs4 import BeautifulSoup
import re
import time


# =========================================================
# 0. 기본 설정
# =========================================================

st.set_page_config(
    page_title="체키 | CHECKI",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed"
)

KST = timezone(timedelta(hours=9))


def now_kst():
    return datetime.now(KST)


def iso_now():
    return now_kst().isoformat()


# =========================================================
# 1. 전체 디자인
#    - Pretendard
#    - 모바일 상단 흰 영역 제거
#    - 이미지 미리보기 축소
# =========================================================

st.markdown(
    """
<style>

@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');


/* =====================================================
   STREAMLIT 기본 UI 제거
   ===================================================== */

[data-testid="stHeader"] {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
}

[data-testid="stToolbar"] {
    display: none !important;
    visibility: hidden !important;
}

[data-testid="stDecoration"] {
    display: none !important;
    visibility: hidden !important;
}

[data-testid="stStatusWidget"] {
    display: none !important;
    visibility: hidden !important;
}

#MainMenu {
    display: none !important;
    visibility: hidden !important;
}

header {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
}

footer {
    display: none !important;
    visibility: hidden !important;
}


/* =====================================================
   전체 페이지
   ===================================================== */

html,
body {
    margin: 0 !important;
    padding: 0 !important;
    overflow-x: hidden !important;
}

body,
html,
.stApp,
button,
input,
textarea,
select,
div,
span,
p {
    font-family:
        "Pretendard",
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif !important;
}

.stApp {
    margin: 0 !important;
    padding: 0 !important;
    overflow-x: hidden !important;

    background:
        linear-gradient(
            180deg,
            #edf8ff 0%,
            #f7fbff 38%,
            #ffffff 100%
        );
}


/* =====================================================
   Streamlit 상단 공간 제거
   ===================================================== */

[data-testid="stAppViewContainer"] {
    padding-top: 0 !important;
    margin-top: 0 !important;
}

[data-testid="stMain"] {
    padding-top: 0 !important;
    margin-top: 0 !important;
}

[data-testid="stMainBlockContainer"] {
    padding-top: 0.35rem !important;
    margin-top: 0 !important;
}

.block-container {
    padding-top: 0.35rem !important;
    padding-bottom: 4rem !important;
    max-width: 1000px !important;
    margin-top: 0 !important;
}


/* =====================================================
   CHECKI HEADER
   ===================================================== */

.checki-header {
    text-align: center;
    padding-top: 8px;
    padding-bottom: 11px;
}

.checki-logo {
    font-family: "Pretendard", sans-serif !important;
    font-size: 36px;
    font-weight: 900;
    letter-spacing: -0.065em;
    color: #1689F8;
    line-height: 1;
}

.checki-subtitle {
    font-size: 10px;
    font-weight: 750;
    letter-spacing: 0.18em;
    color: #7893A8;
    margin-top: 7px;
}


/* =====================================================
   HERO
   ===================================================== */

.hero {
    text-align: center;
    padding: 28px 10px 21px 10px;
}

.hero-title {
    font-family: "Pretendard", sans-serif !important;
    font-size: 29px;
    font-weight: 850;
    color: #172C3F;
    line-height: 1.32;
    letter-spacing: -0.045em;
}

.hero-blue {
    color: #1689F8;
}

.hero-desc {
    margin-top: 12px;
    color: #71879A;
    font-size: 14px;
    font-weight: 450;
    line-height: 1.7;
    letter-spacing: -0.02em;
}


/* =====================================================
   카드
   ===================================================== */

.checki-card {
    background: rgba(255, 255, 255, 0.94);
    border: 1px solid #E2EEF7;
    border-radius: 22px;
    padding: 21px;
    margin: 12px 0;

    box-shadow:
        0 8px 28px
        rgba(25, 104, 165, 0.065);
}

.card-title {
    font-size: 17px;
    font-weight: 750;
    color: #19364D;
    letter-spacing: -0.025em;
    margin-bottom: 6px;
}

.card-desc {
    color: #71899C;
    font-size: 13px;
    font-weight: 450;
    line-height: 1.6;
    letter-spacing: -0.015em;
}


/* =====================================================
   분석 결과
   ===================================================== */

.result-low,
.result-medium,
.result-high {
    border-radius: 20px;
    padding: 20px;
    margin-top: 18px;
}

.result-low {
    background: #EFFBF5;
    border: 1px solid #C8EEDB;
}

.result-medium {
    background: #FFF9E9;
    border: 1px solid #F5DF9F;
}

.result-high {
    background: #FFF1F1;
    border: 1px solid #F3C6C6;
}

.risk-title {
    font-size: 20px;
    font-weight: 850;
    letter-spacing: -0.035em;
    color: #18334A;
}


/* =====================================================
   AI 추출 가격
   ===================================================== */

.price-box {
    background: #F1F8FF;
    border: 1px solid #D8EAFB;
    border-radius: 16px;
    padding: 15px 17px;
    margin: 12px 0;
    color: #526E83;
    font-size: 13px;
}


/* =====================================================
   METRIC
   ===================================================== */

[data-testid="stMetric"] {
    background: rgba(255,255,255,0.94);
    border: 1px solid #E3EDF5;
    border-radius: 18px;
    padding: 16px;

    box-shadow:
        0 5px 18px
        rgba(25,104,165,0.05);
}


/* =====================================================
   INPUT
   ===================================================== */

.stTextInput input,
.stNumberInput input,
.stTextArea textarea {

    border-radius: 14px !important;
    border-color: #DCE8F1 !important;

    font-family:
        "Pretendard",
        sans-serif !important;
}

[data-baseweb="select"] > div {
    border-radius: 14px !important;
}


/* =====================================================
   BUTTON
   ===================================================== */

.stButton > button {
    border-radius: 14px !important;
    min-height: 46px !important;

    font-family:
        "Pretendard",
        sans-serif !important;

    font-weight: 700 !important;
    letter-spacing: -0.02em !important;

    transition:
        transform 0.15s ease,
        opacity 0.15s ease !important;
}

.stButton > button:hover {
    transform: translateY(-1px);
}

.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {

    background:
        linear-gradient(
            135deg,
            #1689F8,
            #42AAFF
        ) !important;

    color: white !important;
    border: none !important;

    box-shadow:
        0 5px 15px
        rgba(22,137,248,0.20) !important;
}

.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover {

    background:
        linear-gradient(
            135deg,
            #087EF0,
            #319EF8
        ) !important;

    color: white !important;
}


/* =====================================================
   RADIO NAVIGATION
   ===================================================== */

div[role="radiogroup"] {
    display: flex;
    justify-content: center;
    gap: 3px;

    background: rgba(255,255,255,0.95);

    border:
        1px solid #E1ECF5;

    border-radius: 17px;

    padding: 5px;

    box-shadow:
        0 4px 18px
        rgba(26,111,175,0.045);
}

div[role="radiogroup"] label {
    flex: 1;
    justify-content: center;
    font-weight: 650;
}


/* =====================================================
   이미지 미리보기
   ===================================================== */

[data-testid="stImage"] {
    text-align: center !important;
}

[data-testid="stImage"] img {

    max-width: 360px !important;

    width: auto !important;
    height: auto !important;

    object-fit: contain !important;

    border-radius: 17px !important;

    display: block !important;

    margin:
        8px auto
        15px auto !important;

    box-shadow:
        0 5px 20px
        rgba(24,91,143,0.08);
}


/* =====================================================
   FILE UPLOADER
   ===================================================== */

[data-testid="stFileUploader"] {

    background:
        rgba(255,255,255,0.65);

    border-radius: 18px;
}


/* =====================================================
   MOBILE
   ===================================================== */

@media (max-width: 768px) {

    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    header {

        display: none !important;
        visibility: hidden !important;

        height: 0 !important;
        min-height: 0 !important;
        max-height: 0 !important;

        margin: 0 !important;
        padding: 0 !important;
    }


    html,
    body,
    .stApp {

        margin: 0 !important;
        padding: 0 !important;

        padding-top: 0 !important;

        overflow-x: hidden !important;
    }


    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {

        padding-top: 0 !important;
        margin-top: 0 !important;
    }


    [data-testid="stMainBlockContainer"],
    .block-container {

        padding-top: 0.1rem !important;

        margin-top: 0 !important;

        padding-left: 0.9rem !important;
        padding-right: 0.9rem !important;
    }


    .checki-header {
        padding-top: 5px !important;
        padding-bottom: 9px !important;
    }


    .checki-logo {
        font-size: 32px !important;
    }


    .checki-subtitle {
        font-size: 8.5px !important;
        margin-top: 5px !important;
    }


    .hero {
        padding:
            20px 5px
            16px 5px !important;
    }


    .hero-title {
        font-size: 25px !important;
        line-height: 1.34 !important;
    }


    .hero-desc {
        font-size: 13px !important;
        margin-top: 9px !important;
    }


    .checki-card {

        padding: 17px !important;

        border-radius:
            18px !important;
    }


    .card-title {
        font-size: 16px !important;
    }


    div[role="radiogroup"] {

        overflow-x: auto;

        border-radius:
            15px !important;
    }


    div[role="radiogroup"] label {

        font-size:
            12px !important;
    }


    /* 모바일 이미지 더 작게 */

    [data-testid="stImage"] img {

        max-width:
            260px !important;

        width:
            auto !important;

        height:
            auto !important;

        margin-left:
            auto !important;

        margin-right:
            auto !important;
    }


    [data-testid="stMetric"] {

        padding:
            12px !important;
    }
}

</style>
""",
    unsafe_allow_html=True
)


# =========================================================
# 2. SECRETS
# =========================================================

try:

    GEMINI_API_KEY = st.secrets[
        "GEMINI_API_KEY"
    ]

    SUPABASE_URL = st.secrets[
        "SUPABASE_URL"
    ]

    SUPABASE_KEY = st.secrets[
        "SUPABASE_KEY"
    ]

except Exception:

    st.error(
        "앱 설정 정보를 불러오지 못했습니다. "
        "Streamlit Secrets 설정을 확인해주세요."
    )

    st.stop()


# =========================================================
# 3. GEMINI
# =========================================================

try:

    gemini = genai.Client(
        api_key=GEMINI_API_KEY
    )

except Exception:

    gemini = None


# =========================================================
# 4. SUPABASE
# =========================================================

if "supabase_client" not in st.session_state:

    try:

        st.session_state[
            "supabase_client"
        ] = create_client(
            SUPABASE_URL,
            SUPABASE_KEY
        )

    except Exception:

        st.session_state[
            "supabase_client"
        ] = None


supabase = st.session_state[
    "supabase_client"
]


# =========================================================
# 5. USER ID
# =========================================================

if "user_id" not in st.session_state:

    try:

        if "uid" in st.query_params:

            uid = st.query_params[
                "uid"
            ]

            if isinstance(
                uid,
                list
            ):

                uid = uid[0]

            st.session_state[
                "user_id"
            ] = uid

        else:

            uid = str(
                uuid.uuid4()
            )

            st.session_state[
                "user_id"
            ] = uid

            st.query_params[
                "uid"
            ] = uid

    except Exception:

        st.session_state[
            "user_id"
        ] = str(
            uuid.uuid4()
        )


user_id = st.session_state[
    "user_id"
]


# =========================================================
# 6. DATABASE
# =========================================================

def get_expenses():

    if supabase is None:
        return []

    try:

        response = (
            supabase
            .table(
                "checki_expenses"
            )
            .select("*")
            .eq(
                "user_id",
                user_id
            )
            .order(
                "created_at",
                desc=True
            )
            .execute()
        )

        return response.data or []

    except Exception:

        return []


def get_records():

    if supabase is None:
        return []

    try:

        response = (
            supabase
            .table(
                "checki_records"
            )
            .select("*")
            .eq(
                "user_id",
                user_id
            )
            .order(
                "created_at",
                desc=True
            )
            .execute()
        )

        return response.data or []

    except Exception:

        return []


def add_expense(
    category,
    item_name,
    amount
):

    if supabase is None:
        return False

    try:

        data = {

            "user_id":
                user_id,

            "category":
                category,

            "item_name":
                item_name,

            "amount":
                int(amount),

            "purchased_at":
                now_kst()
                .date()
                .isoformat(),

            "created_at":
                iso_now()
        }

        (
            supabase
            .table(
                "checki_expenses"
            )
            .insert(data)
            .execute()
        )

        return True

    except Exception:

        return False


def save_analysis_record(
    product_name,
    category,
    product_price,
    risk_level,
    risk_score,
    summary,
    detected,
    ai_result
):

    if supabase is None:
        return None

    try:

        hold_started = now_kst()

        hold_until = (
            hold_started
            + timedelta(
                minutes=30
            )
        )

        data = {

            "user_id":
                user_id,

            "product_name":
                product_name,

            "category":
                category,

            "product_price":
                int(
                    product_price
                    or 0
                ),

            "risk_level":
                risk_level,

            "risk_score":
                int(
                    risk_score
                    or 0
                ),

            "one_line_summary":
                summary,

            "detected_elements":
                detected,

            "ai_result":
                ai_result,

            "action_text":
                "30분 생각하기",

            "decision":
                "HOLD",

            "saved_amount":
                0,

            "hold_started_at":
                hold_started
                .isoformat(),

            "hold_until":
                hold_until
                .isoformat(),

            "created_at":
                hold_started
                .isoformat()
        }

        response = (
            supabase
            .table(
                "checki_records"
            )
            .insert(data)
            .execute()
        )

        if response.data:

            return response.data[0]

        return None

    except Exception:

        return None


def update_record(
    record_id,
    decision,
    saved_amount=0
):

    if (
        supabase is None
        or record_id is None
    ):

        return False

    try:

        data = {

            "decision":
                decision,

            "saved_amount":
                int(
                    saved_amount
                    or 0
                ),

            "decided_at":
                iso_now()
        }

        (
            supabase
            .table(
                "checki_records"
            )
            .update(data)
            .eq(
                "id",
                record_id
            )
            .execute()
        )

        return True

    except Exception:

        return False


# =========================================================
# 7. URL 분석
# =========================================================

def read_url(url):

    if not url:
        return None

    if not url.startswith(
        (
            "http://",
            "https://"
        )
    ):

        url = (
            "https://"
            + url
        )

    headers = {

        "User-Agent":
            "Mozilla/5.0 "
            "(Linux; Android 13) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 "
            "Safari/537.36"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=8
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        for tag in soup(
            [
                "script",
                "style",
                "noscript"
            ]
        ):

            tag.decompose()

        title = ""

        if soup.title:

            title = (
                soup.title
                .get_text(
                    " ",
                    strip=True
                )
            )

        text = soup.get_text(
            " ",
            strip=True
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        text = text[:12000]

        return (
            f"페이지 제목: {title}\n\n"
            f"페이지 내용:\n{text}"
        )

    except Exception:

        return None


# =========================================================
# 8. GEMINI RETRY
# =========================================================

def generate_with_retry(
    contents,
    retries=3
):

    if gemini is None:

        raise Exception(
            "Gemini client unavailable"
        )

    last_error = None

    for i in range(
        retries
    ):

        try:

            return (
                gemini.models
                .generate_content(
                    model=
                        "gemini-2.5-flash",

                    contents=
                        contents
                )
            )

        except Exception as e:

            last_error = e

            msg = str(e).lower()

            retryable = (

                "503" in msg
                or
                "unavailable"
                in msg
                or
                "high demand"
                in msg
                or
                "429"
                in msg
                or
                "resource exhausted"
                in msg
            )

            if (
                retryable
                and
                i < retries - 1
            ):

                time.sleep(
                    2 * (i + 1)
                )

                continue

            raise

    raise last_error


# =========================================================
# 9. AI 응답 파싱
# =========================================================

def parse_field(
    text,
    field,
    default=""
):

    pattern = (
        rf"{field}\s*:\s*(.+)"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if match:

        return (
            match.group(1)
            .strip()
        )

    return default


def parse_price(
    value
):

    if not value:
        return 0

    numbers = re.sub(
        r"[^0-9]",
        "",
        str(value)
    )

    try:

        return int(
            numbers
        )

    except Exception:

        return 0


def parse_score(
    value
):

    if not value:
        return 0

    match = re.search(
        r"\d+",
        str(value)
    )

    if not match:
        return 0

    score = int(
        match.group()
    )

    return max(
        0,
        min(
            score,
            100
        )
    )


# =========================================================
# 10. AI 구매 분석
# =========================================================

def analyze_product(
    product_name,
    category,
    image=None,
    page_text=None
):

    instructions = f"""
너는 소비자를 보호하는 AI 서비스
'체키(CHECKI)'다.

사용자가 구매하려는 상품 또는 쇼핑 페이지를 분석하여
소비자가 충동구매, 불필요한 지출,
다크패턴의 영향을 받고 있는지 판단한다.

상품명:
{product_name}

카테고리:
{category}

다음 요소를 중심으로 확인한다.

1. 거짓 또는 과장된 긴급성
2. 재고 부족 압박
3. 시간 제한 압박
4. 다른 소비자의 구매를 강조하는 사회적 증거
5. 과도한 할인 강조
6. 원래 가격과 할인 가격의 혼동
7. 추가 옵션의 사전 선택
8. 숨겨진 비용
9. 구독 유도
10. 해지 또는 거절을 어렵게 만드는 표현
11. 즉각적인 구매를 유도하는 문구
12. 충동구매 가능성을 높이는 화면 구성

화면이나 페이지에서 상품의 현재 판매 가격을
확실히 확인할 수 있다면 PRICE에 숫자로 추출한다.

쿠폰 적용 여부나 여러 가격이 있어
실제 판매가격을 확실히 판단할 수 없다면
가장 명확하게 표시된 현재 판매가격을 사용한다.

가격을 알 수 없다면 PRICE는 0이다.

RISK_LEVEL은
LOW, MEDIUM, HIGH 중 하나다.

RISK_SCORE는
0부터 100까지의 정수다.

반드시 다음 형식을 사용한다.

PRODUCT_NAME: 상품명
PRICE: 숫자만
RISK_LEVEL: LOW 또는 MEDIUM 또는 HIGH
RISK_SCORE: 숫자
SUMMARY: 소비자가 바로 이해할 수 있는 한 문장
DETECTED: 발견된 다크패턴 또는 구매 압박 요소. 없으면 없음
ADVICE: 구매 전에 확인하면 좋은 점을 짧게 설명
"""

    contents = [
        instructions
    ]

    if page_text:

        contents.append(
            f"""
분석할 쇼핑 페이지 정보:

{page_text}
"""
        )

    if image is not None:

        contents.append(
            image
        )

    response = (
        generate_with_retry(
            contents
        )
    )

    result = (
        response.text
        or ""
    )

    extracted_name = (
        parse_field(
            result,
            "PRODUCT_NAME",
            product_name
        )
    )

    price = parse_price(
        parse_field(
            result,
            "PRICE",
            "0"
        )
    )

    risk_level = (
        parse_field(
            result,
            "RISK_LEVEL",
            "MEDIUM"
        )
        .upper()
    )

    if risk_level not in [
        "LOW",
        "MEDIUM",
        "HIGH"
    ]:

        risk_level = "MEDIUM"

    risk_score = parse_score(
        parse_field(
            result,
            "RISK_SCORE",
            "50"
        )
    )

    summary = parse_field(
        result,
        "SUMMARY",
        "구매 전 한 번 더 확인해보세요."
    )

    detected = parse_field(
        result,
        "DETECTED",
        "확인 필요"
    )

    advice = parse_field(
        result,
        "ADVICE",
        "구매 필요성과 가격을 다시 확인해보세요."
    )

    return {

        "product_name":
            extracted_name,

        "price":
            price,

        "risk_level":
            risk_level,

        "risk_score":
            risk_score,

        "summary":
            summary,

        "detected":
            detected,

        "advice":
            advice,

        "raw":
            result
    }


# =========================================================
# 11. HEADER
# =========================================================

st.markdown(
    """
<div class="checki-header">

    <div class="checki-logo">
        체키
    </div>

    <div class="checki-subtitle">
        CHECK BEFORE YOU BUY
    </div>

</div>
""",
    unsafe_allow_html=True
)


# =========================================================
# 12. NAVIGATION
# =========================================================

page = st.radio(
    "navigation",

    [
        "홈",
        "구매체크",
        "소비분석",
        "MY"
    ],

    horizontal=True,

    label_visibility=
        "collapsed"
)


# =========================================================
# 13. HOME
# =========================================================

if page == "홈":

    st.markdown(
        """
<div class="hero">

    <div class="hero-title">

        사기 전에,
        <span class="hero-blue">
            체키
        </span>
        해보세요.

    </div>

    <div class="hero-desc">

        쇼핑 화면이나 링크를 분석해<br>
        나도 모르게 구매를 유도하는 요소를 찾아드려요.

    </div>

</div>
""",
        unsafe_allow_html=True
    )


    st.markdown(
        """
<div class="checki-card">

    <div class="card-title">
        🔎 구매 전 AI 체크
    </div>

    <div class="card-desc">

        상품 페이지의 할인·재고·시간 압박 등
        구매를 재촉하는 요소를 AI가 분석합니다.

    </div>

</div>


<div class="checki-card">

    <div class="card-title">
        ⏱️ 30분 생각하기
    </div>

    <div class="card-desc">

        바로 결제하지 않고 잠시 멈춰
        정말 필요한 소비인지 다시 판단할 수 있습니다.

    </div>

</div>


<div class="checki-card">

    <div class="card-title">
        📊 소비 기록 확인
    </div>

    <div class="card-desc">

        구매한 금액과
        구매하지 않아 아낀 금액을 확인할 수 있습니다.

    </div>

</div>
""",
        unsafe_allow_html=True
    )


# =========================================================
# 14. 구매체크
# =========================================================

elif page == "구매체크":

    st.markdown(
        """
<div class="hero">

    <div class="hero-title">

        구매 전
        <span class="hero-blue">
            체키
        </span>

    </div>

    <div class="hero-desc">

        쇼핑 화면을 캡처하거나
        상품 링크를 넣어주세요.

    </div>

</div>
""",
        unsafe_allow_html=True
    )


    product_name = st.text_input(
        "상품명",
        placeholder=
            "예: 무선 이어폰"
    )


    category = st.selectbox(
        "카테고리",

        [
            "패션/의류",
            "뷰티",
            "식품",
            "생활용품",
            "전자기기",
            "가구/인테리어",
            "취미/여가",
            "구독서비스",
            "기타"
        ]
    )


    input_type = st.radio(
        "분석 방법",

        [
            "스크린샷",
            "상품 링크"
        ],

        horizontal=True
    )


    uploaded_image = None
    product_url = None


    # -----------------------------------------------------
    # 스크린샷
    # -----------------------------------------------------

    if input_type == "스크린샷":

        uploaded_file = (
            st.file_uploader(
                "쇼핑 화면을 올려주세요",

                type=[
                    "png",
                    "jpg",
                    "jpeg",
                    "webp"
                ]
            )
        )


        if uploaded_file:

            uploaded_image = (
                Image.open(
                    uploaded_file
                )
            )


            # ---------------------------------------------
            # 미리보기만 작게 표시
            # AI 분석에는 원본 사용
            # ---------------------------------------------

            img_width, img_height = (
                uploaded_image.size
            )

            preview_width = min(
                360,
                img_width
            )

            st.image(
                uploaded_image,
                width=preview_width
            )


    # -----------------------------------------------------
    # URL
    # -----------------------------------------------------

    else:

        product_url = (
            st.text_input(
                "상품 링크",

                placeholder=
                    "https://..."
            )
        )


    analyze_clicked = st.button(
        "체키로 분석하기",

        type="primary",

        use_container_width=True
    )


    # -----------------------------------------------------
    # 분석 실행
    # -----------------------------------------------------

    if analyze_clicked:

        if not product_name.strip():

            st.warning(
                "상품명을 입력해주세요."
            )


        elif (
            input_type
            == "스크린샷"
            and
            uploaded_image is None
        ):

            st.warning(
                "분석할 쇼핑 화면을 올려주세요."
            )


        elif (
            input_type
            == "상품 링크"
            and
            not product_url
        ):

            st.warning(
                "상품 링크를 입력해주세요."
            )


        else:

            page_text = None


            # URL 분석
            if (
                input_type
                == "상품 링크"
            ):

                with st.spinner(
                    "상품 페이지를 확인하고 있어요..."
                ):

                    page_text = read_url(
                        product_url
                    )


                if page_text is None:

                    st.warning(
                        "이 쇼핑몰은 상품 페이지를 "
                        "자동으로 읽지 못했어요. "
                        "상품 화면을 캡처한 뒤 "
                        "스크린샷 분석을 이용해주세요."
                    )

                    st.stop()


            # Gemini 분석
            try:

                with st.spinner(
                    "체키가 구매 화면을 분석하고 있어요..."
                ):

                    result = (
                        analyze_product(

                            product_name=
                                product_name,

                            category=
                                category,

                            image=
                                uploaded_image,

                            page_text=
                                page_text
                        )
                    )


                st.session_state[
                    "latest_analysis"
                ] = result


                saved_record = (
                    save_analysis_record(

                        product_name=
                            result[
                                "product_name"
                            ],

                        category=
                            category,

                        product_price=
                            result[
                                "price"
                            ],

                        risk_level=
                            result[
                                "risk_level"
                            ],

                        risk_score=
                            result[
                                "risk_score"
                            ],

                        summary=
                            result[
                                "summary"
                            ],

                        detected=
                            result[
                                "detected"
                            ],

                        ai_result=
                            result[
                                "raw"
                            ]
                    )
                )


                st.session_state[
                    "latest_record"
                ] = saved_record


            except Exception as e:

                error_text = str(e)


                if (
                    "503"
                    in error_text

                    or

                    "high demand"
                    in error_text.lower()

                    or

                    "unavailable"
                    in error_text.lower()

                    or

                    "429"
                    in error_text
                ):

                    st.error(
                        "현재 AI 사용량이 많아요. "
                        "잠시 후 다시 분석해주세요."
                    )

                else:

                    st.error(
                        "분석 중 문제가 발생했습니다. "
                        "잠시 후 다시 시도해주세요."
                    )


    # =====================================================
    # 분석 결과 표시
    # =====================================================

    if (
        "latest_analysis"
        in st.session_state
    ):

        result = (
            st.session_state[
                "latest_analysis"
            ]
        )


        level = result[
            "risk_level"
        ]


        if level == "LOW":

            css_class = (
                "result-low"
            )

            risk_text = (
                "낮음 🟢"
            )


        elif level == "HIGH":

            css_class = (
                "result-high"
            )

            risk_text = (
                "높음 🔴"
            )


        else:

            css_class = (
                "result-medium"
            )

            risk_text = (
                "주의 🟡"
            )


        st.markdown(
            f"""
<div class="{css_class}">

    <div class="risk-title">
        구매 유도 위험도 {risk_text}
    </div>

    <br>

    <b>위험 점수</b><br>
    {result["risk_score"]} / 100

    <br><br>

    <b>체키 한줄 요약</b><br>
    {result["summary"]}

    <br><br>

    <b>발견된 요소</b><br>
    {result["detected"]}

    <br><br>

    <b>체키의 제안</b><br>
    {result["advice"]}

</div>
""",
            unsafe_allow_html=True
        )


        # -------------------------------------------------
        # AI가 가격을 읽은 경우
        # -------------------------------------------------

        if result[
            "price"
        ] > 0:

            st.markdown(
                f"""
<div class="price-box">

    AI가 화면에서 확인한 가격

    <br>

    <b style="
        font-size:22px;
        color:#1689F8;
        letter-spacing:-0.04em;
    ">

        {result["price"]:,}원

    </b>

</div>
""",
                unsafe_allow_html=True
            )


        else:

            st.info(
                "화면에서 정확한 상품 가격을 "
                "확인하지 못했어요."
            )


        st.markdown(
            "### ⏱️ 30분 생각하기"
        )


        st.caption(
            "바로 결제하기 전에 잠시 멈춰 "
            "정말 필요한 구매인지 다시 생각해보세요."
        )


        record = (
            st.session_state
            .get(
                "latest_record"
            )
        )


        if record:

            st.success(
                "구매 보류가 시작되었습니다. "
                "MY에서 기록을 확인할 수 있어요."
            )


# =========================================================
# 15. 소비분석
# =========================================================

elif page == "소비분석":

    st.markdown(
        """
<div class="hero">

    <div class="hero-title">

        나의
        <span class="hero-blue">
            소비 분석
        </span>

    </div>

    <div class="hero-desc">

        체키에 저장된 실제 소비 기록을 기준으로 확인합니다.

    </div>

</div>
""",
        unsafe_allow_html=True
    )


    expenses = get_expenses()

    records = get_records()


    total_spent = sum(

        int(
            x.get(
                "amount",
                0
            )
            or 0
        )

        for x
        in expenses
    )


    total_saved = sum(

        int(
            x.get(
                "saved_amount",
                0
            )
            or 0
        )

        for x
        in records
    )


    avoided = len(

        [
            x

            for x
            in records

            if (
                x.get(
                    "decision"
                )
                == "NOT_BUY"
            )
        ]
    )


    c1, c2, c3 = (
        st.columns(3)
    )


    with c1:

        st.metric(
            "총 소비",
            f"{total_spent:,}원"
        )


    with c2:

        st.metric(
            "아낀 금액",
            f"{total_saved:,}원"
        )


    with c3:

        st.metric(
            "구매하지 않음",
            f"{avoided}회"
        )


    st.markdown(
        "### 최근 소비"
    )


    if not expenses:

        st.info(
            "아직 등록된 소비가 없어요."
        )


    else:

        for expense in (
            expenses[:10]
        ):

            amount = int(

                expense.get(
                    "amount",
                    0
                )
                or 0
            )


            st.markdown(
                f"""
<div class="checki-card">

    <div class="card-title">
        {expense.get("item_name", "상품")}
    </div>

    <div class="card-desc">
        {expense.get("category", "기타")}
    </div>

    <br>

    <b style="
        font-size:18px;
        color:#18344B;
    ">

        {amount:,}원

    </b>

</div>
""",
                unsafe_allow_html=True
            )


# =========================================================
# 16. MY
# =========================================================

elif page == "MY":

    st.markdown(
        """
<div class="hero">

    <div class="hero-title">

        나의
        <span class="hero-blue">
            체키 기록
        </span>

    </div>

    <div class="hero-desc">

        구매하기 전 한 번 멈춰본 기록을 확인해보세요.

    </div>

</div>
""",
        unsafe_allow_html=True
    )


    records = get_records()


    if not records:

        st.info(
            "아직 체키 기록이 없어요."
        )


    else:

        for index, record in enumerate(
            records[:20]
        ):

            product = record.get(
                "product_name",
                "상품"
            )


            category = record.get(
                "category",
                "기타"
            )


            price = int(
                record.get(
                    "product_price",
                    0
                )
                or 0
            )


            decision = record.get(
                "decision",
                "HOLD"
            )


            risk = record.get(
                "risk_level",
                "MEDIUM"
            )


            record_id = record.get(
                "id"
            )


            if price > 0:

                price_text = (
                    f"AI 확인 가격: "
                    f"{price:,}원"
                )

            else:

                price_text = (
                    "가격 확인 안 됨"
                )


            st.markdown(
                f"""
<div class="checki-card">

    <div class="card-title">
        {product}
    </div>

    <div class="card-desc">

        {category}
        ·
        위험도 {risk}

    </div>

    <br>

    <b>
        {price_text}
    </b>

</div>
""",
                unsafe_allow_html=True
            )


            # =================================================
            # HOLD 상태
            # =================================================

            if decision == "HOLD":

                hold_until_text = (
                    record.get(
                        "hold_until"
                    )
                )


                hold_finished = True

                hold_until = None


                if hold_until_text:

                    try:

                        hold_until = (
                            datetime
                            .fromisoformat(
                                hold_until_text
                                .replace(
                                    "Z",
                                    "+00:00"
                                )
                            )
                        )


                        if (
                            hold_until.tzinfo
                            is None
                        ):

                            hold_until = (
                                hold_until
                                .replace(
                                    tzinfo=KST
                                )
                            )


                        hold_finished = (

                            now_kst()

                            >=

                            hold_until
                            .astimezone(
                                KST
                            )
                        )


                    except Exception:

                        hold_finished = True


                # ---------------------------------------------
                # 아직 30분 안 지난 경우
                # ---------------------------------------------

                if not hold_finished:

                    remaining = (

                        hold_until
                        .astimezone(
                            KST
                        )

                        -

                        now_kst()
                    )


                    seconds = max(
                        0,
                        int(
                            remaining
                            .total_seconds()
                        )
                    )


                    minutes = (
                        seconds // 60
                    )

                    seconds_left = (
                        seconds % 60
                    )


                    st.info(
                        f"아직 생각하는 중이에요. "
                        f"{minutes}분 "
                        f"{seconds_left}초 남았습니다."
                    )


                # ---------------------------------------------
                # 30분 지난 경우
                # ---------------------------------------------

                else:

                    st.write(
                        "30분이 지났어요. "
                        "이 상품을 구매하셨나요?"
                    )


                    col1, col2 = (
                        st.columns(2)
                    )


                    with col1:

                        if st.button(
                            "구매하지 않았어요",

                            key=
                                f"no_{record_id}_{index}",

                            use_container_width=
                                True
                        ):

                            saved = (

                                price

                                if price > 0

                                else 0
                            )


                            if update_record(
                                record_id,
                                "NOT_BUY",
                                saved
                            ):

                                st.success(
                                    "좋아요! "
                                    "구매하지 않은 기록을 저장했어요."
                                )

                                st.rerun()


                    with col2:

                        if st.button(
                            "구매했어요",

                            key=
                                f"yes_{record_id}_{index}",

                            type=
                                "primary",

                            use_container_width=
                                True
                        ):

                            st.session_state[
                                "buy_record"
                            ] = record_id


                # ---------------------------------------------
                # 구매 선택 후 실제 결제 금액 입력
                # ---------------------------------------------

                if (
                    st.session_state.get(
                        "buy_record"
                    )
                    == record_id
                ):

                    actual_amount = (
                        st.number_input(

                            "실제로 결제한 금액",

                            min_value=0,

                            step=1000,

                            value=(
                                price
                                if price > 0
                                else 0
                            ),

                            key=
                                f"amount_{record_id}"
                        )
                    )


                    if st.button(
                        "구매 기록 저장",

                        key=
                            f"save_buy_{record_id}",

                        type=
                            "primary",

                        use_container_width=
                            True
                    ):

                        expense_ok = (
                            add_expense(
                                category,
                                product,
                                actual_amount
                            )
                        )


                        record_ok = (
                            update_record(
                                record_id,
                                "BUY",
                                0
                            )
                        )


                        if (
                            expense_ok
                            and
                            record_ok
                        ):

                            st.session_state.pop(
                                "buy_record",
                                None
                            )

                            st.success(
                                "구매 기록을 저장했어요."
                            )

                            st.rerun()


                        else:

                            st.error(
                                "구매 기록 저장 중 "
                                "문제가 발생했습니다."
                            )


            # =================================================
            # 구매하지 않음
            # =================================================

            elif (
                decision
                == "NOT_BUY"
            ):

                saved = int(

                    record.get(
                        "saved_amount",
                        0
                    )
                    or 0
                )


                if saved > 0:

                    st.success(
                        f"구매하지 않음 · "
                        f"{saved:,}원 절약"
                    )


                else:

                    st.success(
                        "구매하지 않음"
                    )


            # =================================================
            # 구매 완료
            # =================================================

            elif (
                decision
                == "BUY"
            ):

                st.info(
                    "구매 완료"
                )
