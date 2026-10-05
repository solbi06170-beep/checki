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
import os
import base64
from io import BytesIO
import html


# =========================================================
# 0. 기본 설정
# =========================================================

st.set_page_config(
    page_title="CHECKI | 체키",
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
# 1. 마스코트 설정
# =========================================================

MASCOT_SCAN = "checki_mascot_scan.png"
MASCOT_SEARCH = "checki_mascot_search.png"
MASCOT_WAIT = "checki_mascot_wait.png"
MASCOT_CHART = "checki_mascot_chart.png"


def image_to_base64(path):
    if not os.path.exists(path):
        return None

    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def show_mascot(path, size=150, extra_class=""):
    encoded = image_to_base64(path)

    if not encoded:
        return

    st.markdown(
        f"""
        <div class="mascot-stage {extra_class}">
            <div class="mascot-box" style="--mascot-size:{size}px;">
                <img
                    src="data:image/png;base64,{encoded}"
                    class="checki-mascot"
                    alt="CHECKI mascot"
                >
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def show_uploaded_preview(image):
    try:
        img = image.copy()

        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        buffer = BytesIO()

        if img.mode == "RGBA":
            img.save(buffer, format="PNG")
            mime = "image/png"
        else:
            img.save(buffer, format="JPEG", quality=90)
            mime = "image/jpeg"

        encoded = base64.b64encode(
            buffer.getvalue()
        ).decode("utf-8")

        st.markdown(
            f"""
            <div class="preview-stage">
                <img
                    src="data:{mime};base64,{encoded}"
                    class="uploaded-preview"
                    alt="업로드한 쇼핑 화면"
                >
            </div>
            """,
            unsafe_allow_html=True
        )

    except Exception:
        st.image(image, width=320)


# =========================================================
# 2. 전체 디자인
# =========================================================

st.markdown(
    """
<style>

/* =====================================================
   FONT
   ===================================================== */

@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css');
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800;900&display=swap');


/* =====================================================
   COLOR
   ===================================================== */

:root {
    --blue: #1689F8;
    --blue2: #42AAFF;
    --navy: #172C3F;
    --text: #526D82;
    --muted: #8194A5;
    --border: #E2EDF6;
    --background: #F8FBFE;
}


/* =====================================================
   STREAMLIT 기본 UI 제거
   ===================================================== */

[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}

#MainMenu,
header,
footer {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}


/* =====================================================
   전체 폰트 통일
   ===================================================== */

html,
body {
    margin: 0 !important;
    padding: 0 !important;
    overflow-x: hidden !important;
}

html,
body,
.stApp,
button,
input,
textarea,
select,
label,
p,
span,
div,
small,
h1,
h2,
h3,
h4,
h5,
h6 {
    font-family:
        "Pretendard Variable",
        "Pretendard",
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif !important;

    letter-spacing: -0.025em;
}

.stApp {
    margin: 0 !important;
    padding: 0 !important;
    overflow-x: hidden !important;

    color: var(--navy);

    background:
        linear-gradient(
            180deg,
            #EEF8FF 0%,
            #F7FBFF 30%,
            #FFFFFF 68%
        );
}

[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    padding-top: 0 !important;
    margin-top: 0 !important;
}

[data-testid="stMainBlockContainer"],
.block-container {
    padding-top: 0.2rem !important;
    padding-bottom: 4rem !important;
    margin-top: 0 !important;
    max-width: 920px !important;
}


/* =====================================================
   STREAMLIT MARKDOWN 제목
   ===================================================== */

.stMarkdown h1,
.stMarkdown h2,
.stMarkdown h3,
.stMarkdown h4 {
    color: var(--navy) !important;
    font-weight: 850 !important;
    letter-spacing: -0.055em !important;
}

.stMarkdown h3 {
    font-size: 25px !important;
    margin-top: 25px !important;
    margin-bottom: 14px !important;
}


/* =====================================================
   LOGO
   ===================================================== */

.checki-header {
    width: 100%;
    text-align: center;
    padding: 15px 0 6px 0;
    margin: 0;
}

.checki-brand {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 9px;

    font-size: 32px;
    line-height: 1;

    letter-spacing: -0.055em;
}

.checki-brand-en {
    font-family:
        "Montserrat",
        "Pretendard Variable",
        sans-serif !important;

    color: var(--blue);

    font-weight: 900 !important;

    letter-spacing: -0.065em;
}

.checki-divider {
    color: #BDD0DE;

    font-weight: 800 !important;

    font-size: 25px;
}

.checki-brand-ko {
    color: var(--navy);

    font-weight: 900 !important;

    letter-spacing: -0.08em;
}

.checki-tagline {
    margin-top: 7px;

    color: #91A3B1;

    font-family:
        "Montserrat",
        "Pretendard Variable",
        sans-serif !important;

    font-size: 8px;

    font-weight: 800 !important;

    letter-spacing: 0.22em;
}


/* =====================================================
   NAVIGATION
   ===================================================== */

div[data-testid="stRadio"] {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}

div[data-testid="stRadio"] > div {
    margin-top: 0 !important;
}

div[role="radiogroup"] {
    display: flex !important;
    justify-content: center !important;

    width: fit-content !important;
    max-width: 100% !important;

    margin: 0 auto !important;

    gap: 2px;

    padding: 4px 7px;

    background: rgba(255,255,255,0.94);

    border: 1px solid #E1ECF5;

    border-radius: 999px;

    box-shadow:
        0 5px 18px
        rgba(25, 91, 142, 0.055);
}

div[role="radiogroup"] label {
    flex: none !important;

    padding: 3px 6px !important;

    font-size: 13px !important;

    font-weight: 700 !important;

    letter-spacing: -0.035em !important;

    color: #40586B !important;
}


/* =====================================================
   HERO
   ===================================================== */

.hero {
    text-align: center;

    padding:
        34px 8px
        8px 8px;
}

.hero-title {
    color: var(--navy);

    font-size: 31px;
    line-height: 1.3;

    font-weight: 900 !important;

    letter-spacing: -0.065em;
}

.hero-blue {
    color: var(--blue);

    font-weight: 900 !important;
}

.hero-desc {
    margin-top: 9px;

    color: #788D9E;

    font-size: 14px;
    line-height: 1.65;

    font-weight: 600 !important;

    letter-spacing: -0.035em;
}


/* =====================================================
   MASCOT
   ===================================================== */

.mascot-stage {
    width: 100%;

    display: flex;
    justify-content: center;
    align-items: center;

    margin:
        3px auto
        13px auto;

    padding: 0;

    text-align: center;
}

.mascot-box {
    width: var(--mascot-size);
    height: var(--mascot-size);

    display: flex;
    justify-content: center;
    align-items: center;

    overflow: hidden;

    margin: 0 auto;
    padding: 0;
}

.checki-mascot {
    display: block;

    width: 100%;
    height: 100%;

    object-fit: contain;
    object-position: center center;

    margin: 0 auto;
    padding: 0;

    border: 0;

    background: transparent;

    filter:
        drop-shadow(
            0 6px 10px
            rgba(32, 102, 160, 0.07)
        );
}

.result-mascot {
    margin-top: 18px;
    margin-bottom: 3px;
}

.wait-mascot {
    margin-top: 22px;
    margin-bottom: 1px;
}

.chart-mascot {
    margin-top: 2px;
    margin-bottom: 12px;
}

.my-wait-mascot {
    margin-top: 4px;
    margin-bottom: 4px;
}


/* =====================================================
   CARD
   ===================================================== */

.checki-card {
    background:
        rgba(255,255,255,0.95);

    border:
        1px solid var(--border);

    border-radius: 20px;

    padding: 20px;

    margin: 12px 0;

    box-shadow:
        0 8px 27px
        rgba(24,96,151,0.055);
}

.card-title {
    color: #19364D;

    font-size: 17px;

    font-weight: 850 !important;

    letter-spacing: -0.045em;

    margin-bottom: 6px;
}

.card-desc {
    color: #71899C;

    font-size: 13px;

    line-height: 1.6;

    font-weight: 600 !important;

    letter-spacing: -0.03em;
}


/* =====================================================
   FORM / LABEL
   ===================================================== */

label,
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p {
    font-weight: 750 !important;

    letter-spacing: -0.035em !important;

    color: #294154 !important;
}


/* =====================================================
   INPUT
   ===================================================== */

.stTextInput input,
.stNumberInput input,
.stTextArea textarea {
    border-radius: 13px !important;

    border-color: #DFE9F1 !important;

    background:
        rgba(247,249,251,0.94) !important;

    font-size: 14px !important;

    font-weight: 600 !important;

    min-height: 44px !important;

    color: #253D50 !important;
}

.stTextInput input::placeholder,
.stTextArea textarea::placeholder {
    color: #9BAAB6 !important;
    font-weight: 500 !important;
}

[data-baseweb="select"] > div {
    border-radius: 13px !important;

    border-color: #DFE9F1 !important;

    background:
        rgba(247,249,251,0.94) !important;

    min-height: 44px !important;

    font-weight: 650 !important;
}

[data-baseweb="select"] span {
    font-weight: 650 !important;
    color: #334C60 !important;
}


/* =====================================================
   FILE UPLOADER
   수정: Streamlit 기본 글자와 가짜 글자가 겹치지 않도록 함
   ===================================================== */

[data-testid="stFileUploader"] {
    border-radius: 16px !important;
}

[data-testid="stFileUploaderDropzone"] {
    background: #F7F9FB !important;

    border:
        1px dashed #CBDCE9 !important;

    border-radius: 16px !important;

    min-height: 90px !important;

    padding: 14px 18px !important;
}


/* 기본 버튼을 그대로 사용한다.
   ::before / ::after로 새 글자를 만들지 않는다. */

[data-testid="stFileUploaderDropzone"] button {
    min-width: 104px !important;

    height: 40px !important;
    min-height: 40px !important;

    padding: 0 15px !important;

    border-radius: 11px !important;

    background: #FFFFFF !important;

    border:
        1px solid #D6E3ED !important;

    box-shadow:
        0 3px 10px
        rgba(37,91,130,0.04) !important;

    color: #294154 !important;

    font-family:
        "Pretendard Variable",
        "Pretendard",
        sans-serif !important;

    font-size: 13px !important;

    font-weight: 750 !important;

    line-height: 1 !important;

    letter-spacing: -0.03em !important;
}


/* 버튼 내부 텍스트 정상 표시 */

[data-testid="stFileUploaderDropzone"] button *,
[data-testid="stFileUploaderDropzone"] button span,
[data-testid="stFileUploaderDropzone"] button p {
    display: inline !important;

    visibility: visible !important;

    color: #294154 !important;

    font-size: 13px !important;

    font-weight: 750 !important;

    line-height: 1 !important;
}


/* 업로드 아이콘만 제거 */

[data-testid="stFileUploaderDropzone"] svg {
    display: none !important;
}


/* 안내 문구 */

[data-testid="stFileUploaderDropzoneInstructions"] {
    color: #758B9C !important;
}

[data-testid="stFileUploaderDropzoneInstructions"] span {
    color: #758B9C !important;

    font-size: 12px !important;

    font-weight: 650 !important;
}

[data-testid="stFileUploaderDropzoneInstructions"] small {
    color: #9AABB8 !important;

    font-size: 10px !important;

    font-weight: 550 !important;
}


/* =====================================================
   업로드 이미지
   ===================================================== */

.preview-stage {
    width: 100%;

    display: flex;

    align-items: center;
    justify-content: center;

    margin:
        13px auto
        17px auto;
}

.uploaded-preview {
    display: block;

    width: auto;
    height: auto;

    max-width: 340px;
    max-height: 420px;

    object-fit: contain;

    margin: 0 auto;

    border-radius: 16px;

    border:
        1px solid #E4EDF4;

    box-shadow:
        0 7px 22px
        rgba(22,83,132,0.09);
}


/* =====================================================
   BUTTON
   ===================================================== */

.stButton > button {
    min-height: 47px !important;

    border-radius: 13px !important;

    font-family:
        "Pretendard Variable",
        "Pretendard",
        sans-serif !important;

    font-size: 14px !important;

    font-weight: 750 !important;

    letter-spacing:
        -0.035em !important;

    transition:
        all 0.15s ease !important;
}

.stButton > button p,
.stButton > button span {
    font-weight: 750 !important;
}

.stButton > button:hover {
    transform:
        translateY(-1px);
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
        0 6px 17px
        rgba(22,137,248,0.20) !important;
}


/* =====================================================
   RESULT
   ===================================================== */

.result-low,
.result-medium,
.result-high {
    border-radius: 19px;

    padding: 20px;

    margin-top: 9px;

    line-height: 1.65;

    letter-spacing: -0.025em;

    font-weight: 550;
}

.result-low {
    background: #EFFBF5;

    border:
        1px solid #C8EEDB;
}

.result-medium {
    background: #FFF9E9;

    border:
        1px solid #F3DEA1;
}

.result-high {
    background: #FFF1F1;

    border:
        1px solid #F2C5C5;
}

.risk-title {
    color: #18344B;

    font-size: 20px;

    font-weight: 850 !important;

    letter-spacing: -0.05em;
}

.result-low b,
.result-medium b,
.result-high b {
    font-weight: 800 !important;
    color: #27465E;
}

.price-box {
    background: #F1F8FF;

    border:
        1px solid #D8EAFB;

    border-radius: 15px;

    padding: 15px 17px;

    margin: 12px 0;

    color: #526E83;

    font-size: 13px;

    font-weight: 650;
}


/* =====================================================
   SECTION
   ===================================================== */

.section-center {
    text-align: center;

    margin:
        2px 0
        12px 0;
}

.section-title {
    color: #19364D;

    font-size: 20px;

    font-weight: 850 !important;

    letter-spacing: -0.055em;
}

.section-desc {
    color: #7A90A1;

    font-size: 13px;

    line-height: 1.6;

    font-weight: 550;

    margin-top: 5px;
}


/* =====================================================
   METRIC
   ===================================================== */

[data-testid="stMetric"] {
    background:
        rgba(255,255,255,0.97);

    border:
        1px solid #DDEAF3;

    border-radius: 18px;

    padding: 17px 18px !important;

    min-height: 114px;

    box-shadow:
        0 7px 22px
        rgba(25,104,165,0.055);
}

[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] *,
[data-testid="stMetricLabel"] p {
    font-family:
        "Pretendard Variable",
        "Pretendard",
        sans-serif !important;

    color: #526B7E !important;

    font-size: 13px !important;

    font-weight: 750 !important;

    letter-spacing: -0.04em !important;
}

[data-testid="stMetricValue"],
[data-testid="stMetricValue"] *,
[data-testid="stMetricValue"] div {
    font-family:
        "Pretendard Variable",
        "Pretendard",
        sans-serif !important;

    color: #172C3F !important;

    font-size: 31px !important;

    line-height: 1.15 !important;

    font-weight: 850 !important;

    letter-spacing: -0.055em !important;
}


/* =====================================================
   INFO / SUCCESS / WARNING
   ===================================================== */

[data-testid="stAlert"] {
    border-radius: 14px !important;
}

[data-testid="stAlert"] p,
[data-testid="stAlert"] div {
    font-weight: 600 !important;
    letter-spacing: -0.03em !important;
}

[data-testid="stNumberInput"] input {
    font-weight: 650 !important;
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

        overflow-x: hidden !important;
    }


    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {
        margin-top: 0 !important;

        padding-top: 0 !important;
    }


    [data-testid="stMainBlockContainer"],
    .block-container {
        margin-top: 0 !important;

        padding-top: 0 !important;

        padding-left: 0.9rem !important;

        padding-right: 0.9rem !important;
    }


    .checki-header {
        padding:
            10px 0
            5px 0 !important;
    }


    .checki-brand {
        font-size: 28px !important;

        gap: 7px !important;
    }


    .checki-divider {
        font-size: 22px !important;
    }


    .checki-tagline {
        margin-top: 6px !important;

        font-size: 7px !important;
    }


    div[role="radiogroup"] {
        margin-top: 0 !important;

        padding:
            3px 5px !important;
    }


    div[role="radiogroup"] label {
        font-size: 11.5px !important;

        font-weight: 700 !important;

        padding:
            2px 3px !important;
    }


    .hero {
        padding:
            27px 5px
            7px 5px !important;
    }


    .hero-title {
        font-size: 25px !important;
    }


    .hero-desc {
        font-size: 13px !important;

        font-weight: 550 !important;

        margin-top: 8px !important;
    }


    .mascot-box {
        width: 125px !important;
        height: 125px !important;
    }


    .my-wait-mascot .mascot-box {
        width: 100px !important;
        height: 100px !important;
    }


    .mascot-stage {
        margin-bottom: 9px !important;
    }


    .checki-card {
        padding: 17px !important;

        border-radius: 18px !important;
    }


    [data-testid="stFileUploaderDropzone"] {
        min-height: 82px !important;

        padding: 11px 12px !important;
    }


    [data-testid="stFileUploaderDropzone"] button {
        min-width: 92px !important;

        height: 38px !important;

        min-height: 38px !important;

        padding: 0 12px !important;

        font-size: 12px !important;
    }


    [data-testid="stFileUploaderDropzone"] button *,
    [data-testid="stFileUploaderDropzone"] button span,
    [data-testid="stFileUploaderDropzone"] button p {
        font-size: 12px !important;
    }


    [data-testid="stFileUploaderDropzoneInstructions"] span {
        font-size: 11px !important;
    }


    [data-testid="stFileUploaderDropzoneInstructions"] small {
        font-size: 9px !important;
    }


    .uploaded-preview {
        max-width: 245px !important;

        max-height: 330px !important;

        border-radius: 14px !important;
    }


    [data-testid="stMetric"] {
        padding: 13px 10px !important;

        min-height: 98px !important;
    }


    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] *,
    [data-testid="stMetricLabel"] p {
        font-size: 11px !important;

        font-weight: 750 !important;
    }


    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] *,
    [data-testid="stMetricValue"] div {
        font-size: 25px !important;

        font-weight: 850 !important;
    }


    .stMarkdown h3 {
        font-size: 22px !important;
    }
}

