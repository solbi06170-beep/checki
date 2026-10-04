import streamlit as st

st.set_page_config(
    page_title="체키 | CHECKY",
    page_icon="🔍"
)

st.title("🔍 체키 CHECKY")

st.write("충동적인 소비 전에, 체키하세요.")

st.divider()

st.subheader("🛍️ 쇼핑 화면 분석")

st.write(
    "쇼핑 중 의심되는 화면을 캡처해서 올려주세요. "
    "체키가 다크패턴을 분석해드립니다."
)

uploaded_file = st.file_uploader(
    "쇼핑 화면 업로드",
    type=["png", "jpg", "jpeg"]
)

if uploaded_file is not None:
    st.image(
        uploaded_file,
        caption="업로드한 쇼핑 화면",
        use_container_width=True
    )

    st.success("이미지가 정상적으로 업로드되었습니다!")

    st.button("🔍 체키 AI로 분석하기")
