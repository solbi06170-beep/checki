import streamlit as st
from google import genai
from PIL import Image
import time
import re
from datetime import datetime, timedelta

# =========================================================
# CHECKI
# =========================================================

st.set_page_config(
    page_title="체키 | CHECKI",
    page_icon="✓",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# =========================================================
# CSS
# =========================================================

st.markdown("""
<style>

html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                 "Noto Sans KR", sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 100% 0%, #eef6ff 0%, transparent 30%),
        #f7faff;
}

.block-container {
    max-width: 760px;
    padding-top: 1.4rem;
    padding-bottom: 7rem;
}

#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {background:transparent !important;}

.checki-header {
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:12px;
}

.logo {
    font-size:28px;
    font-weight:900;
    color:#1683ff;
    letter-spacing:-1.5px;
}

.logo-sub {
    color:#8b97a7;
    font-size:12px;
    margin-top:2px;
}

.hero {
    background:
        linear-gradient(135deg,#eff7ff 0%,#ffffff 55%,#f3f0ff 100%);
    border:1px solid #e4edf8;
    padding:30px 25px;
    border-radius:27px;
    margin:15px 0 20px 0;
    box-shadow:0 12px 35px rgba(31,105,190,.07);
}

.hero-tag {
    display:inline-block;
    background:#e4f1ff;
    color:#1683ff;
    font-size:12px;
    font-weight:800;
    padding:7px 11px;
    border-radius:30px;
    margin-bottom:13px;
}

.hero-title {
    color:#0d2c5a;
    font-size:29px;
    line-height:1.3;
    font-weight:900;
    letter-spacing:-1.3px;
}

.hero-desc {
    color:#69798d;
    font-size:14px;
    line-height:1.7;
    margin-top:12px;
}

.section-title {
    color:#102d57;
    font-size:21px;
    font-weight:900;
    letter-spacing:-.7px;
    margin:26px 0 13px 0;
}

.subtext {
    color:#78879a;
    font-size:14px;
    line-height:1.6;
    margin-bottom:18px;
}

.white-card {
    background:white;
    border:1px solid #e8eef6;
    border-radius:22px;
    padding:20px;
    margin:11px 0;
    box-shadow:0 7px 25px rgba(30,78,130,.05);
}

.blue-card {
    background:linear-gradient(135deg,#edf7ff,#f7fbff);
    border:1px solid #dcecff;
    border-radius:22px;
    padding:20px;
    margin:11px 0;
}

.red-card {
    background:linear-gradient(135deg,#fff1f1,#fff8f8);
    border:1px solid #ffdcdc;
    border-radius:22px;
    padding:20px;
    margin:11px 0;
}

.purple-card {
    background:linear-gradient(135deg,#f6f1ff,#fbf9ff);
    border:1px solid #ebe0ff;
    border-radius:22px;
    padding:20px;
    margin:11px 0;
}

.green-card {
    background:linear-gradient(135deg,#effcf6,#f8fffb);
    border:1px solid #d8f3e5;
    border-radius:22px;
    padding:20px;
    margin:11px 0;
}

.card-title {
    font-size:17px;
    font-weight:900;
    color:#17355e;
    margin-bottom:7px;
}

.card-desc {
    font-size:14px;
    color:#718096;
    line-height:1.6;
}

.red-title {
    color:#e54b4b;
    font-size:17px;
    font-weight:900;
}

.big-score {
    font-size:39px;
    font-weight:900;
    color:#e84e4e;
}

.tag-red {
    display:inline-block;
    background:#ffe1e1;
    color:#e64d4d;
    font-size:12px;
    font-weight:800;
    padding:5px 10px;
    border-radius:20px;
    margin:5px 4px 0 0;
}

.tag-blue {
    display:inline-block;
    background:#e5f2ff;
    color:#1683ff;
    font-size:12px;
    font-weight:800;
    padding:5px 10px;
    border-radius:20px;
    margin:5px 4px 0 0;
}

.stat {
    background:white;
    border:1px solid #e7eef7;
    border-radius:20px;
    padding:18px 8px;
    text-align:center;
    min-height:100px;
    box-shadow:0 6px 20px rgba(30,78,130,.04);
}

.stat-num {
    color:#1683ff;
    font-size:23px;
    font-weight:900;
}

.stat-name {
    color:#8794a5;
    font-size:12px;
    margin-top:5px;
}

.progress-bg {
    height:9px;
    background:#e8f1fb;
    border-radius:20px;
    overflow:hidden;
    margin-top:10px;
}

.progress-blue {
    height:100%;
    background:#2188ff;
    border-radius:20px;
}

.purchase-title {
    font-size:25px;
    font-weight:900;
    color:#102d57;
    line-height:1.35;
    text-align:center;
    margin:20px 0 5px 0;
}

.purchase-sub {
    text-align:center;
    color:#7b899b;
    font-size:14px;
    margin-bottom:20px;
}

.timer {
    font-size:43px;
    color:#1683ff;
    font-weight:900;
    text-align:center;
    padding:16px 0;
}

div.stButton > button {
    width:100%;
    min-height:49px;
    border-radius:14px;
    font-weight:800;
    border:1px solid #dce7f5;
}

div.stButton > button[kind="primary"] {
    background:#1683ff;
    border-color:#1683ff;
    color:white;
}

div[data-testid="stFileUploader"] {
    background:white;
    border:1px solid #e5edf7;
    border-radius:20px;
    padding:10px;
}

div[data-testid="stRadio"] > div {
    background:white;
    padding:5px;
    border-radius:17px;
    border:1px solid #e5edf7;
}

hr {
    border-color:#edf1f6;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# SESSION
# =========================================================

defaults = {
    "analysis_count": 0,
    "stopped_count": 0,
    "saved_money": 0,
    "hold_until": None,
    "hold_product": "",
    "hold_price": 0,
    "hold_reason": "",
    "last_result": None,
    "last_image": None
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# HEADER
# =========================================================

st.markdown("""
<div class="checki-header">
    <div>
        <div class="logo">체키</div>
        <div class="logo-sub">CHECK BEFORE YOU BUY</div>
    </div>
    <div style="font-size:23px;">✓</div>
</div>
""", unsafe_allow_html=True)


# =========================================================
# NAVIGATION
# =========================================================

menu = st.radio(
    "메뉴",
    ["🏠 홈", "✓ 구매체크", "📊 소비분석", "👤 MY"],
    horizontal=True,
    label_visibility="collapsed"
)

page = menu.split(" ", 1)[1]


# =========================================================
# HOME
# =========================================================

if page == "홈":

    st.markdown("""
    <div class="hero">

        <div class="hero-tag">
            AI 소비 방어 도우미
        </div>

        <div class="hero-title">
            구매 전,<br>
            한 번 더 체키해 보세요.
        </div>

        <div class="hero-desc">
            쇼핑 화면 속 구매 유도 요소를 확인하고,
            내 소비상황과 비교해 지금 필요한 소비인지
            한 번 더 생각할 수 있도록 도와드려요.
        </div>

    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="section-title">이번 달 나의 체키</div>',
        unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(f"""
        <div class="stat">
            <div class="stat-num">
                {st.session_state.analysis_count}
            </div>
            <div class="stat-name">
                구매 체크
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="stat">
            <div class="stat-num">
                {st.session_state.stopped_count}
            </div>
            <div class="stat-name">
                구매 포기
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="stat">
            <div class="stat-num">
                {st.session_state.saved_money:,}
            </div>
            <div class="stat-name">
                방어 금액(원)
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(
        '<div class="section-title">체키는 이렇게 도와드려요</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div class="white-card">
        <div class="card-title">🔎 구매 유도 요소 확인</div>
        <div class="card-desc">
            타이머, 재고 부족 강조, 과도한 할인 표시 등
            구매를 서두르게 만드는 화면 요소를 AI가 확인해요.
        </div>
    </div>

    <div class="blue-card">
        <div class="card-title">📊 내 소비상황과 비교</div>
        <div class="card-desc">
            이번 달 예산과 최근 구매내역을 함께 살펴보고
            지금 구매가 내 소비상황에 적절한지 확인해요.
        </div>
    </div>

    <div class="purple-card">
        <div class="card-title">⏸ 잠시 보류하기</div>
        <div class="card-desc">
            바로 결제하지 않고 30분 또는 24시간 동안
            구매를 보류해 충동적인 결제를 줄여요.
        </div>
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# PURCHASE CHECK
# =========================================================

elif page == "구매체크":

    st.markdown(
        '<div class="section-title">구매 전, 체키해 보세요</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div class="subtext">
        구매하려는 쇼핑 화면을 캡처해서 올려주세요.<br>
        체키가 구매 유도 요소를 먼저 확인해드려요.
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "구매 화면 업로드",
        type=["png", "jpg", "jpeg"]
    )

    price_input = st.number_input(
        "상품 가격 (선택)",
        min_value=0,
        step=1000,
        format="%d",
        help="입력하면 구매 보류·소비 방어 기능과 연결할 수 있어요."
    )

    product_input = st.text_input(
        "상품명 (선택)",
        placeholder="예: Balance 러닝화"
    )

    if uploaded_file:

        image = Image.open(uploaded_file)

        st.image(
            image,
            caption="구매하려는 화면",
            use_container_width=True
        )

        if st.button(
            "✓ 체키에게 확인받기",
            type="primary",
            use_container_width=True
        ):

            try:

                client = genai.Client(
                    api_key=st.secrets["GEMINI_API_KEY"]
                )

                prompt = """
너는 AI 소비자 보호 서비스 '체키'다.

사용자가 온라인 쇼핑 결제 전에 올린 화면을 분석한다.

목적은 사용자를 겁주거나 구매를 무조건 막는 것이 아니라,
구매 결정을 서두르게 만드는 요소를 찾아
소비자가 한 번 더 생각할 수 있도록 돕는 것이다.

다음을 확인하라.

1. 긴급성
- 오늘만 할인
- 카운트다운
- 곧 종료 등의 표현

2. 희소성
- 재고 부족
- 몇 개 남음
- 품절 임박

3. 사회적 압박
- 몇 명이 보고 있음
- 최근 몇 개 판매
- 인기 상품 등의 표현

4. 가격 강조
- 과도한 할인율
- 기준가격을 이용한 가격 착시 가능성

5. 사전 선택
- 사용자가 선택하지 않은 추가 상품이나 옵션이
  미리 선택되어 있는지

6. 기타
- 자동결제
- 구독
- 취소 방해
- 구매 버튼 과도한 강조 등

화면에 실제로 보이는 내용만 근거로 판단한다.
확실하지 않은 것은 단정하지 않는다.

반드시 다음 형식으로 답변한다.

RISK: 낮음 / 주의 / 높음
SCORE: 0~100 사이 숫자
SUMMARY: 한 문장
TYPES: 발견 유형을 쉼표로 구분
EVIDENCE: 화면에서 가장 중요한 실제 근거 1~3개를 짧게 설명
ACTION: 결제 전 확인할 내용 한 문장
"""

                result = None
                last_error = None

                progress = st.progress(10)
                status = st.empty()

                steps = [
                    "구매 화면 분석 중",
                    "구매 유도 요소 확인 중",
                    "가격 정보 확인 중",
                    "내 소비내역 확인 중"
                ]

                for attempt in range(3):

                    try:

                        status.info("✓ " + steps[0])
                        progress.progress(25)

                        time.sleep(0.4)

                        status.info("✓ " + steps[1])
                        progress.progress(50)

                        response = client.models.generate_content(
                            model="gemini-3.8-flash",
                            contents=[prompt, image]
                        )

                        status.info("✓ " + steps[2])
                        progress.progress(75)

                        time.sleep(0.3)

                        status.info("✓ " + steps[3])
                        progress.progress(95)

                        result = response.text

                        progress.progress(100)

                        break

                    except Exception as e:

                        last_error = e

                        if "503" in str(e) or "UNAVAILABLE" in str(e):

                            if attempt < 2:
                                status.warning(
                                    "AI 요청이 많아 자동으로 다시 확인하고 있어요."
                                )
                                time.sleep(2 * (attempt + 1))

                            continue

                        raise e

                if result:

                    time.sleep(0.3)

                    progress.empty()
                    status.empty()

                    st.session_state.analysis_count += 1
                    st.session_state.last_result = result
                    st.session_state.last_image = image

                    risk_match = re.search(
                        r"RISK:\s*(.+)",
                        result
                    )

                    score_match = re.search(
                        r"SCORE:\s*(\d+)",
                        result
                    )

                    summary_match = re.search(
                        r"SUMMARY:\s*(.+)",
                        result
                    )

                    types_match = re.search(
                        r"TYPES:\s*(.+)",
                        result
                    )

                    evidence_match = re.search(
                        r"EVIDENCE:\s*(.+)",
                        result
                    )

                    action_match = re.search(
                        r"ACTION:\s*(.+)",
                        result
                    )

                    risk = (
                        risk_match.group(1).strip()
                        if risk_match else "주의"
                    )

                    score = (
                        int(score_match.group(1))
                        if score_match else 60
                    )

                    summary = (
                        summary_match.group(1).strip()
                        if summary_match
                        else "구매 전 한 번 더 확인해보세요."
                    )

                    types = (
                        types_match.group(1).strip()
                        if types_match else "구매 유도"
                    )

                    evidence = (
                        evidence_match.group(1).strip()
                        if evidence_match else result
                    )

                    action = (
                        action_match.group(1).strip()
                        if action_match
                        else "결제 전 다시 확인해보세요."
                    )

                    st.markdown("""
                    <div class="purchase-title">
                        체키가 확인했어요!
                    </div>

                    <div class="purchase-sub">
                        구매 전에 아래 내용을 한 번 확인해 보세요.
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"""
                    <div class="red-card">

                        <div class="red-title">
                            ⚠️ 구매 유도 요소가 발견됐어요
                        </div>

                        <div style="
                            margin-top:10px;
                            color:#37475b;
                            font-weight:700;
                        ">
                            {summary}
                        </div>

                        <div style="margin-top:13px;">
                            <span class="tag-red">
                                {types}
                            </span>
                        </div>

                        <div class="card-desc"
                             style="margin-top:13px;">
                            {evidence}
                        </div>

                    </div>
                    """, unsafe_allow_html=True)

                    # ---------------------------------
                    # 가격 비교: MVP 샘플
                    # ---------------------------------

                    st.markdown("""
                    <div class="blue-card">

                        <div class="card-title">
                            📊 가격을 확인했어요
                        </div>

                        <div class="card-desc">
                            현재 MVP에서는 실제 가격 추적 데이터 대신
                            샘플 비교 정보를 사용하고 있어요.<br><br>

                            최근 가격과 비교했을 때
                            <b>큰 가격 차이는 없는 상품</b>으로
                            가정하여 보여드리고 있어요.
                        </div>

                    </div>
                    """, unsafe_allow_html=True)

                    # ---------------------------------
                    # 소비상황: MVP 샘플
                    # ---------------------------------

                    st.markdown("""
                    <div class="purple-card">

                        <div class="card-title">
                            💳 나의 소비상황과 비교했어요
                        </div>

                        <div class="card-desc">
                            이번 달 의류 예산
                            <b>300,000원 중 246,000원</b>을 사용했어요.
                            <br><br>

                            현재 예산의
                            <b>82%</b>를 사용한 상태예요.
                            <br><br>

                            14일 전에도 비슷한 카테고리의
                            상품을 구매한 기록이 있어요.
                        </div>

                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"""
                    <div class="white-card">

                        <div class="card-title">
                            ✓ 결제 전 마지막 CHECK
                        </div>

                        <div class="card-desc">
                            {action}
                        </div>

                        <div style="
                            margin-top:14px;
                            font-size:13px;
                            color:#9aa4b1;
                        ">
                            소비 유도 위험 점수
                        </div>

                        <div class="big-score">
                            {score}
                            <span style="
                                font-size:15px;
                                color:#8794a5;
                            ">
                                / 100
                            </span>
                        </div>

                    </div>
                    """, unsafe_allow_html=True)

                    st.session_state.temp_product = (
                        product_input or "구매 예정 상품"
                    )

                    st.session_state.temp_price = int(price_input)

                else:

                    st.error(
                        "현재 AI 분석 요청이 많아요. "
                        "잠시 후 다시 시도해주세요."
                    )

                    if last_error:

                        with st.expander("오류 정보"):
                            st.caption(str(last_error))

            except Exception as e:

                st.error("분석 중 오류가 발생했습니다.")

                with st.expander("오류 정보"):
                    st.caption(str(e))

    # =====================================================
    # 이전 분석 결과가 있으면 구매 선택 표시
    # =====================================================

    if st.session_state.last_result:

        st.markdown(
            '<div class="section-title">이제 어떻게 할까요?</div>',
            unsafe_allow_html=True
        )

        if st.button(
            "구매 계속하기",
            type="primary",
            use_container_width=True
        ):

            st.info(
                "구매를 계속하기로 했어요. "
                "체키가 확인한 내용을 참고해 신중하게 결정해주세요."
            )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "⏸ 잠시 보류하기",
                use_container_width=True
            ):

                st.session_state.hold_product = (
                    st.session_state.get(
                        "temp_product",
                        "구매 예정 상품"
                    )
                )

                st.session_state.hold_price = (
                    st.session_state.get(
                        "temp_price",
                        0
                    )
                )

                st.session_state.hold_until = (
                    datetime.now()
                    + timedelta(minutes=30)
                )

                st.success(
                    "30분 동안 구매를 보류했어요. "
                    "MY 메뉴에서 확인할 수 있어요."
                )

        with c2:

            if st.button(
                "구매하지 않기",
                use_container_width=True
            ):

                price = st.session_state.get(
                    "temp_price",
                    0
                )

                st.session_state.stopped_count += 1
                st.session_state.saved_money += price

                if price > 0:

                    st.success(
                        f"🎉 {price:,}원의 소비를 "
                        f"다시 생각하는 데 성공했어요!"
                    )

                else:

                    st.success(
                        "🎉 이번 구매를 다시 생각하기로 했어요!"
                    )

                st.session_state.last_result = None


# =========================================================
# SPENDING ANALYSIS
# =========================================================

elif page == "소비분석":

    st.markdown(
        '<div class="section-title">소비분석</div>',
        unsafe_allow_html=True
    )

    st.caption(
        "※ 현재 경진대회 MVP에서는 아래 소비내역을 "
        "샘플 데이터로 제공합니다."
    )

    period = st.radio(
        "기간",
        ["이번 달", "최근 3개월", "전체"],
        horizontal=True,
        label_visibility="collapsed"
    )

    st.markdown("""
    <div class="hero">

        <div class="hero-tag">
            이번 달 소비 리포트
        </div>

        <div class="hero-title">
            이번 달<br>
            내 소비상황을 확인해 볼까요?
        </div>

        <div class="hero-desc">
            예산과 지출을 비교하고
            반복되는 소비 패턴을 확인해보세요.
        </div>

    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="white-card">

        <div class="card-title">
            👕 의류
            <span style="float:right;">
                82%
            </span>
        </div>

        <div class="card-desc">
            246,000원 / 300,000원
        </div>

        <div class="progress-bg">
            <div class="progress-blue"
                 style="width:82%;">
            </div>
        </div>

    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="section-title">카테고리별 지출</div>',
        unsafe_allow_html=True
    )

    categories = [
        ("👕 의류", 246000, 82),
        ("🍴 식비", 180000, 60),
        ("🧴 뷰티", 72000, 36),
        ("🛒 생활용품", 45000, 30)
    ]

    for name, amount, percent in categories:

        st.markdown(f"""
        <div class="white-card">

            <div style="
                display:flex;
                justify-content:space-between;
                font-weight:800;
                color:#24405f;
            ">
                <span>{name}</span>
                <span>{amount:,}원</span>
            </div>

            <div class="progress-bg">
                <div class="progress-blue"
                     style="width:{percent}%;">
                </div>
            </div>

            <div style="
                text-align:right;
                color:#7f8ea1;
                font-size:12px;
                margin-top:5px;
            ">
                {percent}%
            </div>

        </div>
        """, unsafe_allow_html=True)

    st.markdown(
        '<div class="section-title">최근 구매</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div class="white-card">
        <b>👟 운동화</b>
        <span style="float:right;font-weight:800;">
            79,000원
        </span>
        <div class="card-desc">14일 전</div>
    </div>

    <div class="white-card">
        <b>👔 셔츠</b>
        <span style="float:right;font-weight:800;">
            59,000원
        </span>
        <div class="card-desc">1개월 전</div>
    </div>

    <div class="white-card">
        <b>🧢 모자</b>
        <span style="float:right;font-weight:800;">
            45,000원
        </span>
        <div class="card-desc">1개월 전</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="purple-card">
        <div class="card-title">
            💡 체키 인사이트
        </div>
        <div class="card-desc">
            최근 비슷한 카테고리의 상품을 구매했어요.<br>
            이번 달 의류 예산도 이미 82% 사용했어요.
        </div>
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# MY
# =========================================================

elif page == "MY":

    st.markdown(
        '<div class="section-title">MY 체키</div>',
        unsafe_allow_html=True
    )

    c1, c2 = st.columns(2)

    with c1:

        st.metric(
            "구매 체크",
            f"{st.session_state.analysis_count}회"
        )

    with c2:

        st.metric(
            "구매 포기",
            f"{st.session_state.stopped_count}회"
        )

    st.metric(
        "방어한 소비",
        f"{st.session_state.saved_money:,}원"
    )

    # 구매 보류 중
    if st.session_state.hold_until:

        remaining = (
            st.session_state.hold_until
            - datetime.now()
        )

        seconds = max(
            0,
            int(remaining.total_seconds())
        )

        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60

        st.markdown(
            '<div class="section-title">구매 보류 중</div>',
            unsafe_allow_html=True
        )

        st.markdown(f"""
        <div class="blue-card">

            <div class="card-title">
                🔒 {st.session_state.hold_product}
            </div>

            <div class="card-desc">
                {st.session_state.hold_price:,}원
            </div>

            <div class="timer">
                {h:02d}:{m:02d}:{s:02d}
            </div>

            <div class="card-desc"
                 style="text-align:center;">
                남은 고민 시간
            </div>

        </div>
        """, unsafe_allow_html=True)

        st.caption(
            "화면을 새로고침하면 남은 시간이 갱신됩니다."
        )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "구매하지 않기",
                type="primary",
                use_container_width=True
            ):

                st.session_state.stopped_count += 1

                st.session_state.saved_money += (
                    st.session_state.hold_price
                )

                st.session_state.hold_until = None

                st.success(
                    "이번 구매를 다시 생각하는 데 성공했어요!"
                )

                st.rerun()

        with c2:

            if st.button(
                "보류 종료",
                use_container_width=True
            ):

                st.session_state.hold_until = None

                st.rerun()

    else:

        st.markdown("""
        <div class="blue-card">
            <div class="card-title">
                ⏸ 현재 보류 중인 구매가 없어요
            </div>

            <div class="card-desc">
                구매체크 후 고민되는 상품이 있다면
                '잠시 보류하기'를 사용해보세요.
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(
        '<div class="section-title">체키 기록</div>',
        unsafe_allow_html=True
    )

    if st.session_state.stopped_count > 0:

        st.markdown(f"""
        <div class="green-card">

            <div class="card-title">
                🎉 잘하고 있어요!
            </div>

            <div class="card-desc">
                지금까지
                <b>{st.session_state.stopped_count}번</b>의 구매를
                다시 생각했고,
                총 <b>{st.session_state.saved_money:,}원</b>의
                소비를 방어했어요.
            </div>

        </div>
        """, unsafe_allow_html=True)

    else:

        st.markdown("""
        <div class="white-card">
            <div class="card-desc">
                아직 구매 포기 기록이 없어요.<br>
                첫 번째 구매체크를 시작해보세요.
            </div>
        </div>
        """, unsafe_allow_html=True)


# =========================================================
# FOOTER
# =========================================================

st.markdown("<br><br>", unsafe_allow_html=True)

st.markdown("""
<div style="
    text-align:center;
    color:#a2adba;
    font-size:11px;
    line-height:1.7;
">
    CHECKI · AI 소비자 보호 서비스 MVP<br>
    AI 분석은 소비 판단을 돕기 위한 참고 정보입니다.
</div>
""", unsafe_allow_html=True)