</style>
""",
    unsafe_allow_html=True
)


# =========================================================
# 3. SECRETS
# =========================================================

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

except Exception:
    st.error(
        "앱 설정 정보를 불러오지 못했습니다. "
        "Streamlit Secrets 설정을 확인해주세요."
    )
    st.stop()


# =========================================================
# 4. GEMINI
# =========================================================

try:
    gemini = genai.Client(
        api_key=GEMINI_API_KEY
    )

except Exception:
    gemini = None


# =========================================================
# 5. SUPABASE
# =========================================================

if "supabase_client" not in st.session_state:

    try:
        st.session_state["supabase_client"] = create_client(
            SUPABASE_URL,
            SUPABASE_KEY
        )

    except Exception:
        st.session_state["supabase_client"] = None


supabase = st.session_state["supabase_client"]


# =========================================================
# 6. USER ID
# =========================================================

if "user_id" not in st.session_state:

    try:

        if "uid" in st.query_params:

            uid = st.query_params["uid"]

            if isinstance(uid, list):
                uid = uid[0]

            st.session_state["user_id"] = uid

        else:

            uid = str(
                uuid.uuid4()
            )

            st.session_state["user_id"] = uid

            st.query_params["uid"] = uid

    except Exception:

        st.session_state["user_id"] = str(
            uuid.uuid4()
        )


user_id = st.session_state["user_id"]


# =========================================================
# 7. DATABASE
# =========================================================

def get_expenses():

    if supabase is None:
        return []

    try:

        response = (
            supabase
            .table("checki_expenses")
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
            .table("checki_records")
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
            .table("checki_expenses")
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
                hold_started.isoformat(),

            "hold_until":
                hold_until.isoformat(),

            "created_at":
                hold_started.isoformat()
        }

        response = (
            supabase
            .table("checki_records")
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
            .table("checki_records")
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
# 8. URL 읽기
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
            "Chrome/120.0 Safari/537.36"
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
# 9. GEMINI 자동 재시도
# =========================================================

def generate_with_retry(
    contents,
    retries=5
):

    if gemini is None:

        raise Exception(
            "Gemini client unavailable"
        )

    last_error = None

    for i in range(retries):

        try:

            response = (
                gemini
                .models
                .generate_content(
                    model=
                        "gemini-2.5-flash",

                    contents=
                        contents
                )
            )

            if response is None:
                raise Exception(
                    "Empty Gemini response"
                )

            return response

        except Exception as e:

            last_error = e

            msg = (
                str(e)
                .lower()
            )

            retryable = (
                "503" in msg
                or "unavailable" in msg
                or "high demand" in msg
                or "429" in msg
                or "resource exhausted" in msg
                or "500" in msg
                or "internal" in msg
                or "timeout" in msg
                or "timed out" in msg
                or "temporarily" in msg
            )

            if (
                retryable
                and i < retries - 1
            ):

                wait_seconds = 2 * (i + 1)

                time.sleep(
                    wait_seconds
                )

                continue

            raise

    raise last_error


# =========================================================
# 10. PARSING
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
            match
            .group(1)
            .strip()
        )

    return default


def parse_price(value):

    if not value:
        return 0

    numbers = re.sub(
        r"[^0-9]",
        "",
        str(value)
    )

    try:
        return int(numbers)

    except Exception:
        return 0


def parse_score(value):

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
# 11. AI ANALYSIS
# =========================================================

def analyze_product(
    product_name,
    category,
    image=None,
    page_text=None
):

    instructions = f"""
