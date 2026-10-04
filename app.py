import streamlit as st
from google import genai
from PIL import Image
from supabase import create_client
from datetime import datetime, timedelta, timezone
import requests
from bs4 import BeautifulSoup
import re
import time
import os


# =========================================================
# 1. 기본 설정
# =========================================================

st.set_page_config(
    page_title="체키 | CHECKI",
    page_icon="✓",
    layout="centered",
    initial_sidebar_state="collapsed"
)

KST = timezone(timedelta(hours=9))

MASCOT_FILE = "file_00000000447c81fa8ff9b20ee6b2c9ef.png"

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]


def now_kst():
    return datetime.now(KST)


def iso_now():
    return now_kst().isoformat()


# =========================================================
# 2. 디자인
# =========================================================

st.markdown(
    """
<style>

html, body, .stApp {
    overflow-x: hidden !important;
}

.block-container {
    max-width: 920px;
    padding-top: 1rem !important;
    padding-bottom: 5rem !important;
}

[data-testid="stHeader"] {
    background: transparent !important;
    height: 0 !important;
}

[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {
    display: none !important;
}

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

.stApp {
    background:
        radial-gradient(
            circle at 15% 5%,
            rgba(41,151,255,.08),
            transparent 30%
        ),
        radial-gradient(
            circle at 90% 15%,
            rgba(142,102,255,.06),
            transparent 30%
        ),
        #f9fbff;
}

/* 로고 */

.checki-logo {
    font-size: 31px;
    font-weight: 900;
    color: #1689f8;
    letter-spacing: -2px;
}

.checki-sub {
    font-size: 10px;
    letter-spacing: 2px;
    color: #8993a4;
    margin-top: -4px;
    margin-bottom: 12px;
}

/* 로그인 */

.login-wrap {
    max-width: 520px;
    margin: 35px auto 15px auto;
}

.login-title {
    text-align: center;
    font-size: 31px;
    font-weight: 900;
    color: #0d315b;
    letter-spacing: -1.5px;
}

.login-desc {
    text-align: center;
    color: #738295;
    line-height: 1.7;
    margin: 10px 0 25px 0;
}

/* Hero */

.hero-card {
    padding: 32px;
    border-radius: 26px;

    background:
        linear-gradient(
            135deg,
            rgba(231,245,255,.98),
            rgba(255,255,255,.98),
            rgba(249,239,255,.90)
        );

    border: 1px solid #dce7f2;
    margin: 20px 0 30px 0;

    box-shadow:
        0 12px 35px rgba(41,100,170,.05);
}

.hero-badge {
    display: inline-block;
    background: #dff1ff;
    color: #1689f8;
    font-weight: 800;
    padding: 8px 13px;
    border-radius: 20px;
    font-size: 14px;
    margin-bottom: 16px;
}

.hero-title {
    font-size: 36px;
    line-height: 1.3;
    font-weight: 900;
    color: #0d315b;
    letter-spacing: -2px;
}

.hero-text {
    color: #6f7f91;
    line-height: 1.8;
    margin-top: 13px;
}

/* 카드 */

.info-card {
    padding: 20px;
    background: white;
    border: 1px solid #e1e8f0;
    border-radius: 20px;
    margin-bottom: 12px;
}

.blue-card {
    padding: 20px;

    background:
        linear-gradient(
            135deg,
            #edf8ff,
            #f9fcff
        );

    border: 1px solid #d7e9f8;
    border-radius: 20px;
    margin: 12px 0;
}

.result-card {
    padding: 22px;
    background: white;
    border: 1px solid #dfe7ef;
    border-radius: 20px;
    margin: 12px 0;
}

/* Metric */

[data-testid="stMetric"] {
    background: white;
    border: 1px solid #e1e8f0;
    padding: 18px 10px;
    border-radius: 18px;
    text-align: center;
}

[data-testid="stMetricValue"] {
    color: #1689f8;
}

/* 버튼 */

.stButton > button {
    border-radius: 14px !important;
    min-height: 48px;
    font-weight: 800 !important;
}

/* 체키 파란색 PRIMARY */

.stButton > button[kind="primary"] {
    background: #1689f8 !important;
    border: 1px solid #1689f8 !important;
    color: white !important;
    box-shadow: 0 7px 18px rgba(22,137,248,.18);
}

.stButton > button[kind="primary"]:hover {
    background: #087be8 !important;
    border-color: #087be8 !important;
}

/* 일반 버튼 */

.stButton > button:not([kind="primary"]) {
    border-color: #b8d9fa;
    color: #167bd7;
}

/* Progress */

.stProgress > div > div > div > div {
    background-color: #1689f8;
}

/* 모바일 */

@media (max-width: 600px) {

    .block-container {
        padding-left: 16px !important;
        padding-right: 16px !important;
        padding-top: .6rem !important;
    }

    .hero-card {
        padding: 23px;
    }

    .hero-title {
        font-size: 29px;
    }

    .hero-text {
        font-size: 14px;
    }

    .checki-logo {
        font-size: 28px;
    }

    .login-title {
        font-size: 27px;
    }

    div[data-testid="stRadio"]
    div[role="radiogroup"] {
        display: flex;
        flex-wrap: wrap;
    }
}

</style>
""",
    unsafe_allow_html=True
)


