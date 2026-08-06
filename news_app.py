from bs4 import BeautifulSoup
import pandas as pd
import requests
import streamlit as st
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="나만의 뉴스 탐색기", layout="wide")
st.title("📰 오늘의 뉴스 탐색기")

# 2. 오늘 날짜 및 실시간 날씨 정보 가져오기 (Open-Meteo 무료 API 활용)
today = datetime.now().strftime("%Y년 %m월 %d일")

try:
    # 서울 기준 날씨 정보 가져오기 (위도: 37.56, 경도: 126.97)
    weather_url = "https://api.open-meteo.com/v1/forecast?latitude=37.5665&longitude=126.9780&current=temperature_2m,weather_code"
    weather_res = requests.get(weather_url).json()
    temp = weather_res["current"]["temperature_2m"]
    
    # 상단에 날짜와 날씨 표시
    st.info(f"📅 **오늘 날짜:** {today}  |  🌡️ **현재 서울 기온:** {temp}℃")
except Exception:
    st.info(f"📅 **오늘 날짜:** {today}  |  🌡️ **현재 서울 기온:** 정보를 불러오지 못했습니다.")

st.write("---")

# 3. 테마별 키워드 버튼 생성
st.subheader("🔍 테마별 뉴스 검색")
col1, col2, col3, col4 = st.columns(4)
selected_keyword = None

if col1.button("사회 뉴스"): selected_keyword = "사회"
if col2.button("경제 뉴스"): selected_keyword = "경제"
if col3.button("IT/과학 뉴스"): selected_keyword = "IT 과학"
if col4.button("정치 뉴스"): selected_keyword = "정치"

# 직접 입력 기능
manual_keyword = st.text_input("또는 직접 키워드를 입력하세요:", "")
keyword = manual_keyword if manual_keyword else selected_keyword

# 4. 뉴스 수집 및 출력
if keyword:
    st.subheader(f"'{keyword}' 관련 최신 뉴스입니다.")
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.select(".news_tit")

    news_list = []
    for article in articles:
        news_list.append({"제목": article.get_text(), "링크": article["href"]})

    df = pd.DataFrame(news_list)
    if not df.empty:
        for idx, row in df.iterrows():
            st.markdown(f"{idx+1}. [{row['제목']}]({row['링크']})")
    else:
        st.warning("검색된 뉴스가 없습니다.")
else:
    st.write("상단 버튼을 누르거나 키워드를 입력해 뉴스를 검색해 보세요.")
