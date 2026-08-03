import datetime
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 어제의 박스오피스")

try:
    # 1. 비밀 금고(Secrets) 안전 검사
    if "KOBIS_KEY" not in st.secrets:
        st.error(
            "⚠️ **KOBIS_KEY가 Secrets에 없습니다.**\n\n"
            "Streamlit Cloud 설정 -> Secrets 탭에서 `KOBIS_KEY = '발급받은키'` 형태로 입력해 주세요."
        )
        st.stop()

    KOBIS_KEY = st.secrets["KOBIS_KEY"]

    # 2. 한국 시간 기준 어제 날짜 계산 (배포 서버 시계 독립)
    korea_tz = datetime.timezone(datetime.timedelta(hours=9))
    yesterday = datetime.datetime.now(korea_tz) - datetime.timedelta(days=1)
    target_dt = yesterday.strftime("%Y%m%d")

    st.caption(f"조회 기준일(어제): {yesterday.strftime('%Y-%m-%d')}")

    # 3. KOBIS API 요청
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    res = requests.get(
        url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10
    )

    if res.status_code != 200:
        st.error(f"API 요청 실패 (HTTP 상태코드: {res.status_code})")
        st.stop()

    data = res.json()

    # 4. KOBIS API 예외 응답 처리 (잘못된 인증키 등)
    if "faultInfo" in data:
        st.error(
            f"⚠️ **KOBIS API 인증 에러**: {data['faultInfo'].get('message', '인증 실패')}\n\n"
            "Secrets에 입력한 `KOBIS_KEY` 값이 정확한지 확인해 주세요."
        )
        st.stop()

    box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
    if not box_list:
        st.warning("해당 날짜의 집계 데이터가 존재하지 않습니다.")
        st.stop()

    # 5. 데이터 가공
    df = pd.DataFrame(box_list)

    for col in ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 6. 상단 지표 카드
    top = df.sort_values("rank").iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("어제 1위", top["movieNm"])
    c2.metric("어제 관객수", f"{int(top['audiCnt']):,}명")
    c3.metric("누적 관객", f"{int(top['audiAcc']):,}명")

    # 7. 차트 및 전체 표 출력
    table = df[
        ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
    ].copy()
    table.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]
    table = table.sort_values("순위").reset_index(drop=True)

    st.subheader("📊 관객수 상위 5편")
    top5 = table.sort_values("관객수", ascending=False).head(5)
    st.bar_chart(top5.set_index("영화명")["관객수"])

    st.subheader("📋 박스오피스 TOP 10")
    st.dataframe(table, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"🚨 **앱 실행 중 에러 발생:** `{e}`")
    st.exception(e)