# =========================================================
# 3. Supabase Auth 클라이언트
# =========================================================

def new_supabase_client():
    return create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )


# 세션별 Supabase 클라이언트
if "supabase" not in st.session_state:
    st.session_state.supabase = new_supabase_client()


supabase = st.session_state.supabase


# =========================================================
# 4. Gemini
# =========================================================

@st.cache_resource
def get_gemini():
    return genai.Client(
        api_key=GEMINI_API_KEY
    )


gemini = get_gemini()


# =========================================================
# 5. Auth 보조 함수
# =========================================================

def get_current_user():

    try:
        response = supabase.auth.get_user()

        if response and response.user:
            return response.user

    except Exception:
        pass

    return None


def login(email, password):

    result = (
        supabase.auth
        .sign_in_with_password(
            {
                "email": email,
                "password": password
            }
        )
    )

    if result.session:

        st.session_state[
            "access_token"
        ] = result.session.access_token

        st.session_state[
            "refresh_token"
        ] = result.session.refresh_token

    return result


def signup(email, password):

    result = (
        supabase.auth.sign_up(
            {
                "email": email,
                "password": password
            }
        )
    )

    if result.session:

        st.session_state[
            "access_token"
        ] = result.session.access_token

        st.session_state[
            "refresh_token"
        ] = result.session.refresh_token

    return result


def logout():

    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    for key in [
        "access_token",
        "refresh_token",
        "latest_analysis",
        "latest_record",
        "purchase_after_hold"
    ]:

        st.session_state.pop(
            key,
            None
        )

    # 완전히 새 클라이언트 생성
    st.session_state.supabase = (
        new_supabase_client()
    )


# =========================================================
# 6. 기존 세션 복원
# =========================================================

if (
    st.session_state.get("access_token")
    and
    st.session_state.get("refresh_token")
):

    try:

        supabase.auth.set_session(
            st.session_state[
                "access_token"
            ],
            st.session_state[
                "refresh_token"
            ]
        )

    except Exception:

        st.session_state.pop(
            "access_token",
            None
        )

        st.session_state.pop(
            "refresh_token",
            None
        )


current_user = get_current_user()


# =========================================================
# 7. 공통 로고
# =========================================================

st.markdown(
    """
<div class="checki-logo">
체키
</div>

<div class="checki-sub">
CHECK BEFORE YOU BUY
</div>
""",
    unsafe_allow_html=True
)


# =========================================================
# 8. 로그인 안 된 상태
# =========================================================

