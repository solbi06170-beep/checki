import streamlit as st
from google import genai
from PIL import Image

st.set_page_config(
    page_title="체키 | CHECKI",
    page_icon="🔎",
    layout="centered"
)

st.title("🔎 체키 CHECKI")
st.write("충동적인 소비 전에, 체키하세요.")

st.divider()

st.header("🛍️ 쇼핑 화면 분석")
st.write(
    "쇼핑 중 의심되는 화면을 캡처해서 올려주세요. "
    "체키가 AI로 소비를 유도하는 요소를 분석합니다."
)

uploaded_file = st.file_uploader(
    "쇼핑 화면 업로드",
    type=["png", "jpg", "jpeg"]
)

if uploaded_file is not None:

    image = Image.open(uploaded_file)

    st.image(
        image,
        caption="업로드한 쇼핑 화면",
        use_container_width=True
    )

    if st.button(
        "🔎 체키로 분석하기",
        type="primary",
        use_container_width=True
    ):

        try:
            with st.spinner("체키가 쇼핑 화면을 분석하고 있어요..."):

                client = genai.Client(
                    api_key=st.secrets["GEMINI_API_KEY"]
                )

                prompt = """
너는 온라인 소비자의 합리적인 소비를 돕는
AI 소비자 보호 서비스 '체키(CHECKI)'의 분석 AI다.

사용자가 업로드한 쇼핑 화면을 분석하라.

다음 요소를 중점적으로 확인한다.

- 허위 또는 반복적인 시간 제한
- 재고 부족 및 품절 임박 강조
- 다른 소비자의 구매·조회 행동을 이용한 압박
- 할인율이나 가격의 과도한 강조
- 추가 상품 또는 옵션의 사전 선택
- 구독 및 자동결제 정보의 불명확한 표시
- 구매·동의 버튼만 과도하게 강조하는 인터페이스
- 소비자의 판단을 재촉하는 문구
- 취소나 거절을 어렵게 만드는 화면 구성

중요한 원칙:
화면에서 실제로 확인되는 내용만 분석한다.
확인되지 않은 내용을 추측하지 않는다.
일반적인 할인이나 정상적인 마케팅을 무조건
다크패턴으로 판단하지 않는다.

반드시 아래 형식으로 한국어로 답변하라.

## 🚦 위험도
'낮음 🟢 / 주의 🟡 / 높음 🔴' 중 하나를 표시한다.

그리고 0점부터 100점 사이의
'소비 유도 위험 점수'를 함께 표시한다.

예:
**높음 🔴 · 87점 / 100점**

## 💬 체키 한줄 진단
이 화면에서 가장 중요한 문제를
소비자가 바로 이해할 수 있도록 한 문장으로 설명한다.

## ⚠️ 탐지된 소비 유도 요소
발견한 요소를 번호로 구분한다.

각 요소마다 반드시 다음 내용을 포함한다.

**유형:** 소비 유도 방식의 이름
**화면 근거:** 실제 화면에서 발견한 문구 또는 구성
**영향:** 소비자의 판단에 어떤 영향을 줄 수 있는지

## 🛡️ 결제 전 CHECK!
사용자가 결제하기 전에 실제로 확인하면 좋은 행동을
3개 이내로 짧고 구체적으로 제시한다.

뚜렷한 문제가 없다면 억지로 문제를 만들지 말고
'뚜렷한 다크패턴이 확인되지 않습니다.'라고 알려라.
위험 점수 역시 낮게 평가하라.
"""

                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=[prompt, image]
                )

            st.success("체키 분석이 완료되었습니다! ✅")

            st.divider()

            st.markdown(response.text)

            st.divider()

            st.caption(
                "※ 체키의 분석은 AI 기반 참고 정보이며, "
                "법률상 다크패턴 여부를 확정하는 판단은 아닙니다."
            )

        except Exception as e:
            st.error("잠시 분석 요청이 몰리고 있어요.")
            st.info("잠시 후 🔎 체키로 분석하기 버튼을 다시 눌러주세요.")
            st.caption(str(e))