너는 소비자를 보호하는 AI 서비스 '체키(CHECKI)'다.

사용자가 구매하려는 상품 또는 쇼핑 페이지를 분석해서
소비자가 충동구매, 불필요한 지출 또는 다크패턴에
영향을 받고 있는지 판단한다.

상품명:
{product_name}

카테고리:
{category}

특히 다음 요소를 확인한다.

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

화면이나 페이지에서 상품 가격을 확인할 수 있다면
현재 실제 판매가격을 PRICE에 숫자로 추출한다.

가격을 확실히 알 수 없으면 PRICE는 0으로 한다.

위험도는 LOW, MEDIUM, HIGH 중 하나다.
RISK_SCORE는 0~100 사이 정수다.

반드시 다음 형식으로 답한다.

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
            "분석할 쇼핑 페이지 정보:\n\n"
            + page_text
        )

    if image is not None:

        contents.append(
            image
        )

    response = (
        generate_with_retry(
            contents,
            retries=5
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

    risk_score = (
        parse_score(
            parse_field(
                result,
                "RISK_SCORE",
                "50"
            )
        )
    )

    summary = (
        parse_field(
            result,
            "SUMMARY",
            "구매 전 한 번 더 확인해보세요."
        )
    )

    detected = (
        parse_field(
            result,
            "DETECTED",
            "확인 필요"
        )
    )

    advice = (
        parse_field(
            result,
            "ADVICE",
            "구매 필요성과 가격을 다시 확인해보세요."
        )
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
# 12. LOGO
# =========================================================

header_html = (
    '<div class="checki-header">'

    '<div class="checki-brand">'

    '<span class="checki-brand-en">'
    'CHECKI'
    '</span>'

    '<span class="checki-divider">'
    '|'
    '</span>'

    '<span class="checki-brand-ko">'
    '체키'
    '</span>'

    '</div>'

    '<div class="checki-tagline">'
    'CHECK BEFORE YOU BUY'
    '</div>'

    '</div>'
)

st.markdown(
    header_html,
    unsafe_allow_html=True
)


# =========================================================
# 13. NAVIGATION
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
# 14. HOME
# =========================================================

if page == "홈":

    hero_html = (
        '<div class="hero">'

        '<div class="hero-title">'
        '사기 전에, '
        '<span class="hero-blue">체키</span> '
        '해보세요.'
        '</div>'

        '<div class="hero-desc">'
        '쇼핑 화면이나 링크를 분석해<br>'
        '나도 모르게 구매를 유도하는 요소를 찾아드려요.'
        '</div>'

        '</div>'
    )

    st.markdown(
        hero_html,
        unsafe_allow_html=True
    )


    cards_html = (
        '<div class="checki-card">'

        '<div class="card-title">'
        '🔎 구매 전 AI 체크'
        '</div>'

        '<div class="card-desc">'
        '상품 페이지의 할인·재고·시간 압박 등 '
        '구매를 재촉하는 요소를 AI가 분석합니다.'
        '</div>'

        '</div>'


        '<div class="checki-card">'

        '<div class="card-title">'
        '⏱️ 30분 생각하기'
        '</div>'

        '<div class="card-desc">'
        '바로 결제하지 않고 잠시 멈춰 '
        '정말 필요한 소비인지 다시 판단할 수 있습니다.'
        '</div>'

        '</div>'


        '<div class="checki-card">'

        '<div class="card-title">'
        '📊 소비 기록 확인'
        '</div>'

        '<div class="card-desc">'
        '구매한 금액과 구매하지 않아 아낀 금액을 '
        '한눈에 확인할 수 있습니다.'
        '</div>'

        '</div>'
    )

    st.markdown(
        cards_html,
        unsafe_allow_html=True
    )


# =========================================================
# 15. 구매체크
# =========================================================

elif page == "구매체크":

    purchase_hero = (
        '<div class="hero">'

        '<div class="hero-title">'
        '구매 전 '
        '<span class="hero-blue">체키</span>'
        '</div>'

        '<div class="hero-desc">'
        '쇼핑 화면을 캡처하거나 상품 링크를 넣어주세요.'
        '</div>'

        '</div>'
    )

    st.markdown(
        purchase_hero,
        unsafe_allow_html=True
    )


    show_mascot(
        MASCOT_SCAN,
        size=150
    )


    product_name = (
        st.text_input(
            "상품명",

            placeholder=
                "예: 무선 이어폰"
        )
    )


    category = (
        st.selectbox(
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
    )


    input_type = (
        st.radio(
            "분석 방법",

            [
                "스크린샷",
                "상품 링크"
            ],

            horizontal=True
        )
    )


    uploaded_image = None
    product_url = None


    if (
        input_type
        == "스크린샷"
    ):

        uploaded_file = (
            st.file_uploader(
                "쇼핑 화면을 올려주세요",

                type=[
                    "png",
                    "jpg",
                    "jpeg",
                    "webp"
                ],

                label_visibility=
                    "visible"
            )
        )


        if uploaded_file:

            uploaded_image = (
                Image.open(
                    uploaded_file
                )
            )


            show_uploaded_preview(
                uploaded_image
            )


    else:

        product_url = (
            st.text_input(
                "상품 링크",

                placeholder=
                    "https://..."
            )
        )


    analyze_clicked = (
        st.button(
            "체키로 분석하기",

            type=
                "primary",

            use_container_width=
                True
        )
    )


    if analyze_clicked:

        if not product_name.strip():

            st.warning(
                "상품명을 입력해주세요."
            )


        elif (
            input_type
            == "스크린샷"
            and uploaded_image is None
        ):

            st.warning(
                "분석할 쇼핑 화면을 올려주세요."
            )


        elif (
            input_type
            == "상품 링크"
            and not product_url
        ):

            st.warning(
                "상품 링크를 입력해주세요."
            )


        else:

            page_text = None


            if (
                input_type
                == "상품 링크"
            ):

                with st.spinner(
                    "상품 페이지를 확인하고 있어요..."
                ):

                    page_text = (
                        read_url(
                            product_url
                        )
                    )


                if page_text is None:

                    st.warning(
                        "이 쇼핑몰은 상품 페이지를 "
                        "자동으로 읽지 못했어요. "
                        "상품 화면을 캡처한 뒤 "
                        "스크린샷 분석을 이용해주세요."
                    )

                    st.stop()


            try:

                with st.spinner(
                    "체키가 구매 화면을 분석하고 있어요. "
                    "일시적인 오류가 생기면 자동으로 다시 시도합니다..."
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

                error_text = (
                    str(e)
                    .lower()
                )


                if (
                    "503" in error_text

                    or "high demand" in error_text

                    or "unavailable" in error_text

                    or "429" in error_text

                    or "resource exhausted" in error_text

                    or "500" in error_text

                    or "timeout" in error_text
                ):

                    st.error(
                        "AI 서버가 계속 혼잡해서 "
                        "자동 재시도를 완료하지 못했어요. "
                        "잠시 뒤 분석 버튼을 한 번만 다시 눌러주세요."
                    )

                else:

                    st.error(
                        "분석 중 문제가 발생했습니다. "
                        "잠시 후 다시 시도해주세요."
                    )


    if (
        "latest_analysis"
        in st.session_state
    ):

        result = (
            st.session_state[
                "latest_analysis"
            ]
        )


        show_mascot(
            MASCOT_SEARCH,
            size=150,
            extra_class="result-mascot"
        )


        level = (
            result[
                "risk_level"
            ]
        )


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


        safe_summary = html.escape(
            str(
                result[
                    "summary"
                ]
            )
        )

        safe_detected = html.escape(
            str(
                result[
                    "detected"
                ]
            )
        )

        safe_advice = html.escape(
            str(
                result[
                    "advice"
                ]
            )
        )


        result_html = (
            f'<div class="{css_class}">'

            f'<div class="risk-title">'
            f'구매 유도 위험도 {risk_text}'
            f'</div>'

            f'<div style="margin-top:16px;">'
            f'<b>위험 점수</b><br>'
            f'{result["risk_score"]} / 100'
            f'</div>'

            f'<div style="margin-top:15px;">'
            f'<b>체키 한줄 요약</b><br>'
            f'{safe_summary}'
            f'</div>'

            f'<div style="margin-top:15px;">'
            f'<b>발견된 요소</b><br>'
            f'{safe_detected}'
            f'</div>'

            f'<div style="margin-top:15px;">'
            f'<b>체키의 제안</b><br>'
            f'{safe_advice}'
            f'</div>'

            f'</div>'
        )


        st.markdown(
            result_html,
            unsafe_allow_html=True
        )


        if (
            result[
                "price"
            ]
            > 0
        ):

            price_html = (
                '<div class="price-box">'

                'AI가 화면에서 확인한 가격'

                '<br>'

                '<span style="'
                'font-size:22px;'
                'font-weight:850;'
                'color:#1689F8;'
                'letter-spacing:-0.05em;'
                '">'

                f'{result["price"]:,}원'

                '</span>'

                '</div>'
            )


            st.markdown(
                price_html,
                unsafe_allow_html=True
            )


        else:

            st.info(
                "화면에서 정확한 상품 가격을 "
                "확인하지 못했어요."
            )


        show_mascot(
            MASCOT_WAIT,
            size=150,
            extra_class="wait-mascot"
        )


        st.markdown(
            """
            <div class="section-center">

                <div class="section-title">
                    30분 생각하기
                </div>

                <div class="section-desc">
                    바로 결제하기 전에 잠시 멈춰<br>
                    정말 필요한 소비인지 다시 생각해보세요.
                </div>

            </div>
            """,
            unsafe_allow_html=True
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
# 16. 소비분석
# =========================================================

elif page == "소비분석":

    analysis_hero = (
        '<div class="hero">'

        '<div class="hero-title">'
        '나의 '
        '<span class="hero-blue">'
        '소비 분석'
        '</span>'
        '</div>'

        '<div class="hero-desc">'
        '체키에 저장된 실제 소비 기록을 기준으로 확인합니다.'
        '</div>'

        '</div>'
    )


    st.markdown(
        analysis_hero,
        unsafe_allow_html=True
    )


    show_mascot(
        MASCOT_CHART,
        size=150,
        extra_class="chart-mascot"
    )


    expenses = (
        get_expenses()
    )

    records = (
        get_records()
    )


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


            item_name = html.escape(
                str(
                    expense.get(
                        "item_name",
                        "상품"
                    )
                )
            )


            expense_category = html.escape(
                str(
                    expense.get(
                        "category",
                        "기타"
                    )
                )
            )


            expense_html = (
                '<div class="checki-card">'

                f'<div class="card-title">'
                f'{item_name}'
                f'</div>'

                f'<div class="card-desc">'
                f'{expense_category}'
                f'</div>'

                f'<div style="'
                f'margin-top:12px;'
                f'font-size:19px;'
                f'font-weight:850;'
                f'letter-spacing:-0.05em;'
                f'color:#18344B;'
                f'">'

                f'{amount:,}원'

                f'</div>'

                '</div>'
            )


            st.markdown(
                expense_html,
                unsafe_allow_html=True
            )


# =========================================================
# 17. MY
# =========================================================

elif page == "MY":

    my_hero = (
        '<div class="hero">'

        '<div class="hero-title">'
        '나의 '
        '<span class="hero-blue">'
        '체키 기록'
        '</span>'
        '</div>'

        '<div class="hero-desc">'
        '구매하기 전 한 번 멈춰본 기록을 확인해보세요.'
        '</div>'

        '</div>'
    )


    st.markdown(
        my_hero,
        unsafe_allow_html=True
    )


    records = (
        get_records()
    )


    if not records:

        st.info(
            "아직 체키 기록이 없어요."
        )


    else:

        for index, record in enumerate(
            records[:20]
        ):

            product_raw = (
                record.get(
                    "product_name",
                    "상품"
                )
            )

            product = html.escape(
                str(product_raw)
            )


            category_raw = (
                record.get(
                    "category",
                    "기타"
                )
            )

            category = html.escape(
                str(category_raw)
            )


            price = int(
                record.get(
                    "product_price",
                    0
                )
                or 0
            )


            decision = (
                record.get(
                    "decision",
                    "HOLD"
                )
            )


            risk = html.escape(
                str(
                    record.get(
                        "risk_level",
                        "MEDIUM"
                    )
                )
            )


            record_id = (
                record.get(
                    "id"
                )
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


            record_html = (
                '<div class="checki-card">'

                f'<div class="card-title">'
                f'{product}'
                f'</div>'

                f'<div class="card-desc">'
                f'{category} · 위험도 {risk}'
                f'</div>'

                f'<div style="'
                f'margin-top:12px;'
                f'font-weight:800;'
                f'letter-spacing:-0.04em;'
                f'color:#19364D;'
                f'">'

                f'{price_text}'

                f'</div>'

                '</div>'
            )


            st.markdown(
                record_html,
                unsafe_allow_html=True
            )


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


                if not hold_finished:

                    show_mascot(
                        MASCOT_WAIT,
                        size=115,
                        extra_class=
                            "my-wait-mascot"
                    )


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
                        seconds
                        // 60
                    )


                    seconds_left = (
                        seconds
                        % 60
                    )


                    st.info(
                        f"아직 생각하는 중이에요. "
                        f"{minutes}분 "
                        f"{seconds_left}초 남았습니다."
                    )


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
                            ] = (
                                record_id
                            )


                if (
                    st.session_state.get(
                        "buy_record"
                    )
                    == record_id
                ):

                    actual_amount = (
                        st.number_input(
                            "실제로 결제한 금액",

                            min_value=
                                0,

                            step=
                                1000,

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
                                category_raw,
                                product_raw,
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
                            and record_ok
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


            elif (
                decision
                == "BUY"
            ):

                st.info(
                    "구매 완료"
                )
