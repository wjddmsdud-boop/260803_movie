import datetime
import requests
import pandas as pd
import plotly.express as px
import streamlit as st

# 페이지 기본 설정 (제목, 레이아웃)
st.set_page_config(page_title="어제 박스오피스", layout="wide")

st.title("🎬 어제의 박스오피스")


# 1. secrets에서 KOBIS API 키 불러오기
# 스트림릿 클라우드의 Secrets 설정에서 KOBIS_KEY="내_API_키" 형태로 등록해야 합니다.
if "KOBIS_KEY" not in st.secrets:
    st.error(
        "Secrets에서 `KOBIS_KEY`를 찾을 수 없습니다.\n\n"
        "**해결 방법:**\n"
        "1. Streamlit Cloud 설정의 'Secrets' 메뉴를 엽니다.\n"
        '2. `KOBIS_KEY = "발급받은_키"` 형식으로 입력 후 저장해 주세요.'
    )
    st.stop()

api_key = st.secrets["KOBIS_KEY"]


# 2. 한국 표준시(UTC+9) 기준으로 '어제' 날짜 계산하기
# 배포 서버의 시계(UTC)에 영향을 받지 않도록 한국 시간대를 직접 계산합니다.
korea_tz = datetime.timezone(datetime.timedelta(hours=9))
today_korea = datetime.datetime.now(korea_tz).date()
yesterday_korea = today_korea - datetime.timedelta(days=1)

# API 요청용 날짜 형식 (YYYYMMDD) 및 화면 표시용 날짜 형식 (YYYY-MM-DD)
target_dt = yesterday_korea.strftime("%Y%m%d")
display_dt = yesterday_korea.strftime("%Y-%m-%d")

st.caption(f" 기준 날짜: **{display_dt}** (한국 시간 기준 어제)")


# 3. KOBIS Open API 데이터 요청
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {"key": api_key, "targetDt": target_dt}

try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()  # 네트워크 에러(4xx, 5xx) 체크
    data = response.json()
except Exception as e:
    st.error(
        "API 서버와 통신하는 중 에러가 발생했습니다.\n\n"
        f"- **오류 내용**: {e}\n"
        "- **확인할 사항**: 네트워크 상태를 확인하거나 잠시 후 다시 시도해 주세요."
    )
    st.stop()


# 4. API 예외 처리 (인증키 오류, 빈 데이터 등)
# KOBIS API는 키가 틀려도 HTTP 200 응답과 함께 'faultInfo'를 반환합니다.
if "faultInfo" in data:
    fault_msg = data["faultInfo"].get("message", "알 수 없는 에러")
    st.error(
        "KOBIS API 호출 오류가 발생했습니다.\n\n"
        f"- **메시지**: {fault_msg}\n"
        "- **확인할 사항**: Secrets에 입력한 `KOBIS_KEY` 값이 정확한지 확인해 주세요."
    )
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
movie_list = box_office_result.get("dailyBoxOfficeList", [])

if not movie_list:
    st.warning(
        "해당 날짜의 박스오피스 데이터가 없습니다.\n\n"
        "- **확인할 사항**: 아직 집계가 완료되지 않았거나, KOBIS 서비스에 일시적 데이터가 없을 수 있습니다."
    )
    st.stop()


# 5. 데이터 가공 (데이터프레임 생성 및 숫자형 변환)
df = pd.DataFrame(movie_list)

# 숫자가 문자열로 전달되므로 정수(int) 타입으로 변환합니다.
numeric_cols = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)


# 6. 1위 영화 상단 지표 카드 (Metric)
top_1 = df.iloc[0]

st.subheader("🏆 어제 박스오피스 1위")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="영화명", value=top_1["movieNm"])
with col2:
    st.metric(label="어제 관객수", value=f"{top_1['audiCnt']:,} 명")
with col3:
    st.metric(label="누적 관객수", value=f"{top_1['audiAcc']:,} 명")

st.divider()


# 7. 관객수 상위 5편 막대그래프
st.subheader("📊 관객수 상위 5개 영화")

# 상위 5개 영화 추출
top5_df = df.head(5).copy()

# 막대그래프 생성 (Plotly 사용)
fig = px.bar(
    top5_df,
    x="movieNm",
    y="audiCnt",
    text="audiCnt",
    labels={"movieNm": "영화명", "audiCnt": "관객수"},
)

# 그래프 레이아웃 깔끔하게 변경
fig.update_traces(texttemplate="%{text:,}명", textposition="outside")
fig.update_layout(xaxis_title="", yaxis_title="관객수(명)", showlegend=False)

st.plotly_chart(fig, use_container_width=True)

st.divider()


# 8. 박스오피스 순위 전체 표 출력
st.subheader("📋 전체 순위 표")

# 화면에 표시할 컬럼 정리 및 이름 변경
display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

# 천 단위 쉼표(,) 포맷팅을 적용하여 표 출력
st.dataframe(
    display_df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "순위": st.column_config.NumberColumn(format="%d위"),
        "관객수": st.column_config.NumberColumn(format="%d명"),
        "누적관객": st.column_config.NumberColumn(format="%d명"),
        "스크린수": st.column_config.NumberColumn(format="%d개"),
    },
)