if current_user is None:

    # 마스코트
    if os.path.exists(MASCOT_FILE):

        a, b, c = st.columns(
            [1, 1.1, 1]
        )

        with b:

            st.image(
                MASCOT_FILE,
                use_container_width=True
            )


    st.markdown(
        """
<div class="login-wrap">

<div class="login-title">
체키에 오신 것을 환영해요
</div>

<div class="login-desc">
로그인하면 구매체크와 소비 기록을 저장하고<br>
다음에 다시 접속해도 그대로 이어서 확인할 수 있어요.
</div>

</div>
""",
        unsafe_allow_html=True
    )


    login_tab, signup_tab = st.tabs(
        [
            "로그인",
            "회원가입"
        ]
    )


    # =====================================================
    # 로그인
    # =====================================================

    with login_tab:

        login_email = st.text_input(
            "이메일",
            placeholder="example@email.com",
            key="login_email"
        )

        login_password = st.text_input(
            "비밀번호",
            type="password",
            key="login_password"
        )

        if st.button(
            "체키 로그인",
            type="primary",
            use_container_width=True,
            key="login_button"
        ):

            if not login_email.strip():

                st.warning(
                    "이메일을 입력해주세요."
                )

            elif not login_password:

                st.warning(
                    "비밀번호를 입력해주세요."
                )

            else:

                try:

                    result = login(
                        login_email.strip(),
                        login_password
                    )

                    if result.user:

                        st.success(
                            "로그인했어요!"
                        )

                        st.rerun()

                except Exception as e:

                    error = str(e).lower()

                    if (
                        "invalid login"
                        in error
                        or
                        "invalid credentials"
                        in error
                    ):

                        st.error(
                            "이메일 또는 비밀번호가 맞지 않아요."
                        )

                    else:

                        st.error(
                            "로그인하지 못했어요."
                        )

                        st.code(
                            str(e)
                        )


    # =====================================================
    # 회원가입
    # =====================================================

    with signup_tab:

        signup_email = st.text_input(
            "이메일",
            placeholder="example@email.com",
            key="signup_email"
        )

        signup_password = st.text_input(
            "비밀번호",
            type="password",
            key="signup_password"
        )

        signup_password2 = st.text_input(
            "비밀번호 확인",
            type="password",
            key="signup_password2"
        )

        st.caption(
            "비밀번호는 6자 이상으로 만들어주세요."
        )

        if st.button(
            "체키 시작하기",
            type="primary",
            use_container_width=True,
            key="signup_button"
        ):

            if not signup_email.strip():

                st.warning(
                    "이메일을 입력해주세요."
                )

            elif len(
                signup_password
            ) < 6:

                st.warning(
                    "비밀번호는 6자 이상이어야 해요."
                )

            elif (
                signup_password
                != signup_password2
            ):

                st.warning(
                    "비밀번호 확인이 일치하지 않아요."
                )

            else:

                try:

                    result = signup(
                        signup_email.strip(),
                        signup_password
                    )

                    if result.user:

                        if result.session:

                            st.success(
                                "회원가입이 완료됐어요!"
                            )

                            st.rerun()

                        else:

                            st.success(
                                "회원가입했어요. "
                                "이메일 인증 후 로그인해주세요."
                            )

                except Exception as e:

                    st.error(
                        "회원가입 중 문제가 발생했어요."
                    )

                    st.code(
                        str(e)
                    )


    st.stop()


# =========================================================
# 9. 로그인 사용자 ID
# =========================================================

user_id = str(
    current_user.id
)

user_email = (
    current_user.email
    or ""
)


# =========================================================
# 10. DB 함수
# =========================================================

