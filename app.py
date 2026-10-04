import streamlit as st
from google import genai
from PIL import Image
import time
from datetime import datetime, timedelta

# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="CHECKI | 충동결제 방어",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# =========================================================
# 디자인
# =========================================================

st.markdown("""
<style>

.stApp {
    background:
        radial-gradient(circle at 10% 0%, #fff1f3 0%, transparent 32%),
        linear-gradient(180deg, #ffffff 0%, #fffafb 100%);
}

.block-container {
    max-width: 820px;
    padding-top: 2rem;
    padding-bottom: 6rem;
}

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

.checki-logo {
    font-size: 32px;
    font-weight: 900;
    letter-spacing: -1px;
    color: #111111;
    margin-bottom: 0px;
}

.checki-logo span {
    color: #ff3b5c;
}

.hero {
    padding: 34px 28px;
    border-radius: 28px;
    background: linear-gradient(135deg, #ff3b5c 0%, #ff6b7f 100%);
    color: white;
    margin: 18px 0 24px 0;
    box-shadow: 0 12px 30px rgba(255, 59, 92, 0.18);
}

.hero-small {
    font-size: 14px;
    font-weight: 700;
    opacity: 0.9;
    margin-bottom: 10px;
}

.hero-title {
    font-size: 31px;
    font-weight: 900;
    line-height: 1.25;
    letter-spacing: -1.2px;
}

.hero-text {
    margin-top: 12px;
    font-size: 15px;
    line-height: 1.6;
    opacity: 0.94;
}

.section-title {
    font-size: 22px;
    font-weight: 900;
    letter-spacing: -0.6px;
    margin-top: 28px;
    margin-bottom: 13px;
}

.card {
    background: rgba(255,255,255,0.92);
    padding: 21px;
    border-radius: 20px;
    border: 1px solid #f0e9eb;
    margin-bottom: 12px;
    box-shadow: 0 6px 20px rgba(30,20,20,0.04);
}

.card-icon {
    font-size: 25px;
    margin-bottom: 8px;
}

.card-title {
    font-size: 17px;
    font-weight: 850;
    color: #171717;
    margin-bottom: 5px;
}

.card-text {
    color: #6d6668;
    font-size: 14px;
    line-height: 1.55;
}

.stat {
    background: white;
    border: 1px solid #f0e9eb;
    border-radius: 18px;
    padding: 18px 10px;
    text-align: center;
}

.stat-number {
    font-size: 24px;
    font-weight: 900;
    color: #ff3b5c;
}

.stat-label {
    font-size: 12px;
    color: #81797b;
    margin-top: 3px;
}

.stop-card {
    background: #fff4f5;
    border: 1px solid #ffd7dd;
    border-radius: 22px;
    padding: 23px;
    margin: 15px 0;
}

.timer {
    text-align: center;
    font-size: 42px;
    font-weight: 900;
    color: #ff3b5c;
    padding: 18px;
}

.safe-box {
    background: #f4fbf7;
    border: 1px solid #d7efe0;
    border-radius: 18px;
    padding: 18px;
    margin: 10px 0;
}

.notice {
    background: #fff8e8;
    padding: 16px 18px;
    border-radius: 16px;
    font-size: 14px;
    line-height: 1.55;
    margin: 15px 0;
}

div.stButton > button {
    border-radius: 14px;
    min-height: 48px;
    font-weight: 800;
}

div.stButton > button[kind="primary"] {
    background: #ff3b5c;
    border-color: #ff3b5c;
}

div[data-testid="stFileUploader"] {
    background: white;
    border-radius: 20px;
    padding: 10px;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# 세션 데이터
# =========================================================

if "page" not in st.session_state:
    st.session_state.page = "홈"

if "analysis_count" not in st.session_state:
    st.session_state.analysis_count = 0

if "stop_count" not in st.session_state:
    st.session_state.stop_count = 0

if "saved_money" not in st.session_state:
    st.session_state.saved_money = 0

if "hold_until" not in st.session_state:
    st.session_state.hold_until = None

if "hold_product" not in st.session_state:
    st.session_state.hold_product = ""

if "hold_price" not in st.session_state:
    st.session_state.hold_price = 0

if "purchase_reason" not in st.session_state:
    st.session_state.purchase_reason = ""

# =========================================================
# 공통 헤더
# =========================================================

st.markdown(
    '<div class="checki-logo">CHECK<span>I</span></div>',
    unsafe_allow_html=True
)

st.caption("충동적인 소비 전에, 체키하세요.")

# =========================================================
# 네비게이션
# =========================================================

pages = ["🏠 홈", "🔎 AI 분석", "⏸️ 결제 멈추기", "📊 리포트"]

selected = st.radio(
    "메뉴",
    pages,
    horizontal=True,
    label_visibility="collapsed"
)

page = selected.split(" ", 1)[1]

# =========================================================
# 홈
# =========================================================

if page == "홈":

    st.markdown("""
    <div class="hero">
        <div class="hero-small">AI CONSUMER GUARD</div>

        <div class="hero-title">
            결제 버튼을 누르기 전,<br>
            한 번 더 CHECK.
        </div>

        <div class="hero-text">
            쇼핑 화면 속 소비 유도 요소를 AI가 찾아내고,
            충동적인 결제라면 잠시 멈춰 생각할 시간을 만들어드려요.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="section-title">오늘의 CHECKI</div>',
        unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            f"""
            <div class="stat">
                <div class="stat-number">{st.session_state.analysis_count}</div>
                <div class="stat-label">AI 분석</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c2:
        st.markdown(
            f"""
            <div class="stat">
                <div class="stat-number">{st.session_state.stop_count}</div>
                <div class="stat-label">구매 포기</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c3:
        st.markdown(
            f"""
            <div class="stat">
                <div class="stat-number">{st.session_state.saved_money:,}</div>
                <div class="stat-label">방어 금액(원)</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown(
        '<div class="section-title">체키가 도와드려요</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    <div class="card">
        <div class="card-icon">🔎</div>
        <div class="card-title">AI 쇼핑 화면 분석</div>
        <div class="card-text">
            쇼핑 화면을 올리면 시간 압박, 희소성 강조,
            사회적 압박, 사전 선택 등 소비 유도 요소를 분석해요.
        </div>
    </div>

    <div class="card">
        <div class="card-icon">⏸️</div>
        <div class="card-title">결제 멈추기</div>
        <div class="card-text">
            사고 싶은 마음이 강할수록 바로 결제하지 말고
            체키에 잠시 보관해보세요.
        </div>
    </div>

    <div class="card">
        <div class="card-icon">📊</div>
        <div class="card-title">소비 방어 리포트</div>
        <div class="card-text">
            얼마나 분석했고, 몇 번의 구매를 다시 생각했는지
            한눈에 확인할 수 있어요.
        </div>
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# AI 분석
# =========================================================

elif page == "AI 분석":

    st.markdown(
        '<div class="section-title">🔎 쇼핑 화면 AI 분석</div>',
        unsafe_allow_html=True
    )

    st.write(
        "결제하기 전 마음에 걸리는 쇼핑 화면을 캡처해서 올려주세요."
    )

    uploaded_file = st.file_uploader(
        "쇼핑 화면 업로드",
        type=["png", "jpg", "jpeg"]
    )

    if uploaded_file is not None:

        image = Image.open(uploaded_file)

        st.image(
            image,
            caption="분석할 쇼핑 화면",
            use_container_width=True
        )

        if st.button(
            "🔎 체키로 분석하기",
            type="primary",
            use_container_width=True
        ):

            try:

                client = genai.Client(
                    api_key=st.secrets["GEMINI_API_KEY"]
                )

                prompt = """
너는 AI 소비자 보호 서비스 '체키(CHECKI)'의 분석 AI다.

사용자가 업로드한 온라인 쇼핑 화면을 분석하여
충동구매나 원하지 않는 소비를 유도할 수 있는 요소를 찾아라.

중점적으로 확인할 요소:

- 반복적이거나 과도한 시간 제한
- 재고 부족 및 품절 임박 강조
- 다른 소비자의 조회·구매 행동을 이용한 압박
- 할인율 및 가격의 과도한 강조
- 추가 상품 또는 옵션의 사전 선택
- 구독 및 자동결제 정보의 불명확한 표시
- 구매 또는 동의 버튼의 과도한 시각적 강조
- 소비자의 판단을 재촉하는 문구
- 취소나 거절을 어렵게 만드는 화면 구성

화면에서 실제로 확인되는 내용만 분석한다.
확인되지 않은 내용을 추측하지 않는다.
정상적인 할인이나 마케팅을 무조건 다크패턴으로 판단하지 않는다.

반드시 아래 형식으로 한국어로 답변한다.

## 🚦 위험도

낮음 🟢 / 주의 🟡 / 높음 🔴 중 하나와
0~100점 사이의 소비 유도 위험 점수를 표시한다.

예시:
**높음 🔴 · 87점 / 100점**

## 💬 체키 한줄 진단

가장 중요한 내용을 소비자가 바로 이해할 수 있도록
한 문장으로 설명한다.

## ⚠️ 탐지된 소비 유도 요소

발견된 요소마다 아래 세 항목을 작성한다.

**유형:** 소비 유도 방식
**화면 근거:** 실제 화면에서 확인되는 내용
**영향:** 소비자 판단에 미칠 수 있는 영향

## 🛡️ 결제 전 CHECK!

결제 전에 다시 확인하면 좋은 행동을
최대 3개 제시한다.

뚜렷한 문제가 없다면
'뚜렷한 다크패턴이 확인되지 않습니다.'라고 알려라.
"""

                response = None
                last_error = None

                for attempt in range(3):

                    try:

                        if attempt == 0:
                            message = "체키가 화면을 분석하고 있어요..."
                        else:
                            message = (
                                f"AI 서버가 혼잡해 자동으로 다시 분석하고 있어요... "
                                f"({attempt + 1}/3)"
                            )

                        with st.spinner(message):

                            response = client.models.generate_content(
                                model="gemini-3.8-flash",
                                contents=[prompt, image]
                            )

                        break

                    except Exception as e:

                        last_error = e

                        if "503" in str(e) or "UNAVAILABLE" in str(e):

                            if attempt < 2:
                                time.sleep(2 * (attempt + 1))

                            continue

                        raise e

                if response is not None:

                    st.session_state.analysis_count += 1

                    st.success("체키 분석이 완료되었습니다! ✅")

                    st.markdown(response.text)

                    st.markdown("""
                    <div class="stop-card">
                        <b>🛑 지금 바로 결제하려고 하셨나요?</b><br><br>
                        분석 결과가 마음에 걸린다면,
                        바로 구매하지 않고 잠시 생각할 시간을 가져보세요.
                    </div>
                    """, unsafe_allow_html=True)

                    st.caption(
                        "※ 체키 분석은 AI 기반 참고 정보이며 "
                        "법률상 다크패턴 여부를 확정하는 판단은 아닙니다."
                    )

                else:

                    st.error(
                        "현재 AI 요청이 많이 몰리고 있어요. "
                        "잠시 후 다시 시도해주세요."
                    )

                    if last_error:
                        with st.expander("오류 정보"):
                            st.caption(str(last_error))

            except Exception as e:

                st.error("분석 중 오류가 발생했습니다.")

                with st.expander("오류 정보"):
                    st.caption(str(e))

# =========================================================
# 결제 멈추기
# =========================================================

elif page == "결제 멈추기":

    st.markdown(
        '<div class="section-title">⏸️ 결제 멈추기</div>',
        unsafe_allow_html=True
    )

    st.write(
        "사고 싶은 상품을 바로 결제하지 말고 "
        "체키에 잠시 맡겨보세요."
    )

    if st.session_state.hold_until is None:

        product = st.text_input(
            "사고 싶은 상품",
            placeholder="예: 운동화"
        )

        price = st.number_input(
            "가격",
            min_value=0,
            step=1000,
            format="%d"
        )

        reason = st.text_area(
            "왜 지금 사고 싶나요?",
            placeholder="예: 오늘까지만 50% 할인이라서"
        )

        st.markdown("""
        <div class="notice">
            💡 <b>체키 질문</b><br>
            할인하지 않았어도 이 상품을 지금 구매했을까요?
        </div>
        """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "⏱️ 30분 멈추기",
                use_container_width=True
            ):

                if not product:
                    st.warning("상품 이름을 입력해주세요.")

                else:

                    st.session_state.hold_product = product
                    st.session_state.hold_price = int(price)
                    st.session_state.purchase_reason = reason

                    st.session_state.hold_until = (
                        datetime.now() + timedelta(minutes=30)
                    )

                    st.rerun()

        with c2:

            if st.button(
                "🌙 24시간 고민하기",
                type="primary",
                use_container_width=True
            ):

                if not product:
                    st.warning("상품 이름을 입력해주세요.")

                else:

                    st.session_state.hold_product = product
                    st.session_state.hold_price = int(price)
                    st.session_state.purchase_reason = reason

                    st.session_state.hold_until = (
                        datetime.now() + timedelta(hours=24)
                    )

                    st.rerun()

    else:

        remaining = (
            st.session_state.hold_until - datetime.now()
        )

        seconds = max(0, int(remaining.total_seconds()))

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        st.markdown(f"""
        <div class="stop-card">
            <div class="card-title">
                🔒 {st.session_state.hold_product}
            </div>

            <div class="card-text">
                {st.session_state.hold_price:,}원
            </div>

            <div class="timer">
                {hours:02d}:{minutes:02d}:{secs:02d}
            </div>

            <div class="card-text" style="text-align:center;">
                구매 보류 중
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.purchase_reason:

            st.info(
                "처음 사고 싶었던 이유: "
                + st.session_state.purchase_reason
            )

        st.markdown("""
        <div class="notice">
            🤔 <b>다시 생각해볼까요?</b><br><br>
            • 이 상품이 오늘 꼭 필요한가요?<br>
            • 할인하지 않았어도 구매했을까요?<br>
            • 비슷한 물건을 이미 가지고 있지는 않나요?
        </div>
        """, unsafe_allow_html=True)

        if seconds > 0:

            st.caption(
                "💡 화면을 새로고침하면 남은 시간이 갱신됩니다."
            )

        else:

            st.success(
                "고민 시간이 끝났어요. "
                "이제 다시 구매 여부를 결정해보세요."
            )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "🙅 구매하지 않을래요",
                type="primary",
                use_container_width=True
            ):

                st.session_state.stop_count += 1
                st.session_state.saved_money += (
                    st.session_state.hold_price
                )

                st.session_state.hold_until = None
                st.session_state.hold_product = ""
                st.session_state.hold_price = 0
                st.session_state.purchase_reason = ""

                st.success(
                    "좋아요! 이번 소비는 다시 생각해보기로 했어요."
                )

                st.rerun()

        with c2:

            if st.button(
                "구매할래요",
                use_container_width=True
            ):

                st.session_state.hold_until = None
                st.session_state.hold_product = ""
                st.session_state.hold_price = 0
                st.session_state.purchase_reason = ""

                st.rerun()

# =========================================================
# 리포트
# =========================================================

elif page == "리포트":

    st.markdown(
        '<div class="section-title">📊 나의 소비 방어 리포트</div>',
        unsafe_allow_html=True
    )

    st.write(
        "체키와 함께 한 소비 판단을 확인해보세요."
    )

    c1, c2 = st.columns(2)

    with c1:

        st.metric(
            "🔎 AI 분석 횟수",
            f"{st.session_state.analysis_count}회"
        )

    with c2:

        st.metric(
            "🙅 구매 포기",
            f"{st.session_state.stop_count}회"
        )

    st.metric(
        "💰 방어한 소비 금액",
        f"{st.session_state.saved_money:,}원"
    )

    if st.session_state.stop_count > 0:

        st.markdown(f"""
        <div class="safe-box">
            <b>🛡️ CHECKI가 만든 변화</b><br><br>
            지금까지 {st.session_state.stop_count}번의 구매를
            다시 생각했고,
            총 <b>{st.session_state.saved_money:,}원</b>의
            소비를 멈췄어요.
        </div>
        """, unsafe_allow_html=True)

    else:

        st.markdown("""
        <div class="safe-box">
            아직 기록이 없어요.<br>
            쇼핑 중 고민되는 순간 체키를 사용해보세요.
        </div>
        """, unsafe_allow_html=True)

# =========================================================
# 하단
# =========================================================

st.markdown("<br><br>", unsafe_allow_html=True)

st.caption(
    "CHECKI · AI 기반 소비자 보호 서비스 MVP"
)
