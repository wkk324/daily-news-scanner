from bs4 import BeautifulSoup
import pandas as pd
import requests
import streamlit as st
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="나만의 뉴스 탐색기", layout="wide")
st.title("📰 오늘의 뉴스 탐색기")

# 2. 날짜/날씨 정보
today = datetime.now().strftime("%Y년 %m월 %d일")
try:
    weather_url = "https://api.open-meteo.com/v1/forecast?latitude=37.5665&longitude=126.9780&current=temperature_2m,weather_code"
    weather_res = requests.get(weather_url).json()
    temp = weather_res["current"]["temperature_2m"]
    st.info(f"📅 **오늘 날짜:** {today}  |  🌡️ **현재 서울 기온:** {temp}℃")
except:
    st.info(f"📅 **오늘 날짜:** {today}  |  🌡️ **현재 서울 기온:** 정보를 불러오지 못했습니다.")

st.write("---")

# 3. 세션 상태 및 검색 기능
if "keyword" not in st.session_state: st.session_state.keyword = ""

col1, col2, col3, col4 = st.columns(4)
if col1.button("사회 뉴스"): st.session_state.keyword = "사회"
if col2.button("경제 뉴스"): st.session_state.keyword = "경제"
if col3.button("IT/과학 뉴스"): st.session_state.keyword = "IT"
if col4.button("정치 뉴스"): st.session_state.keyword = "정치"

manual_keyword = st.text_input("직접 키워드 입력:", value=st.session_state.keyword)
if manual_keyword: st.session_state.keyword = manual_keyword

# 4. 뉴스 수집 및 출력 (제목 클릭 활성화)
if st.session_state.keyword:
    st.subheader(f"🔍 '{st.session_state.keyword}' 관련 최신 구글 뉴스")
    
    rss_url = f"https://news.google.com/rss/search?q={st.session_state.keyword}&hl=ko&gl=KR&ceid=KR:ko"
    response = requests.get(rss_url)
    soup = BeautifulSoup(response.content, "html.parser")
    items = soup.find_all("item")

    if items:
        for idx, item in enumerate(items[:10]):
            title = item.find("title").text if item.find("title") else "제목 없음"
            link = item.find("link").text if item.find("link") else "#"
            pub_date = item.find("pubdate").text if item.find("pubdate") else ""
            source = item.find("source").text if item.find("source") else "출처 미상"
            
            # 요약 정제
            desc_text = ""
            if item.find("description"):
                desc_soup = BeautifulSoup(item.find("description").text, "html.parser")
                desc_text = desc_soup.get_text().strip()

            # 시각적 강조를 위한 박스 구성
            with st.container(border=True):
                st.markdown(f"### [{title}]({link})") # 제목 클릭 시 링크 연결
                st.caption(f"📢 {source}  |  ⏰ {pub_date}")
                if desc_text:
                    st.write(desc_text)
    else:
        st.warning("검색된 뉴스가 없습니다.")
