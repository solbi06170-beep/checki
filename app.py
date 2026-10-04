import streamlit as st
from google import genai
from PIL import Image
from datetime import datetime, timedelta, timezone
from supabase import create_client
import time
import re


# ============================================================
# 기본 설정
# ============================================================

st.set_page_config(
    page_title="체키 | CHECKI",
    page_icon="🔵",
    layout="centered",
    initial_sidebar_state="collapsed"
)


# ============================================================
# Supabase 연결
# ============================================================

@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )


supabase = get_supabase()
USER_ID = "demo_user"


# ============================================================
# 시간 처리
# ============================================================

def now_utc():
    return datetime.now(timezone.utc)


def parse_db_time(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except:
        return None


# ============================================================
# DB 함수
# ============================================================

def get_records():
    try:
        response = (
            supabase.table("checki_records")
            .select("*")
            .eq("user_id", USER_ID)
            .order("created_at", desc=True)
            .execute()
        )

        return response.data or []

    except Exception:
        return []


def save_analysis(product, price, result):

    try:
        data = {
            "user_id": USER_ID,
            "product_name": product,
            "product_price": int(price),
            "risk_level": result["risk"],
            "risk_score": int(result["score"]),
            "one_line_summary": result["summary"],
            "detected_elements": result["types"],
            "ai_result": result["evidence"],
            "decision": "analyzed",
            "saved_amount": 0
        }

        response = (
            supabase.table("checki_records")
            .insert(data)
            .execute()
        )

        if response.data:
            return response.data[0]["id"]

    except Exception as e:
        st.warning(
            "분석은 완료됐지만 기록 저장에 문제가 생겼어요."
        )
        with st.expander("저장 오류"):
            st.caption(str(e))

    return None


def save_hold(record_id):

    if not record_id:
        return False

    try:
        start = now_utc()
        end = start + timedelta(minutes=30)

        (
            supabase.table("checki_records")
            .update({
                "decision": "hold",
                "hold_started_at": start.isoformat(),
                "hold_until": end.isoformat()
            })
            .eq("id", record_id)
            .execute()
        )

        return True

    except Exception:
        return False


def save_stopped(record_id, price):

    if not record_id:
        return False

    try:
        (
            supabase.table("checki_records")
            .update({
                "decision": "stopped",
                "saved_amount": int(price),
                "decided_at": now_utc().isoformat(),
                "hold_until": None
            })
            .eq("id", record_id)
            .execute()
        )

        return True

    except Exception:
        return False


def save_continue(record_id):

    if not record_id:
        return False

    try:
        (
            supabase.table("checki_records")
            .update({
                "decision": "continued",
                "decided_at": now_utc().isoformat(),
                "hold_until": None
            })
            .eq("id", record_id)
            .execute()
        )

        return True

    except Exception:
        return False


def get_active_hold():

    records = get_records()
    current = now_utc()

    for record in records:

        if record.get("decision") != "hold":
            continue

        hold_until = parse_db_time(
            record.get("hold_until")
        )

        if hold_until and hold_until > current:
            return record

    return None


def get_stats():

    records = get_records()

    analysis_count = len(records)

    stopped_records = [
        r for r in records
        if r.get("decision") == "stopped"
    ]

    stopped_count = len(stopped_records)

    saved_money = sum(
        int(r.get("saved_amount") or 0)
        for r in stopped_records
    )

    return (
        analysis_count,
        stopped_count,
        saved_money
    )


# ============================================================
# 상태값
# ============================================================

DEFAULTS = {
    "result": None,
    "result_product": "",
    "result_price": 0,
    "current_record_id": None,
}

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ============================================================
# DB 통계 불러오기
# ============================================================

analysis_count, stopped_count, saved_money = get_stats()


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

#MainMenu {
    visibility:hidden;
}

footer {
    visibility:hidden;
}

header {
    background:transparent;
}

