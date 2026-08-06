from bs4 import BeautifulSoup
import pandas as pd
import requests
import streamlit as st
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="나만의 뉴스 탐색기", layout="wide")
st.title("📰 오늘의 뉴스 탐색기")

# 날짜/날씨 정보
today = datetime.now().strftime("%Y년 %m월 %d일")
try:
    weather_url = "https://api.open-meteo.com/v1/forecast?latitude=37.5665&longitude=126.9780&current=temperature_2m,weather_code"
    weather_res = requests.get(weather_url).json()
    temp = weather_res["current"]["temperature_2m"]
    st.info(f"📅 **오늘 날짜:** {today}  |  🌡️ **현재 서울 기온:** {temp}℃")
except:
    st.info(f"📅 **오늘 날짜:** {today}  |  🌡️ **현재 서울 기온:** 정보를 불러오지 못했습니다.")

st.write("---")

# 세션 상태 초기화
if "keyword" not in st.session_state:
    st.session_state.keyword = ""

col1, col2, col3, col4 = st.columns(4)
if col1.button("사회 뉴스"): st.session_state.keyword = "사회"
if col2.button("경제 뉴스"): st.session_state.keyword = "경제"
if col3.button("IT/과학 뉴스"): st.session_state.keyword = "IT 과학"
if col4.button("정치 뉴스"): st.session_state.keyword = "정치"

manual_keyword = st.text_input("직접 키워드 입력:", value=st.session_state.keyword)
if manual_keyword: st.session_state.keyword = manual_keyword

# 뉴스 크롤링 로직 (선택자 수정)
if st.session_state.keyword:
    st.subheader(f"'{st.session_state.keyword}' 관련 최신 뉴스")
    url = f"https://search.naver.com/search.naver?where=news&query={st.session_state.keyword}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    # 2026년 검색 구조에 맞춰 제목/링크를 찾기 위한 여러 선택자 시도
    articles = soup.select("a.news_tit") or soup.select(".list_news .tit") or soup.select("div.news_wrap a")

    if articles:
        news_data = []
        for a in articles:
            if a.get_text().strip():
                news_data.append({"제목": a.get_text().strip(), "링크": a.get("href")})
        
        # 중복 제거 및 결과 출력
        df = pd.DataFrame(news_data).drop_duplicates()
        for idx, row in df.head(10).iterrows():
            st.markdown(f"**{idx+1}. [{row['제목']}]({row['링크']})**")
    else:
        st.warning("네이버 검색 결과 구조가 변경되어 뉴스를 불러올 수 없습니다.")
