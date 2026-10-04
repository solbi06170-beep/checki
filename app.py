import streamlit as st
from google import genai
from PIL import Image
from supabase import create_client
from datetime import datetime, timedelta, timezone
import uuid
import requests
from bs4 import BeautifulSoup
import re


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
GEMINI_MODEL = "gemini-3.8-flash"


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

/* 가로 넘침 방지 */
html, body, .stApp {
    overflow-x: hidden !important;
}

/* 본문 */
.block-container {
    max-width: 920px;
    padding-top: 1.0rem !important;
    padding-bottom: 5rem !important;
}

/* Streamlit 상단 영역 최소화 */
[data-testid="stHeader"] {
    background: transparent !important;
    height: 0rem !important;
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

#MainMenu {
    visibility: hidden !important;
}

footer {
    visibility: hidden !important;
}

/* 전체 배경 */
.stApp {
    background:
        radial-gradient(
            circle at 15% 5%,
            rgba(41,151,255,0.07),
            transparent 30%
        ),
        radial-gradient(
            circle at 90% 15%,
            rgba(142,102,255,0.06),
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
    margin-bottom: 0;
}

.checki-sub {
    font-size: 10px;
    letter-spacing: 2px;
    color: #8993a4;
    margin-top: -4px;
    margin-bottom: 12px;
}

/* 히어로 */
.hero-card {
    padding: 32px;
    border-radius: 25px;

    background:
        linear-gradient(
            135deg,
            rgba(231,245,255,.96),
            rgba(255,255,255,.98),
            rgba(249,239,255,.90)
        );

    border: 1px solid #dce7f2;
    margin: 20px 0 30px 0;

    box-shadow:
        0 12px 35px
        rgba(41,100,170,0.05);
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

.risk-low {
    padding: 18px;
    background: #f1fbf5;
    border: 1px solid #d8f0e1;
    border-radius: 18px;
}

.risk-warning {
    padding: 18px;
    background: #fff9ed;
    border: 1px solid #f4e5be;
    border-radius: 18px;
}

.risk-high {
    padding: 18px;
    background: #fff2f2;
    border: 1px solid #f1d6d6;
    border-radius: 18px;
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
    min-height: 46px;
    font-weight: 700;
}

/* 입력 */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {
    border-radius: 12px;
}

/* 네비게이션 */
div[data-testid="stRadio"] div[role="radiogroup"] {
    gap: 8px;
}

/* 모바일 */
@media (max-width: 600px) {

    .block-container {
        padding-left: 16px !important;
        padding-right: 16px !important;
        padding-top: 0.6rem !important;
    }

    .hero-card {
        padding: 23px;
        border-radius: 22px;
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

    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap;
    }

    [data-testid="column"] {
        min-width: 100% !important;
        width: 100% !important;
        flex: 1 1 100% !important;
    }
}

</style>
""",
    unsafe_allow_html=True
)


# =========================================================
# 3. Supabase 연결
# =========================================================

@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )


supabase = get_supabase()


# =========================================================
# 4. Gemini 연결
# =========================================================

@st.cache_resource
def get_gemini():
    return genai.Client(
        api_key=st.secrets["GEMINI_API_KEY"]
    )


gemini = get_gemini()


# =========================================================
# 5. 사용자 구분
# =========================================================

if "uid" in st.query_params:

    user_id = st.query_params["uid"]

    if isinstance(user_id, list):
        user_id = user_id[0]

else:

    user_id = str(uuid.uuid4())
    st.query_params["uid"] = user_id


st.session_state["user_id"] = user_id


# =========================================================
# 6. DB 함수
# =========================================================

def get_expenses():

    try:

        result = (
            supabase
            .table("checki_expenses")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        return result.data or []

    except Exception:
        return []


def get_records():

    try:

        result = (
            supabase
            .table("checki_records")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        return result.data or []

    except Exception:
        return []


def add_expense(
    category,
    item_name,
    amount
):

    data = {
        "user_id": user_id,
        "category": category,
        "item_name": item_name,
        "amount": int(amount),
        "purchased_at": iso_now(),
        "created_at": iso_now()
    }

    return (
        supabase
        .table("checki_expenses")
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

    # 분석 시점에는 가격을 받지 않는다.
    data = {
        "user_id": user_id,
        "product_name": product_name,
        "category": category,
        "product_price": 0,
        "risk_level": risk_level,
        "risk_score": int(risk_score),
        "one_line_summary": summary,
        "detected_elements": detected,
        "ai_result": ai_result,
        "action_text": action_text,
        "decision": "checking",
        "saved_amount": 0,
        "created_at": iso_now()
    }

    result = (
        supabase
        .table("checki_records")
        .insert(data)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


def update_record(
    record_id,
    values
):

    return (
        supabase
        .table("checki_records")
        .update(values)
        .eq("id", record_id)
        .eq("user_id", user_id)
        .execute()
    )


# =========================================================
# 7. 통계
# =========================================================

def calculate_stats():

    expenses = get_expenses()
    records = get_records()

    total_spending = sum(
        int(x.get("amount") or 0)
        for x in expenses
    )

    purchase_checks = len(records)

    abandoned = [
        x
        for x in records
        if x.get("decision") == "abandoned"
    ]

    abandoned_count = len(abandoned)

    saved_amount = sum(
        int(x.get("saved_amount") or 0)
        for x in abandoned
    )

    return {
        "expenses": expenses,
        "records": records,
        "total_spending": total_spending,
        "purchase_checks": purchase_checks,
        "abandoned_count": abandoned_count,
        "saved_amount": saved_amount
    }


# =========================================================
# 8. URL 읽기
# =========================================================

def read_url(url):

    if not url.startswith(
        ("http://", "https://")
    ):
        url = "https://" + url

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

        title = soup.title.get_text(
            " ",
            strip=True
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

    return title, text[:18000]


# =========================================================
# 9. AI Prompt
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

사용자는 지금 특정 상품을 구매할지 고민하고 있다.

상품명: {product_name}
상품 카테고리: {category}
분석 방식: {source_type}

웹페이지에서 추출된 내용이 있는 경우 아래 내용을 참고한다.

--- 웹페이지 내용 시작 ---

{webpage_text}

--- 웹페이지 내용 끝 ---

분석 목적은 상품 자체의 품질을 평가하는 것이 아니라,
사용자가 보고 있는 쇼핑 화면이나 웹페이지에
구매 결정을 부당하게 서두르게 하거나
소비자의 선택을 방해하는 요소가 있는지 확인하는 것이다.

다음 요소를 중점적으로 확인한다.

1. 시간 압박
   - 곧 종료되는 것처럼 보이는 타이머
   - 마감 임박 강조
   - 지금 결제해야 한다는 표현

2. 희소성 압박
   - 품절 임박
   - 재고 몇 개 남음
   - 구매자가 몰리고 있다는 표현

3. 사회적 증거를 이용한 압박
   - 몇 명이 보고 있음
   - 몇 명이 구매함
   - 과도한 인기 강조

4. 가격 및 할인 표현
   - 과도한 할인율 강조
   - 기준 가격이 불명확한 할인
   - 쿠폰을 사용하지 않으면 손해인 것처럼 보이는 표현

5. 추가 비용 또는 조건의 은폐
   - 배송비
   - 구독 조건
   - 자동결제
   - 추가 옵션 비용

6. 선택 방해
   - 거절 버튼을 찾기 어렵게 만드는 디자인
   - 특정 선택지만 지나치게 강조
   - 소비자가 원하지 않는 옵션의 사전 선택

7. 감정적 압박
   - 구매하지 않으면 손해를 보는 것 같은 표현
   - 죄책감이나 불안감을 자극하는 표현

중요:

단순히 할인 중이라는 이유만으로
다크패턴이라고 판단하지 않는다.

화면이나 페이지에서 실제로 확인할 수 없는 내용은
절대로 만들어내지 않는다.

증거가 불충분하면
"명확한 다크패턴 근거가 부족함"이라고 판단한다.

사용자가 구매를 해야 한다거나
하지 말아야 한다고 강제로 결정하지 않는다.

반드시 아래 형식을 그대로 사용한다.

RISK_LEVEL: 낮음/주의/높음 중 하나

RISK_SCORE: 0~100 사이 정수

SUMMARY: 가장 중요한 내용을 한 문장으로 요약

DETECTED: 발견된 구매 유도 요소를 작성.
여러 개라면 | 기호로 구분.
없다면 "뚜렷한 구매 유도 요소 없음"이라고 작성.

ACTION: 결제 전에 사용자가 다시 확인하면 좋은 행동 한 가지

DETAIL:
왜 이런 판단을 했는지 초보 소비자도 이해할 수 있도록 설명한다.
화면이나 페이지에서 확인된 구체적인 표현이나 구조를 근거로 설명한다.
"""


# =========================================================
# 10. AI 응답 파싱
# =========================================================

def extract_value(
    text,
    key,
    default=""
):

    pattern = rf"{key}:\s*(.*)"

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

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
        int(score_match.group())
        if score_match
        else 50
    )

    risk_score = max(
        0,
        min(100, risk_score)
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
        "구매 필요성을 다시 한 번 확인해보세요."
    )

    if "DETAIL:" in text:

        detail = text.split(
            "DETAIL:",
            1
        )[1].strip()

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
# 11. 공통 상단
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
# 12. 메뉴
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
# 13. 홈
# =========================================================

if menu == "🏠 홈":

    stats = calculate_stats()

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
실제 나의 소비 기록과 함께 살펴보며
지금 필요한 소비인지 한 번 더 생각할 수 있도록 도와드려요.
</div>

</div>
""",
        unsafe_allow_html=True
    )

    st.subheader("나의 체키")

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "구매 체크",
            stats["purchase_checks"]
        )

    with c2:

        st.metric(
            "구매 포기",
            stats["abandoned_count"]
        )

    with c3:

        st.metric(
            "방어 금액",
            f'{stats["saved_amount"]:,}원'
        )

    st.markdown(
        "### 체키는 이렇게 도와드려요"
    )

    st.markdown(
        """
<div class="blue-card">
<b>① 구매 화면 체크</b><br><br>
구매를 고민하고 있는 쇼핑 화면의
스크린샷이나 상품 링크를 체키에게 보여주세요.
AI가 구매를 서두르게 만드는 요소가 있는지 살펴봐요.
</div>

<div class="blue-card">
<b>② 잠깐 보류하기</b><br><br>
바로 결제하지 않고
30분 동안 구매 결정을 보류할 수 있어요.
</div>

<div class="blue-card">
<b>③ 나의 소비 확인</b><br><br>
직접 입력한 실제 소비 기록을 기반으로
내 소비 흐름을 확인할 수 있어요.
</div>
""",
        unsafe_allow_html=True
    )


# =========================================================
# 14. 구매체크
# =========================================================

elif menu == "✓ 구매체크":

    st.header(
        "구매 전, 한 번 더 체키해 보세요"
    )

    st.markdown(
        """
<div class="blue-card">

<b>
📸 구매 고민 화면 또는 🔗 상품 링크를 넣어주세요.
</b>

<br><br>

상품 가격은 입력하지 않아도 됩니다.
체키가 화면이나 페이지에 나타난
구매 유도 요소와 다크패턴 가능성을 살펴봅니다.

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

    # -----------------------------------------------------
    # 이미지
    # -----------------------------------------------------

    if analysis_type == "📸 이미지 분석":

        uploaded_file = st.file_uploader(
            "구매를 고민하고 있는 쇼핑 화면",
            type=[
                "png",
                "jpg",
                "jpeg"
            ]
        )

        if uploaded_file is not None:

            image = Image.open(
                uploaded_file
            )

            st.image(
                image,
                caption="체키가 분석할 화면",
                use_container_width=True
            )

    # -----------------------------------------------------
    # 링크
    # -----------------------------------------------------

    else:

        shopping_url = st.text_input(
            "상품 링크",
            placeholder="https://..."
        )

        st.caption(
            "일부 쇼핑몰은 외부 접근을 막고 있어 "
            "링크 분석이 제한될 수 있습니다. "
            "그 경우 상품 화면을 캡처해 이미지 분석을 이용해주세요."
        )

    # -----------------------------------------------------
    # 상품명
    # -----------------------------------------------------

    product_name = st.text_input(
        "상품명",
        placeholder="예: 러닝화"
    )

    # -----------------------------------------------------
    # 카테고리
    # -----------------------------------------------------

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
        if analysis_type == "📸 이미지 분석"
        else bool(shopping_url.strip())
    )

    # -----------------------------------------------------
    # 분석 버튼
    # -----------------------------------------------------

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
                    "체키가 구매 유도 요소를 살펴보고 있어요..."
                ):

                    webpage_text = ""

                    # -----------------------------------------
                    # 링크 분석
                    # -----------------------------------------

                    if analysis_type == "🔗 링크 분석":

                        title, webpage_text = read_url(
                            shopping_url.strip()
                        )

                        prompt = analysis_prompt(
                            product_name,
                            category,
                            "쇼핑 상품 링크",
                            webpage_text
                        )

                        response = (
                            gemini.models.generate_content(
                                model=GEMINI_MODEL,
                                contents=prompt
                            )
                        )

                    # -----------------------------------------
                    # 이미지 분석
                    # -----------------------------------------

                    else:

                        image = Image.open(
                            uploaded_file
                        )

                        prompt = analysis_prompt(
                            product_name,
                            category,
                            "구매 고민 화면 이미지"
                        )

                        response = (
                            gemini.models.generate_content(
                                model=GEMINI_MODEL,
                                contents=[
                                    prompt,
                                    image
                                ]
                            )
                        )

                    ai_text = response.text or ""

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
                        product_name,
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
                            product_name,

                        "category":
                            category
                    }

            except requests.exceptions.RequestException:

                st.error(
                    "이 쇼핑몰의 페이지 내용을 "
                    "직접 불러오지 못했어요.\n\n"
                    "상품 화면을 캡처해서 "
                    "이미지 분석을 이용해주세요."
                )

            except Exception as e:

                st.error(
                    "분석 중 오류가 발생했어요."
                )

                st.code(
                    str(e)
                )


    # =====================================================
    # 분석 결과
    # =====================================================

    if "latest_analysis" in st.session_state:

        result = st.session_state[
            "latest_analysis"
        ]

        record = st.session_state.get(
            "latest_record"
        )

        st.divider()

        st.subheader(
            "체키 분석 결과"
        )

        risk_level = result[
            "risk_level"
        ]

        if risk_level == "높음":
            risk_class = "risk-high"

        elif risk_level == "낮음":
            risk_class = "risk-low"

        else:
            risk_class = "risk-warning"

        st.markdown(
            f"""
<div class="{risk_class}">

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
            result["risk_score"] / 100
        )

        # -------------------------------------------------
        # 발견 요소
        # -------------------------------------------------

        st.markdown(
            "#### ⚠️ 발견된 요소"
        )

        elements = result[
            "detected"
        ].split("|")

        for element in elements:

            if element.strip():

                st.write(
                    "• " +
                    element.strip()
                )

        # -------------------------------------------------
        # 상세 분석
        # -------------------------------------------------

        st.markdown(
            "#### 🧠 체키의 분석"
        )

        st.write(
            result["detail"]
        )

        # -------------------------------------------------
        # 행동
        # -------------------------------------------------

        st.markdown(
            "#### ✅ 결제 전 체크"
        )

        st.info(
            result["action"]
        )

        st.markdown(
            "### 그래서, 이 상품 어떻게 할까요?"
        )

        if record:

            # 가격 입력 없이 보류 가능
            if st.button(
                "⏱️ 일단 30분 보류하기",
                use_container_width=True
            ):

                hold_start = now_kst()

                hold_until = (
                    hold_start +
                    timedelta(minutes=30)
                )

                update_record(
                    record["id"],
                    {
                        "decision":
                            "hold",

                        "hold_started_at":
                            hold_start.isoformat(),

                        "hold_until":
                            hold_until.isoformat()
                    }
                )

                st.success(
                    "좋아요. 30분 동안 구매를 보류했어요. "
                    "MY에서 다시 확인할 수 있어요."
                )

            st.markdown(
                "##### 구매하지 않기로 했나요?"
            )

            st.caption(
                "가격은 AI 분석에는 필요하지 않습니다. "
                "구매를 포기한 뒤 절약한 금액까지 기록하고 싶을 때만 입력하세요."
            )

            abandoned_price = st.number_input(
                "이 상품 가격 (선택)",
                min_value=0,
                step=1000,
                value=0,
                key=f'abandoned_price_{record["id"]}'
            )

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

                        "product_price":
                            int(abandoned_price),

                        "saved_amount":
                            int(abandoned_price),

                        "decided_at":
                            iso_now()
                    }
                )

                if abandoned_price > 0:

                    st.success(
                        f'{int(abandoned_price):,}원의 '
                        "소비를 방어했어요!"
                    )

                else:

                    st.success(
                        "구매하지 않기로 한 결정이 저장됐어요!"
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
# 15. 소비분석
# =========================================================

elif menu == "📊 소비분석":

    stats = calculate_stats()

    st.header(
        "나의 소비분석"
    )

    st.caption(
        "예시 금액이 아니라 "
        "내가 직접 입력한 실제 소비 기록으로 계산됩니다."
    )

    st.markdown(
        "### 이번 소비 기록"
    )

    c1, c2 = st.columns(2)

    with c1:

        st.metric(
            "누적 소비",
            f'{stats["total_spending"]:,}원'
        )

    with c2:

        st.metric(
            "방어한 금액",
            f'{stats["saved_amount"]:,}원'
        )

    st.divider()

    # -----------------------------------------------------
    # 소비 추가
    # -----------------------------------------------------

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
        placeholder="예: 점심, 운동화, 영화",
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

                st.success(
                    "소비내역을 저장했어요."
                )

                st.rerun()

            except Exception as e:

                st.error(
                    "소비내역 저장 중 오류가 발생했어요."
                )

                st.code(
                    str(e)
                )

    # -----------------------------------------------------
    # 실제 소비
    # -----------------------------------------------------

    expenses = get_expenses()

    st.divider()

    st.markdown(
        "### 나의 소비내역"
    )

    if not expenses:

        st.info(
            "아직 등록된 소비내역이 없어요. "
            "위에서 첫 소비내역을 추가해보세요."
        )

    else:

        category_totals = {}

        for expense in expenses:

            cat = (
                expense.get("category")
                or "기타"
            )

            amount = int(
                expense.get("amount")
                or 0
            )

            category_totals[cat] = (
                category_totals.get(
                    cat,
                    0
                )
                + amount
            )

        # ---------------------------------------------
        # 카테고리별
        # ---------------------------------------------

        st.markdown(
            "#### 카테고리별 소비"
        )

        max_category_amount = max(
            category_totals.values()
        )

        for cat, amount in sorted(
            category_totals.items(),
            key=lambda x: x[1],
            reverse=True
        ):

            st.write(
                f"**{cat}** · {amount:,}원"
            )

            if max_category_amount > 0:

                st.progress(
                    amount /
                    max_category_amount
                )

        st.divider()

        # ---------------------------------------------
        # 최근 소비
        # ---------------------------------------------

        st.markdown(
            "#### 최근 소비"
        )

        for expense in expenses[:10]:

            name = (
                expense.get("item_name")
                or "소비"
            )

            cat = (
                expense.get("category")
                or "기타"
            )

            amount = int(
                expense.get("amount")
                or 0
            )

            st.markdown(
                f"""
<div class="info-card">

<b>{name}</b>

<br>

<span style="color:#7a8795">
{cat}
</span>

<br><br>

<b>{amount:,}원</b>

</div>
""",
                unsafe_allow_html=True
            )


# =========================================================
# 16. MY
# =========================================================

elif menu == "👤 MY":

    stats = calculate_stats()
    records = stats["records"]

    st.header(
        "MY"
    )

    st.markdown(
        "### 나의 체키 기록"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "구매 체크",
            stats["purchase_checks"]
        )

    with c2:

        st.metric(
            "구매 포기",
            stats["abandoned_count"]
        )

    with c3:

        st.metric(
            "방어 금액",
            f'{stats["saved_amount"]:,}원'
        )

    st.divider()

    # =====================================================
    # 보류 중 구매
    # =====================================================

    st.markdown(
        "### ⏱️ 보류 중인 구매"
    )

    hold_records = [
        x
        for x in records
        if x.get("decision") == "hold"
    ]

    active_holds = []

    for record in hold_records:

        hold_until_text = record.get(
            "hold_until"
        )

        if not hold_until_text:
            continue

        try:

            hold_until = (
                datetime.fromisoformat(
                    hold_until_text.replace(
                        "Z",
                        "+00:00"
                    )
                )
            )

            if hold_until.tzinfo is None:

                hold_until = (
                    hold_until.replace(
                        tzinfo=KST
                    )
                )

            if hold_until > now_kst():

                active_holds.append(
                    (
                        record,
                        hold_until
                    )
                )

        except Exception:
            pass

    # -----------------------------------------------------
    # 보류 없음
    # -----------------------------------------------------

    if not active_holds:

        st.info(
            "현재 보류 중인 구매가 없어요."
        )

    # -----------------------------------------------------
    # 보류 있음
    # -----------------------------------------------------

    else:

        for record, hold_until in active_holds:

            remaining = (
                hold_until -
                now_kst()
            )

            remaining_seconds = max(
                0,
                int(
                    remaining.total_seconds()
                )
            )

            remaining_minutes = (
                remaining_seconds // 60
            )

            remaining_sec = (
                remaining_seconds % 60
            )

            product = (
                record.get("product_name")
                or "상품"
            )

            category = (
                record.get("category")
                or "기타"
            )

            st.markdown(
                f"""
<div class="result-card">

<b>{product}</b>

<br>

<span style="color:#7a8795">
{category}
</span>

<br><br>

⏱️ 약 {remaining_minutes}분 {remaining_sec}초 남음

</div>
""",
                unsafe_allow_html=True
            )

            # ---------------------------------------------
            # 30분 뒤 구매
            # ---------------------------------------------

            purchase_price = st.number_input(
                "구매하기로 했다면 실제 결제 금액",
                min_value=0,
                step=1000,
                value=0,
                key=f'purchase_price_{record["id"]}'
            )

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "구매하기",
                    key=f'buy_{record["id"]}',
                    use_container_width=True
                ):

                    if purchase_price <= 0:

                        st.warning(
                            "실제 구매 금액을 입력해주세요."
                        )

                    else:

                        update_record(
                            record["id"],
                            {
                                "decision":
                                    "purchased",

                                "product_price":
                                    int(purchase_price),

                                "decided_at":
                                    iso_now()
                            }
                        )

                        try:

                            add_expense(
                                category,
                                product,
                                purchase_price
                            )

                        except Exception:
                            pass

                        st.success(
                            "구매 결정과 소비내역이 저장됐어요."
                        )

                        st.rerun()

            # ---------------------------------------------
            # 30분 뒤 포기
            # ---------------------------------------------

            with col2:

                if st.button(
                    "구매 포기",
                    key=f'abandon_{record["id"]}',
                    type="primary",
                    use_container_width=True
                ):

                    update_record(
                        record["id"],
                        {
                            "decision":
                                "abandoned",

                            "product_price":
                                int(purchase_price),

                            "saved_amount":
                                int(purchase_price),

                            "decided_at":
                                iso_now()
                        }
                    )

                    if purchase_price > 0:

                        st.success(
                            f"{int(purchase_price):,}원의 "
                            "소비를 방어했어요."
                        )

                    else:

                        st.success(
                            "구매 포기 결정이 저장됐어요."
                        )

                    st.rerun()

    st.divider()

    # =====================================================
    # 최근 체크
    # =====================================================

    st.markdown(
        "### 최근 구매체크"
    )

    if not records:

        st.info(
            "아직 구매체크 기록이 없어요."
        )

    else:

        for record in records[:10]:

            product = (
                record.get("product_name")
                or "상품"
            )

            category = (
                record.get("category")
                or "기타"
            )

            price = int(
                record.get("product_price")
                or 0
            )

            risk = (
                record.get("risk_level")
                or "-"
            )

            decision = (
                record.get("decision")
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

            price_text = (
                f"{price:,}원"
                if price > 0
                else "가격 미입력"
            )

            st.markdown(
                f"""
<div class="info-card">

<b>{product}</b>

<br>

<span style="color:#7a8795">
{category}
</span>

<br><br>

{price_text}

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
