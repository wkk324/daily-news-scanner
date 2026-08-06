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
if col3.button("IT/과학 뉴스"): st.session_state.keyword = "IT"
if col4.button("정치 뉴스"): st.session_state.keyword = "정치"

manual_keyword = st.text_input("직접 키워드 입력:", value=st.session_state.keyword)
if manual_keyword: st.session_state.keyword = manual_keyword

# 구글 뉴스 RSS 크롤링 (html.parser 사용으로 에러 방지)
if st.session_state.keyword:
    st.subheader(f"'{st.session_state.keyword}' 관련 최신 구글 뉴스")
    
    rss_url = f"https://news.google.com/rss/search?q={st.session_state.keyword}&hl=ko&gl=KR&ceid=KR:ko"
    
    response = requests.get(rss_url)
    soup = BeautifulSoup(response.content, "html.parser") # html.parser로 변경
    
    items = soup.find_all("item")

    if items:
        news_data = []
        for item in items[:15]:
            title = item.find("title").text if item.find("title") else "제목 없음"
            link = item.find("link").text if item.find("link") else "#"
            news_data.append({"제목": title, "링크": link})
        
        df = pd.DataFrame(news_data)
        for idx, row in df.iterrows():
            st.markdown(f"**{idx+1}. [{row['제목']}]({row['링크']})**")
    else:
        st.warning("검색된 뉴스가 없습니다. 다른 키워드를 입력해 보세요.")
else:
    st.write("상단 버튼을 누르거나 키워드를 입력해 뉴스를 검색해 보세요.")