.stApp {
    background:
        radial-gradient(
            circle at 90% 5%,
            #eaf4ff 0,
            transparent 26%
        ),
        #f8fbff;
}

.block-container {
    width:100%;
    max-width:820px;
    padding-top:24px;
    padding-left:24px;
    padding-right:24px;
    padding-bottom:90px;
}

@media (max-width:700px) {

    .block-container {
        padding-left:16px;
        padding-right:16px;
        padding-top:18px;
    }

    .hero {
        padding:24px 20px !important;
    }

    .hero-title {
        font-size:27px !important;
    }

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

div.stButton > button {
    width:100%;
    min-height:52px;
    border-radius:15px;
    font-weight:800;
    border:1px solid #dce8f6;
}

div.stButton > button[kind="primary"] {
    background:
        linear-gradient(
            135deg,
            #1685ff,
            #2875ef
        );
    color:white;
    border:none;
}

div[data-testid="stFileUploader"] {
    background:white;
    border:1px solid #e2ebf6;
    padding:12px;
    border-radius:20px;
}

div[data-testid="stMetric"] {
    background:white;
    border:1px solid #e4edf7;
    border-radius:18px;
    padding:15px;
}

div[data-testid="stRadio"] > div {
    background:white;
    border:1px solid #e2eaf4;
    border-radius:18px;
    padding:5px;
}

.logo {
    font-size:30px;
    font-weight:900;
    color:#1683ff;
    letter-spacing:-2px;
}

.logo-sub {
    font-size:10px;
    color:#96a2b1;
    letter-spacing:1px;
}

.hero {
    padding:30px 26px;
    background:
        linear-gradient(
            135deg,
            #edf6ff,
            #ffffff 55%,
            #f3efff
        );
    border:1px solid #e1ebf6;
    border-radius:28px;
    box-shadow:
        0 12px 35px rgba(50,100,160,.07);
    margin:22px 0;
    overflow:hidden;
}

.hero-badge {
    display:inline-block;
    padding:7px 12px;
    background:#deefff;
    color:#1683ff;
    border-radius:30px;
    font-size:12px;
    font-weight:800;
}

.hero-title {
    margin-top:14px;
    font-size:30px;
    line-height:1.3;
    font-weight:900;
    letter-spacing:-1.5px;
    color:#102f5d;
}

.hero-desc {
    margin-top:12px;
    color:#6e7f93;
    line-height:1.7;
    font-size:14px;
}

.section {
    font-size:21px;
    font-weight:900;
    color:#112f59;
    margin:28px 0 12px 0;
    letter-spacing:-.7px;
}

.card {
    background:white;
    border:1px solid #e5edf7;
    border-radius:22px;
    padding:20px;
    margin:11px 0;
    box-shadow:
        0 7px 25px rgba(30,80,140,.05);
    overflow:hidden;
}

.card-blue {
    background:
        linear-gradient(
            135deg,
            #edf7ff,
            #f9fcff
        );
    border:1px solid #d9eaff;
    border-radius:22px;
    padding:20px;
    margin:11px 0;
    overflow:hidden;
}

.card-red {
    background:
        linear-gradient(
            135deg,
            #fff0f0,
            #fff8f8
        );
    border:1px solid #ffdada;
    border-radius:22px;
    padding:20px;
    margin:11px 0;
    overflow:hidden;
}

.card-purple {
    background:
        linear-gradient(
            135deg,
            #f5f0ff,
            #fcfaff
        );
    border:1px solid #e9dfff;
    border-radius:22px;
    padding:20px;
    margin:11px 0;
    overflow:hidden;
}

.card-green {
    background:
        linear-gradient(
            135deg,
            #ecfbf4,
            #f8fffb
        );
    border:1px solid #d4f0e2;
    border-radius:22px;
    padding:20px;
    margin:11px 0;
    overflow:hidden;
}

.card-title {
    color:#16365f;
    font-size:17px;
    font-weight:900;
    word-break:keep-all;
}

.card-text {
    margin-top:7px;
    color:#718095;
    font-size:14px;
    line-height:1.65;
    word-break:keep-all;
    overflow-wrap:anywhere;
}

.danger-title {
    color:#e24e4e;
    font-size:17px;
    font-weight:900;
}

.tag {
    display:inline-block;
    padding:5px 10px;
    background:#ffe0e0;
    color:#df5050;
    border-radius:20px;
    font-size:12px;
    font-weight:800;
    margin-top:10px;
}

.result-title {
    font-size:28px;
    font-weight:900;
    color:#102e59;
    text-align:center;
    margin:30px 0 6px 0;
}

.result-sub {
    color:#7d8b9d;
    font-size:14px;
    text-align:center;
    margin-bottom:20px;
}

.score {
    font-size:39px;
    color:#e74f4f;
    font-weight:900;
    margin-top:5px;
}

.stat {
    background:white;
    border:1px solid #e4edf7;
    border-radius:19px;
    padding:18px 5px;
    text-align:center;
    min-height:90px;
}

.stat-value {
    color:#1683ff;
    font-size:23px;
    font-weight:900;
}

.stat-label {
    color:#8a98aa;
    font-size:11px;
    margin-top:5px;
}

.progress-bg {
    height:9px;
    background:#e6eff9;
    border-radius:20px;
    margin-top:10px;
    overflow:hidden;
}

.progress-fill {
    height:100%;
    background:#2188ff;
    border-radius:20px;
}

.timer {
    text-align:center;
    color:#1683ff;
    font-size:42px;
    font-weight:900;
    padding:15px 0;
}

.footer {
    text-align:center;
    color:#a3adba;
    font-size:10px;
    margin-top:55px;
    line-height:1.7;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# HTML helper
# ============================================================

def html(content):
    clean = re.sub(r"\n\s*", "", content)
    st.markdown(
        clean,
        unsafe_allow_html=True
    )


# ============================================================
# 상단 로고
# ============================================================

html("""
<div style="
display:flex;
justify-content:space-between;
align-items:center;
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
# 메뉴
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
# 홈
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
            내 소비상황과 비교해 지금 필요한 소비인지
            한 번 더 생각할 수 있도록 도와드려요.
        </div>
    </div>
    """)

    html(
        '<div class="section">'
        '이번 달 나의 체키'
        '</div>'
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        html(
            f'<div class="stat">'
            f'<div class="stat-value">'
            f'{analysis_count}'
            f'</div>'
            f'<div class="stat-label">'
            f'구매 체크'
            f'</div>'
            f'</div>'
        )

    with c2:
        html(
            f'<div class="stat">'
            f'<div class="stat-value">'
            f'{stopped_count}'
            f'</div>'
            f'<div class="stat-label">'
            f'구매 포기'
            f'</div>'
            f'</div>'
        )

    with c3:
        html(
            f'<div class="stat">'
            f'<div class="stat-value">'
            f'{saved_money:,}'
            f'</div>'
            f'<div class="stat-label">'
            f'방어 금액(원)'
            f'</div>'
            f'</div>'
        )

    html(
        '<div class="section">'
        '체키는 이렇게 도와드려요'
        '</div>'
    )

    html("""
    <div class="card">
        <div class="card-title">
            🔎 구매 유도 요소 확인
        </div>
        <div class="card-text">
            타이머, 재고 부족, 과도한 할인 강조처럼
            구매를 서두르게 만드는 요소를
            AI가 확인해요.
        </div>
    </div>
    """)

    html("""
    <div class="card-blue">
        <div class="card-title">
            📊 내 소비상황과 비교
        </div>
        <div class="card-text">
            이번 달 예산과 최근 구매내역을 함께 살펴보고
            현재 소비상황을 확인해요.
        </div>
    </div>
    """)

    html("""
    <div class="card-purple">
        <div class="card-title">
            ⏸ 잠시 보류하기
        </div>
        <div class="card-text">
            바로 결제하지 않고 잠시 구매를 보류해
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
        type=["png", "jpg", "jpeg"]
    )

    product = st.text_input(
        "상품명",
        placeholder="예: Balance 러닝화"
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
            width="stretch"
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
너는 AI 소비자 보호 서비스 '체키(CHECKI)'다.

사용자가 업로드한 온라인 쇼핑 화면을 분석하라.

목표는 구매를 무조건 막는 것이 아니라
소비자의 구매 결정을 서두르게 만들 수 있는 요소를
객관적으로 알려주는 것이다.

확인할 항목:

- 긴급성: 오늘만, 곧 종료, 카운트다운
- 희소성: 재고 부족, 몇 개 남음, 품절 임박
- 사회적 압박: 몇 명이 보는 중, 판매량 강조
- 가격 프레이밍: 과도한 할인율이나 기준가격 강조
- 사전 선택: 추가 상품 또는 옵션 자동 선택
- 구독/자동결제
- 취소나 거절을 어렵게 만드는 구조
- 구매 버튼의 과도한 시각적 강조
- 기타 소비자의 합리적 판단을 방해할 수 있는 요소

이미지에서 실제로 확인되는 내용만 사용하라.
확실하지 않은 내용은 추측하지 마라.

반드시 아래 형식 그대로 출력하라.

RISK: 낮음 또는 주의 또는 높음
SCORE: 0부터 100 사이 숫자
SUMMARY: 가장 중요한 결과 한 문장
TYPES: 핵심 유형 최대 3개
EVIDENCE: 화면에서 실제 확인한 근거를 짧게 설명
ACTION: 결제 전에 사용자가 확인할 내용을 한 문장으로 설명
"""

                response_text = None
                last_error = None

                models_to_try = [
                    "gemini-2.5-flash",
                    "gemini-2.5-flash-lite"
                ]

                for model_name in models_to_try:

                    for attempt in range(2):

                        try:

                            message.info(
                                "② 구매 유도 요소를 "
                                "확인하고 있어요."
                            )

                            progress.progress(45)

                            response = (
                                client.models
                                .generate_content(
                                    model=model_name,
                                    contents=[
                                        prompt,
                                        image
                                    ]
                                )
                            )

                            response_text = (
                                response.text
                            )

                            if response_text:
                                break

                        except Exception as e:

                            last_error = e

                            if attempt == 0:
                                time.sleep(2)

                    if response_text:
                        break

                if not response_text:
                    raise last_error or Exception(
                        "AI 분석 결과를 받지 못했습니다."
                    )

                message.info(
                    "③ 분석 결과를 정리하고 있어요."
                )

                progress.progress(75)

                def extract(label, default):

                    match = re.search(
                        rf"{label}:\s*(.+)",
                        response_text
                    )

                    return (
                        match.group(1).strip()
                        if match
                        else default
                    )

                risk = extract(
                    "RISK",
                    "주의"
                )

                score_match = re.search(
                    r"SCORE:\s*(\d+)",
                    response_text
                )

                if score_match:
                    score = int(
                        score_match.group(1)
                    )
                else:
                    score = 60

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
                    "구매 화면의 표현을 "
                    "다시 확인해보세요."
                )

                action = extract(
                    "ACTION",
                    "혜택의 실제 종료 조건과 "
                    "최종 결제금액을 확인해보세요."
                )

                result = {
                    "risk": risk,
                    "score": score,
                    "summary": summary,
                    "types": types,
                    "evidence": evidence,
                    "action": action
                }

                result_product = (
                    product.strip()
                    if product.strip()
                    else "구매 예정 상품"
                )

                result_price = int(price)

                record_id = save_analysis(
                    result_product,
                    result_price,
                    result
                )

                st.session_state.result = result

                st.session_state.result_product = (
                    result_product
                )

                st.session_state.result_price = (
                    result_price
                )

                st.session_state.current_record_id = (
                    record_id
                )

                progress.progress(100)

                time.sleep(.2)

                progress.empty()
                message.empty()

                st.success(
                    "체키 분석이 완료됐어요."
                )

            except Exception as e:

                progress.empty()
                message.empty()

                st.error(
                    "지금 AI 요청이 많거나 "
                    "분석에 문제가 생겼어요."
                )

                with st.expander("오류 정보"):
                    st.caption(str(e))


    # --------------------------------------------------------
    # 분석 결과
    # --------------------------------------------------------

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

        html(
            f'<div class="card-red">'
            f'<div class="danger-title">'
            f'⚠️ 구매 유도 요소를 확인했어요'
            f'</div>'
            f'<div class="card-text">'
            f'<b>{r["summary"]}</b>'
            f'</div>'
            f'<div class="tag">'
            f'{r["types"]}'
            f'</div>'
            f'<div class="card-text">'
            f'{r["evidence"]}'
            f'</div>'
            f'</div>'
        )

        html("""
        <div class="card-blue">
            <div class="card-title">
                📊 가격을 확인했어요
            </div>
            <div class="card-text">
                데모에서는 샘플 가격 비교 데이터를
                사용하고 있어요.<br>
                최근 가격과 비교했을 때 큰 가격 차이는
                없는 상품으로 가정하여 분석합니다.
            </div>
        </div>
        """)

        html("""
        <div class="card-purple">
            <div class="card-title">
                💳 나의 소비상황과 비교했어요
            </div>
            <div class="card-text">
                이번 달 의류 예산
                <b>300,000원 중 246,000원</b>을
                사용했어요.<br>
                현재 예산의 <b>82%</b>를 사용한
                상태예요.<br>
                14일 전 비슷한 카테고리 상품을
                구매한 기록이 있어요.
            </div>
        </div>
        """)

        html(
            f'<div class="card">'
            f'<div class="card-title">'
            f'🛡️ 결제 전 CHECK'
            f'</div>'
            f'<div class="card-text">'
            f'{r["action"]}'
            f'</div>'
            f'<div class="card-text">'
            f'소비 유도 위험도 · {r["risk"]}'
            f'</div>'
            f'<div class="score">'
            f'{r["score"]}'
            f'<span style="'
            f'font-size:14px;'
            f'color:#8996a8;">'
            f' / 100'
            f'</span>'
            f'</div>'
            f'</div>'
        )

        html(
            '<div class="section">'
            '구매를 계속할까요?'
            '</div>'
        )

        if st.button(
            "구매 계속하기",
            type="primary",
            width="stretch"
        ):

            save_continue(
                st.session_state.current_record_id
            )

            st.session_state.result = None
            st.session_state.current_record_id = None

            st.success(
                "구매를 계속하기로 했어요. "
                "체키가 확인한 내용을 참고해 "
                "결정해주세요."
            )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "⏸ 30분 보류",
                width="stretch"
            ):

                success = save_hold(
                    st.session_state.current_record_id
                )

                if success:

                    st.session_state.result = None
                    st.session_state.current_record_id = None

                    st.success(
                        "구매를 30분 보류했어요. "
                        "MY에서 확인할 수 있어요."
                    )

                else:

                    st.error(
                        "보류 기록 저장에 실패했어요."
                    )

        with c2:

            if st.button(
                "구매하지 않기",
                width="stretch"
            ):

                p = (
                    st.session_state.result_price
                )

                success = save_stopped(
                    st.session_state.current_record_id,
                    p
                )

                if success:

                    st.session_state.result = None
                    st.session_state.current_record_id = None

                    if p > 0:
                        st.success(
                            f"🎉 {p:,}원의 소비를 "
                            f"다시 생각했어요!"
                        )

                    else:
                        st.success(
                            "🎉 이번 구매를 "
                            "다시 생각하기로 했어요!"
                        )

                    time.sleep(.5)
                    st.rerun()

                else:

                    st.error(
                        "구매 포기 기록 저장에 "
                        "실패했어요."
                    )


# ============================================================
# 소비 분석
# ============================================================

elif page == "소비분석":

    html(
        '<div class="section">'
        '소비분석'
        '</div>'
    )

    st.caption(
        "경진대회 MVP용 샘플 소비 데이터입니다."
    )

    st.radio(
        "기간",
        [
            "이번 달",
            "최근 3개월",
            "전체"
        ],
        horizontal=True,
        label_visibility="collapsed"
    )

    html("""
    <div class="hero">

        <div class="hero-badge">
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
    """)

    html("""
    <div class="card">

        <div class="card-title">
            👕 의류
            <span style="float:right;">
                82%
            </span>
        </div>

        <div class="card-text">
            246,000원 / 300,000원
        </div>

        <div class="progress-bg">
            <div
                class="progress-fill"
                style="width:82%;">
            </div>
        </div>

    </div>
    """)

    html("""
    <div class="card-blue">

        <div class="card-title">
            💡 체키가 발견한 소비 패턴
        </div>

        <div class="card-text">
            이번 달 의류 예산의 82%를 사용했어요.
            최근 비슷한 상품을 구매한 기록도 있어요.
            새로운 의류 구매 전 한 번 더
            확인해보는 것을 추천해요.
        </div>

    </div>
    """)

    html(
        '<div class="section">'
        '카테고리별 지출'
        '</div>'
    )

    categories = [
        ("👕 의류", 246000, 82),
        ("🍴 식비", 180000, 60),
        ("🧴 뷰티", 72000, 36),
        ("🛒 생활용품", 45000, 30)
    ]

    for name, amount, percent in categories:

        html(
            f'<div class="card">'
            f'<div class="card-title">'
            f'{name}'
            f'<span style="float:right;">'
            f'{amount:,}원'
            f'</span>'
            f'</div>'
            f'<div class="progress-bg">'
            f'<div class="progress-fill" '
            f'style="width:{percent}%;">'
            f'</div>'
            f'</div>'
            f'<div class="card-text" '
            f'style="text-align:right;">'
            f'{percent}%'
            f'</div>'
            f'</div>'
        )

    html(
        '<div class="section">'
        '최근 구매한 상품'
        '</div>'
    )

    purchases = [
        ("👟", "운동화", "14일 전", 79000),
        ("👔", "셔츠", "1개월 전", 59000),
        ("🧢", "모자", "1개월 전", 45000)
    ]

    for icon, name, date, amount in purchases:

        html(
            f'<div class="card">'
            f'<div class="card-title">'
            f'{icon} {name}'
            f'<span style="float:right;">'
            f'{amount:,}원'
            f'</span>'
            f'</div>'
            f'<div class="card-text">'
            f'{date}'
            f'</div>'
            f'</div>'
        )


# ============================================================
# MY
# ============================================================

elif page == "MY":

    html(
        '<div class="section">'
        'MY 체키'
        '</div>'
    )

    # 매번 DB에서 최신 통계를 가져옴
    analysis_count, stopped_count, saved_money = (
        get_stats()
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
    # Supabase에서 현재 보류 상품 가져오기
    # --------------------------------------------------------

    active_hold = get_active_hold()

    if active_hold is not None:

        hold_until = parse_db_time(
            active_hold.get("hold_until")
        )

        remaining = (
            hold_until - now_utc()
        )

        seconds = max(
            0,
            int(remaining.total_seconds())
        )

        hours = seconds // 3600
        minutes = (
            seconds % 3600
        ) // 60
        secs = seconds % 60

        product_name = (
            active_hold.get("product_name")
            or "구매 예정 상품"
        )

        product_price = int(
            active_hold.get("product_price")
            or 0
        )

        html(
            '<div class="section">'
            '구매 보류 중'
            '</div>'
        )

        html(
            f'<div class="card-blue">'
            f'<div class="card-title">'
            f'🔒 {product_name}'
            f'</div>'
            f'<div class="card-text">'
            f'{product_price:,}원'
            f'</div>'
            f'<div class="timer">'
            f'{hours:02d}:'
            f'{minutes:02d}:'
            f'{secs:02d}'
            f'</div>'
            f'<div class="card-text" '
            f'style="text-align:center;">'
            f'남은 고민 시간'
            f'</div>'
            f'</div>'
        )

        st.caption(
            "새로고침해도 보류 기록은 "
            "사라지지 않아요."
        )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "구매하지 않기",
                type="primary",
                width="stretch",
                key="hold_stop"
            ):

                success = save_stopped(
                    active_hold["id"],
                    product_price
                )

                if success:

                    st.success(
                        f"🎉 {product_price:,}원의 "
                        f"소비를 다시 생각했어요!"
                    )

                    time.sleep(.5)
                    st.rerun()

                else:

                    st.error(
                        "기록 저장에 실패했어요."
                    )

        with c2:

            if st.button(
                "구매 계속하기",
                width="stretch",
                key="hold_continue"
            ):

                success = save_continue(
                    active_hold["id"]
                )

                if success:

                    st.success(
                        "보류를 종료했어요."
                    )

                    time.sleep(.5)
                    st.rerun()

                else:

                    st.error(
                        "기록 저장에 실패했어요."
                    )

    else:

        html("""
        <div class="card-blue">

            <div class="card-title">
                ⏸ 현재 보류 중인 구매가 없어요
            </div>

            <div class="card-text">
                고민되는 상품은 구매체크에서
                잠시 보류할 수 있어요.
            </div>

        </div>
        """)


    # --------------------------------------------------------
    # 체키 효과
    # --------------------------------------------------------

    if stopped_count > 0:

        html(
            f'<div class="card-green">'
            f'<div class="card-title">'
            f'🎉 체키 효과'
            f'</div>'
            f'<div class="card-text">'
            f'지금까지 '
            f'<b>{stopped_count}번</b>의 '
            f'구매를 다시 생각했고, '
            f'<b>{saved_money:,}원</b>의 '
            f'소비를 재검토했어요.'
            f'</div>'
            f'</div>'
        )


    # --------------------------------------------------------
    # 최근 체키 기록
    # --------------------------------------------------------

    records = get_records()

    if records:

        html(
            '<div class="section">'
            '최근 체키 기록'
            '</div>'
        )

        decision_names = {
            "analyzed": "분석 완료",
            "hold": "30분 보류",
            "stopped": "구매 포기",
            "continued": "구매 계속"
        }

        for record in records[:5]:

            name = (
                record.get("product_name")
                or "구매 예정 상품"
            )

            amount = int(
                record.get("product_price")
                or 0
            )

            risk = (
                record.get("risk_level")
                or "-"
            )

            decision = decision_names.get(
                record.get("decision"),
                "분석 완료"
            )

            html(
                f'<div class="card">'
                f'<div class="card-title">'
                f'🧾 {name}'
                f'<span style="float:right;">'
                f'{amount:,}원'
                f'</span>'
                f'</div>'
                f'<div class="card-text">'
                f'위험도 {risk} · {decision}'
                f'</div>'
                f'</div>'
            )


# ============================================================
# Footer
# ============================================================

html("""
<div class="footer">
    CHECKI · AI 소비자 보호 서비스 MVP<br>
    AI 분석 결과는 소비자의 판단을 돕기 위한
    참고 정보입니다.<br>
    가격 비교 및 개인 소비 데이터는
    현재 MVP용 샘플 데이터입니다.
</div>
""")