def get_expenses():

    try:

        result = (
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

        return (
            result.data
            or []
        )

    except Exception as e:

        st.error(
            "소비 기록을 불러오지 못했어요."
        )

        return []


def get_records():

    try:

        result = (
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

        return (
            result.data
            or []
        )

    except Exception:

        return []


def add_expense(
    category,
    item_name,
    amount
):

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

    return (
        supabase
        .table(
            "checki_expenses"
        )
        .insert(data)
        .execute()
    )


def save_analysis_record(
    product_name,
    category,
    risk_level,
    risk_score,
    summary,
    detected,
    ai_result,
    action_text
):

    data = {

        "user_id":
            user_id,

        "product_name":
            product_name,

        "category":
            category,

        "product_price":
            0,

        "risk_level":
            risk_level,

        "risk_score":
            int(risk_score),

        "one_line_summary":
            summary,

        "detected_elements":
            detected,

        "ai_result":
            ai_result,

        "action_text":
            action_text,

        "decision":
            "checking",

        "saved_amount":
            0,

        "created_at":
            iso_now()
    }


    result = (
        supabase
        .table(
            "checki_records"
        )
        .insert(data)
        .execute()
    )


    if result.data:

        return (
            result.data[0]
        )

    return None


def update_record(
    record_id,
    values
):

    return (
        supabase
        .table(
            "checki_records"
        )
        .update(values)
        .eq(
            "id",
            record_id
        )
        .eq(
            "user_id",
            user_id
        )
        .execute()
    )


# =========================================================
# 11. 통계
# =========================================================

def calculate_stats():

    expenses = get_expenses()
    records = get_records()

    total_spending = sum(
        int(
            x.get("amount")
            or 0
        )
        for x in expenses
    )

    abandoned = [
        x
        for x in records
        if x.get("decision")
        == "abandoned"
    ]

    saved_amount = sum(
        int(
            x.get("saved_amount")
            or 0
        )
        for x in abandoned
    )

    return {

        "expenses":
            expenses,

        "records":
            records,

        "total_spending":
            total_spending,

        "purchase_checks":
            len(records),

        "abandoned_count":
            len(abandoned),

        "saved_amount":
            saved_amount
    }


# =========================================================
# 12. URL 읽기
# =========================================================

def read_url(url):

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
            "(iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 "
            "Version/17.0 "
            "Mobile Safari/604.1"
    }


    response = requests.get(
        url,
        headers=headers,
        timeout=12
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
            "noscript",
            "svg"
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


    return (
        title,
        text[:18000]
    )


# =========================================================
# 13. Gemini 호출
# =========================================================

def call_gemini(contents):

    # 사용 가능한 모델을 순차 시도
    models = [
        "gemini-3.8-flash",
        "gemini-3-flash-preview",
        "gemini-2.5-flash"
    ]

    last_error = None


    for model_name in models:

        for attempt in range(3):

            try:

                response = (
                    gemini.models
                    .generate_content(
                        model=model_name,
                        contents=contents
                    )
                )

                if response.text:

                    return response


            except Exception as e:

                last_error = e

                error = (
                    str(e)
                    .lower()
                )


                temporary = (
                    "503" in error
                    or
                    "high demand"
                    in error
                    or
                    "unavailable"
                    in error
                    or
                    "429" in error
                    or
                    "resource_exhausted"
                    in error
                )


                if temporary:

                    time.sleep(
                        2
                        * (
                            attempt
                            + 1
                        )
                    )

                    continue


                # 모델 없음/404 등이면
                # 다음 모델 시도
                break


    if last_error:

        raise last_error


    raise Exception(
        "AI 분석 결과를 받지 못했습니다."
    )


# =========================================================
# 14. Prompt
# =========================================================

def analysis_prompt(
    product_name,
    category,
    source_type,
    webpage_text=""
):

    return f"""
너는 소비자의 충동구매와 다크패턴 피해를 예방하는
AI 소비 방어 도우미 '체키(CHECKI)'다.

사용자는 현재 상품 구매를 고민하고 있다.

상품명: {product_name}
카테고리: {category}
분석 방식: {source_type}

웹페이지에서 추출한 정보가 있다면 아래와 같다.

{webpage_text}


다음 요소를 분석한다.

1. 시간 압박
2. 희소성 강조
3. 사회적 증거를 이용한 압박
4. 과도한 할인 강조
5. 추가비용 은폐
6. 구독 또는 자동결제 유도
7. 선택 방해
8. 취소 방해
9. 감정적 압박
10. 반복적인 구매 유도


중요:

화면이나 페이지에서 실제로 확인되지 않는 내용은
절대 만들어내지 않는다.

단순 할인 자체를 다크패턴으로 판단하지 않는다.

가격이 화면에 보이면 분석에 참고할 수 있지만
가격이 없어도 정상적으로 분석한다.

소비자가 스스로 합리적으로 결정할 수 있도록
중립적으로 설명한다.


반드시 아래 형식으로 답한다.

RISK_LEVEL: 낮음/주의/높음

RISK_SCORE: 0~100 사이 정수

SUMMARY: 한 문장 요약

DETECTED: 발견된 요소. 여러 개면 | 로 구분

ACTION: 결제 전에 다시 확인할 행동

DETAIL:
판단 근거를 쉽게 설명한다.
"""


# =========================================================
# 15. AI 응답 파싱
# =========================================================

def extract_value(
    text,
    key,
    default=""
):

    match = re.search(
        rf"{key}:\s*(.*)",
        text,
        re.IGNORECASE
    )

    if match:

        return (
            match.group(1)
            .strip()
        )

    return default


def parse_ai_result(text):

    risk_level = extract_value(
        text,
        "RISK_LEVEL",
        "주의"
    )

    score_text = extract_value(
        text,
        "RISK_SCORE",
        "50"
    )

    score_match = re.search(
        r"\d+",
        score_text
    )

    risk_score = (
        int(
            score_match.group()
        )
        if score_match
        else 50
    )

    risk_score = max(
        0,
        min(
            100,
            risk_score
        )
    )

    summary = extract_value(
        text,
        "SUMMARY",
        "구매 전 한 번 더 확인해보세요."
    )

    detected = extract_value(
        text,
        "DETECTED",
        "뚜렷한 구매 유도 요소 없음"
    )

    action = extract_value(
        text,
        "ACTION",
        "지금 필요한 구매인지 다시 확인해보세요."
    )

    if "DETAIL:" in text:

        detail = (
            text
            .split(
                "DETAIL:",
                1
            )[1]
            .strip()
        )

    else:

        detail = text


    return (
        risk_level,
        risk_score,
        summary,
        detected,
        action,
        detail
    )


# =========================================================
# 16. 메뉴
# =========================================================

menu = st.radio(
    "메뉴",
    [
        "🏠 홈",
        "✓ 구매체크",
        "📊 소비분석",
        "👤 MY"
    ],
    horizontal=True,
    label_visibility="collapsed"
)


# =========================================================
# 17. 홈
# =========================================================

if menu == "🏠 홈":

    stats = calculate_stats()


    left, right = st.columns(
        [1.6, 1]
    )


    with left:

        st.markdown(
            """
<div class="hero-card">

<div class="hero-badge">
AI 소비 방어 도우미
</div>

<div class="hero-title">
구매 전,<br>
한 번 더 체키해 보세요.
</div>

<div class="hero-text">
쇼핑 화면 속 구매 유도 요소를 확인하고,
나의 실제 소비 기록과 함께 살펴보며
지금 필요한 소비인지 한 번 더 생각할 수 있도록 도와드려요.
</div>

</div>
""",
            unsafe_allow_html=True
        )


    with right:

        if os.path.exists(
            MASCOT_FILE
        ):

            st.image(
                MASCOT_FILE,
                use_container_width=True
            )


    st.subheader(
        "나의 체키"
    )


    c1, c2, c3 = st.columns(3)


    with c1:

        st.metric(
            "구매 체크",
            stats[
                "purchase_checks"
            ]
        )


    with c2:

        st.metric(
            "구매 포기",
            stats[
                "abandoned_count"
            ]
        )


    with c3:

        st.metric(
            "누적 소비",
            f'{stats["total_spending"]:,}원'
        )


    st.markdown(
        "### 체키는 이렇게 도와드려요"
    )


    st.markdown(
        """
<div class="blue-card">
<b>① 구매 화면 체크</b><br><br>
구매를 고민하고 있는 화면이나 상품 링크를 보여주세요.
AI가 구매를 서두르게 하는 요소를 살펴봐요.
</div>

<div class="blue-card">
<b>② 잠깐 보류하기</b><br><br>
바로 결제하지 않고 30분 동안 구매 결정을 보류할 수 있어요.
</div>

<div class="blue-card">
<b>③ 나의 소비 확인</b><br><br>
실제 소비 기록을 저장하고 다시 접속해도 이어서 확인할 수 있어요.
</div>
""",
        unsafe_allow_html=True
    )


# =========================================================
# 18. 구매체크
# =========================================================

elif menu == "✓ 구매체크":

    st.header(
        "구매 전, 한 번 더 체키해 보세요"
    )


    st.markdown(
        """
<div class="blue-card">
<b>📸 쇼핑 화면 또는 🔗 상품 링크를 보여주세요.</b>
<br><br>
상품 가격을 따로 입력하지 않아도 돼요.
체키가 구매 유도 요소와 다크패턴 가능성을 살펴봅니다.
</div>
""",
        unsafe_allow_html=True
    )


    analysis_type = st.radio(
        "분석 방법",
        [
            "📸 이미지 분석",
            "🔗 링크 분석"
        ],
        horizontal=True
    )


    uploaded_file = None
    shopping_url = ""


    if (
        analysis_type
        == "📸 이미지 분석"
    ):

        uploaded_file = (
            st.file_uploader(
                "구매를 고민 중인 쇼핑 화면",
                type=[
                    "png",
                    "jpg",
                    "jpeg"
                ]
            )
        )


        if uploaded_file:

            image = Image.open(
                uploaded_file
            )

            st.image(
                image,
                use_container_width=True
            )


    else:

        shopping_url = st.text_input(
            "상품 링크",
            placeholder="https://..."
        )

        st.caption(
            "사이트가 외부 접근을 차단하면 "
            "스크린샷 분석을 이용해주세요."
        )


    product_name = st.text_input(
        "상품명",
        placeholder="예: 에어팟"
    )


    category = st.selectbox(
        "카테고리",
        [
            "의류",
            "패션잡화",
            "화장품/뷰티",
            "식비",
            "전자기기",
            "생활용품",
            "취미/여가",
            "구독",
            "교통",
            "기타"
        ]
    )


    can_analyze = (
        uploaded_file is not None
        if (
            analysis_type
            == "📸 이미지 분석"
        )
        else bool(
            shopping_url.strip()
        )
    )


    if st.button(
        "🔎 체키로 분석하기",
        type="primary",
        use_container_width=True,
        disabled=not can_analyze
    ):

        if not product_name.strip():

            st.warning(
                "상품명을 입력해주세요."
            )

        else:

            try:

                with st.spinner(
                    "🤖 체키가 구매 유도 요소를 분석하고 있어요..."
                ):


                    if (
                        analysis_type
                        == "🔗 링크 분석"
                    ):

                        title, webpage_text = (
                            read_url(
                                shopping_url.strip()
                            )
                        )


                        prompt = analysis_prompt(
                            product_name,
                            category,
                            "쇼핑 링크",
                            webpage_text
                        )


                        response = call_gemini(
                            prompt
                        )


                    else:

                        image = Image.open(
                            uploaded_file
                        )


                        prompt = analysis_prompt(
                            product_name,
                            category,
                            "쇼핑 화면 이미지"
                        )


                        response = call_gemini(
                            [
                                prompt,
                                image
                            ]
                        )


                    ai_text = (
                        response.text
                        or ""
                    )


                    (
                        risk_level,
                        risk_score,
                        summary,
                        detected,
                        action,
                        detail
                    ) = parse_ai_result(
                        ai_text
                    )


                    record = save_analysis_record(
                        product_name.strip(),
                        category,
                        risk_level,
                        risk_score,
                        summary,
                        detected,
                        detail,
                        action
                    )


                    st.session_state[
                        "latest_record"
                    ] = record


                    st.session_state[
                        "latest_analysis"
                    ] = {

                        "risk_level":
                            risk_level,

                        "risk_score":
                            risk_score,

                        "summary":
                            summary,

                        "detected":
                            detected,

                        "action":
                            action,

                        "detail":
                            detail,

                        "product_name":
                            product_name.strip(),

                        "category":
                            category
                    }


            except requests.exceptions.RequestException:

                st.error(
                    "이 사이트의 내용을 직접 불러오지 못했어요. "
                    "상품 화면을 캡처해서 분석해주세요."
                )


            except Exception as e:

                st.error(
                    "분석 중 문제가 발생했어요."
                )

                st.code(
                    str(e)
                )


    # =====================================================
    # 분석 결과
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

        record = (
            st.session_state.get(
                "latest_record"
            )
        )


        st.divider()

        st.subheader(
            "체키 분석 결과"
        )


        st.markdown(
            f"""
<div class="result-card">

<b>위험도</b><br>
{result["risk_level"]}

<br><br>

<b>체키 위험 점수</b><br>
{result["risk_score"]} / 100

<br><br>

<b>한 줄 분석</b><br>
{result["summary"]}

</div>
""",
            unsafe_allow_html=True
        )


        st.progress(
            result[
                "risk_score"
            ] / 100
        )


        st.markdown(
            "#### ⚠️ 발견된 요소"
        )


        for element in (
            result[
                "detected"
            ]
            .split("|")
        ):

            if element.strip():

                st.write(
                    "• "
                    + element.strip()
                )


        st.markdown(
            "#### 🧠 체키의 분석"
        )

        st.write(
            result[
                "detail"
            ]
        )


        st.markdown(
            "#### ✅ 결제 전 체크"
        )

        st.info(
            result[
                "action"
            ]
        )


        st.markdown(
            "### 그래서, 이 상품 어떻게 할까요?"
        )


        if record:

            col1, col2 = st.columns(2)


            with col1:

                if st.button(
                    "⏱️ 30분 보류",
                    use_container_width=True
                ):

                    start = now_kst()

                    until = (
                        start
                        + timedelta(
                            minutes=30
                        )
                    )


                    update_record(
                        record["id"],
                        {

                            "decision":
                                "hold",

                            "hold_started_at":
                                start.isoformat(),

                            "hold_until":
                                until.isoformat()
                        }
                    )


                    st.success(
                        "30분 동안 구매를 보류했어요. "
                        "MY에서 다시 확인할 수 있어요."
                    )


            with col2:

                if st.button(
                    "🛡️ 구매하지 않기",
                    type="primary",
                    use_container_width=True
                ):

                    update_record(
                        record["id"],
                        {

                            "decision":
                                "abandoned",

                            "saved_amount":
                                0,

                            "decided_at":
                                iso_now()
                        }
                    )


                    st.session_state.pop(
                        "latest_analysis",
                        None
                    )

                    st.session_state.pop(
                        "latest_record",
                        None
                    )


                    st.rerun()


# =========================================================
# 19. 소비분석
# =========================================================

elif menu == "📊 소비분석":

    stats = calculate_stats()


    st.header(
        "나의 소비분석"
    )


    c1, c2 = st.columns(2)


    with c1:

        st.metric(
            "누적 소비",
            f'{stats["total_spending"]:,}원'
        )


    with c2:

        st.metric(
            "구매 포기",
            f'{stats["abandoned_count"]}회'
        )


    st.divider()


    st.markdown(
        "### ＋ 소비내역 추가하기"
    )


    expense_category = st.selectbox(
        "소비 카테고리",
        [
            "식비",
            "의류",
            "패션잡화",
            "화장품/뷰티",
            "전자기기",
            "생활용품",
            "취미/여가",
            "교통",
            "구독",
            "기타"
        ],
        key="expense_category"
    )


    expense_name = st.text_input(
        "구매한 항목",
        placeholder="예: 점심, 운동화",
        key="expense_name"
    )


    expense_amount = st.number_input(
        "사용한 금액",
        min_value=0,
        step=1000,
        value=0,
        key="expense_amount"
    )


    if st.button(
        "소비내역 저장",
        type="primary",
        use_container_width=True
    ):

        if not expense_name.strip():

            st.warning(
                "구매한 항목을 입력해주세요."
            )

        elif expense_amount <= 0:

            st.warning(
                "사용한 금액을 입력해주세요."
            )

        else:

            try:

                add_expense(
                    expense_category,
                    expense_name.strip(),
                    expense_amount
                )

                st.rerun()

            except Exception as e:

                st.error(
                    "저장하지 못했어요."
                )

                st.code(
                    str(e)
                )


    expenses = get_expenses()


    st.divider()

    st.markdown(
        "### 나의 소비내역"
    )


    if not expenses:

        st.info(
            "아직 등록된 소비내역이 없어요."
        )


    else:

        category_totals = {}


        for expense in expenses:

            category_name = (
                expense.get(
                    "category"
                )
                or "기타"
            )

            amount = int(
                expense.get(
                    "amount"
                )
                or 0
            )


            category_totals[
                category_name
            ] = (
                category_totals.get(
                    category_name,
                    0
                )
                + amount
            )


        st.markdown(
            "#### 카테고리별 소비"
        )


        total = max(
            stats[
                "total_spending"
            ],
            1
        )


        for (
            category_name,
            amount
        ) in sorted(
            category_totals.items(),
            key=lambda x:
                x[1],
            reverse=True
        ):

            st.write(
                f"**{category_name}** · "
                f"{amount:,}원"
            )

            st.progress(
                min(
                    amount / total,
                    1.0
                )
            )


        st.divider()


        st.markdown(
            "#### 최근 소비"
        )


        for expense in (
            expenses[:10]
        ):

            name = (
                expense.get(
                    "item_name"
                )
                or "소비"
            )

            category_name = (
                expense.get(
                    "category"
                )
                or "기타"
            )

            amount = int(
                expense.get(
                    "amount"
                )
                or 0
            )


            st.markdown(
                f"""
<div class="info-card">

<b>{name}</b>

<br>

<span style="color:#7a8795">
{category_name}
</span>

<br><br>

<b>{amount:,}원</b>

</div>
""",
                unsafe_allow_html=True
            )


# =========================================================
# 20. MY
# =========================================================

elif menu == "👤 MY":

    stats = calculate_stats()
    records = stats["records"]


    st.header(
        "MY"
    )


    # =====================================================
    # 계정
    # =====================================================

    st.markdown(
        "### 내 계정"
    )


    st.markdown(
        f"""
<div class="blue-card">

<b>로그인 계정</b>

<br><br>

{user_email}

<br><br>

이 계정으로 다시 로그인하면
현재 체키 기록을 다시 불러올 수 있어요.

</div>
""",
        unsafe_allow_html=True
    )


    if st.button(
        "로그아웃",
        use_container_width=True
    ):

        logout()

        st.rerun()


    st.divider()


    # =====================================================
    # 통계
    # =====================================================

    st.markdown(
        "### 나의 체키 기록"
    )


    c1, c2, c3 = st.columns(3)


    with c1:

        st.metric(
            "구매 체크",
            stats[
                "purchase_checks"
            ]
        )


    with c2:

        st.metric(
            "구매 포기",
            stats[
                "abandoned_count"
            ]
        )


    with c3:

        st.metric(
            "누적 소비",
            f'{stats["total_spending"]:,}원'
        )


    st.divider()


    # =====================================================
    # 보류 중
    # =====================================================

    st.markdown(
        "### ⏱️ 보류 중인 구매"
    )


    active_holds = []


    for record in records:

        if (
            record.get(
                "decision"
            )
            != "hold"
        ):

            continue


        hold_text = (
            record.get(
                "hold_until"
            )
        )


        if not hold_text:

            continue


        try:

            hold_until = (
                datetime
                .fromisoformat(
                    hold_text
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


            if (
                hold_until
                > now_kst()
            ):

                active_holds.append(
                    (
                        record,
                        hold_until
                    )
                )


        except Exception:

            pass


    if not active_holds:

        st.info(
            "현재 보류 중인 구매가 없어요."
        )


    else:

        for (
            record,
            hold_until
        ) in active_holds:

            remaining = (
                hold_until
                - now_kst()
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


            product = (
                record.get(
                    "product_name"
                )
                or "상품"
            )


            category_name = (
                record.get(
                    "category"
                )
                or "기타"
            )


            st.markdown(
                f"""
<div class="result-card">

<b>{product}</b>

<br>

{category_name}

<br><br>

⏱️ 약 {minutes}분 남음

</div>
""",
                unsafe_allow_html=True
            )


            col1, col2 = (
                st.columns(2)
            )


            with col1:

                if st.button(
                    "구매하기",
                    key=
                        f'buy_{record["id"]}',
                    use_container_width=True
                ):

                    update_record(
                        record["id"],
                        {

                            "decision":
                                "purchased",

                            "decided_at":
                                iso_now()
                        }
                    )


                    st.session_state[
                        "purchase_after_hold"
                    ] = {

                        "record_id":
                            record["id"],

                        "product":
                            product,

                        "category":
                            category_name
                    }


                    st.rerun()


            with col2:

                if st.button(
                    "구매 포기",
                    key=
                        f'abandon_{record["id"]}',
                    type="primary",
                    use_container_width=True
                ):

                    update_record(
                        record["id"],
                        {

                            "decision":
                                "abandoned",

                            "saved_amount":
                                0,

                            "decided_at":
                                iso_now()
                        }
                    )


                    st.rerun()


    # =====================================================
    # 구매 결정 후 금액 입력
    # =====================================================

    if (
        "purchase_after_hold"
        in st.session_state
    ):

        purchase_data = (
            st.session_state[
                "purchase_after_hold"
            ]
        )


        st.markdown(
            "### 구매 기록 남기기"
        )


        purchase_price = (
            st.number_input(
                "실제 결제 금액",
                min_value=0,
                step=1000,
                value=0
            )
        )


        if st.button(
            "구매내역 저장",
            type="primary",
            use_container_width=True
        ):

            if purchase_price <= 0:

                st.warning(
                    "결제 금액을 입력해주세요."
                )


            else:

                add_expense(
                    purchase_data[
                        "category"
                    ],
                    purchase_data[
                        "product"
                    ],
                    purchase_price
                )


                update_record(
                    purchase_data[
                        "record_id"
                    ],
                    {

                        "product_price":
                            int(
                                purchase_price
                            )
                    }
                )


                st.session_state.pop(
                    "purchase_after_hold",
                    None
                )


                st.rerun()


    st.divider()


    # =====================================================
    # 최근 기록
    # =====================================================

    st.markdown(
        "### 최근 구매체크"
    )


    if not records:

        st.info(
            "아직 구매체크 기록이 없어요."
        )


    else:

        for record in (
            records[:10]
        ):

            product = (
                record.get(
                    "product_name"
                )
                or "상품"
            )

            category_name = (
                record.get(
                    "category"
                )
                or "기타"
            )

            risk = (
                record.get(
                    "risk_level"
                )
                or "-"
            )

            decision = (
                record.get(
                    "decision"
                )
                or "checking"
            )


            decision_text = {

                "checking":
                    "검토 중",

                "hold":
                    "30분 보류",

                "abandoned":
                    "구매 포기",

                "purchased":
                    "구매"

            }.get(
                decision,
                decision
            )


            st.markdown(
                f"""
<div class="info-card">

<b>{product}</b>

<br>

<span style="color:#7a8795">
{category_name}
</span>

<br><br>

위험도:
<b>{risk}</b>

<br>

결정:
<b>{decision_text}</b>

</div>
""",
                unsafe_allow_html=True
            )


# =========================================================
# 21. Footer
# =========================================================

st.markdown(
    """
<br><br>

<div style="
text-align:center;
color:#9aa6b2;
font-size:12px;
line-height:1.8;
">

CHECKI · AI 소비 방어 도우미

<br>

구매를 막는 서비스가 아니라,
결제 전 한 번 더 확인할 수 있도록 돕습니다.

</div>
""",
    unsafe_allow_html=True
)
