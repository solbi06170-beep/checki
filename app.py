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
    "체키가 다크패턴과 소비 유도 요소를 분석해드립니다."
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

    if st.button("🔎 체키로 분석하기", type="primary"):

        try:
            with st.spinner("체키가 화면을 분석하고 있어요..."):

                client = genai.Client(
                    api_key=st.secrets["GEMINI_API_KEY"]
                )

                prompt = """
너는 온라인 소비자의 합리적인 소비를 돕는 AI 서비스
'체키(CHECKI)'의 분석 AI다.

사용자가 업로드한 쇼핑 화면을 보고
충동구매나 원하지 않는 소비를 유도할 가능성이 있는
다크패턴 및 소비 유도 요소를 분석하라.

특히 다음과 같은 요소를 살펴본다.

- 허위 또는 과장된 시간 제한
- 재고 부족이나 품절 임박 강조
- 다른 소비자의 구매 행동을 이용한 압박
- 할인율이나 가격을 과도하게 강조하는 방식
- 추가 상품이나 옵션의 사전 선택
- 구독이나 자동결제 관련 정보의 불명확한 표시
- 취소·거절보다 구매·동의 버튼을 지나치게 강조하는 방식
- 소비자의 판단을 재촉하는 문구 또는 화면 구성

단, 화면에서 확인되지 않는 내용을 추측해서는 안 된다.
일반적인 할인이나 정상적인 마케팅 표현을 무조건
다크패턴이라고 판단해서도 안 된다.

다음 형식으로 한국어로 답변하라.

### 🔎 체키 분석 결과
위험도: 낮음 / 주의 / 높음 중 하나

전체적인 분석 결과를 간단히 설명한다.

### ⚠️ 발견된 의심 요소
실제 화면에서 발견한 요소와 해당 문구를 설명한다.
발견되지 않았다면 그렇다고 명확하게 말한다.

### 🧠 왜 주의해야 하나요?
해당 요소가 소비자의 구매 판단에 어떤 영향을
줄 가능성이 있는지 쉽게 설명한다.

### ✅ 결제 전 체크
사용자가 결제하기 전에 다시 확인할 사항을
2~4개 제시한다.

뚜렷한 문제가 없다면 억지로 문제를 만들지 말고
'뚜렷한 다크패턴이 확인되지 않습니다.'라고 알려라.
"""

                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[prompt, image]
                )

            st.success("분석이 완료되었습니다!")
            st.markdown(response.text)

        except Exception as e:
            st.error("분석 중 오류가 발생했습니다.")
            st.error(str(e))
