from bs4 import BeautifulSoup
import pandas as pd
import requests
import streamlit as st
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="나만의 뉴스 탐색기", layout="wide")
st.title("📰 오늘의 뉴스 탐색기")

# 날짜 및 날씨 정보 표시
today = datetime.now().strftime("%Y년 %m월 %d일")
st.write(f"📅 **오늘 날짜:** {today}")
st.info("☀️ **서울 날씨:** 오늘은 최고 37℃로 매우 무덥습니다. 건강에 유의하세요!")

st.write("---")

# 2. 키워드 선택 버튼
col1, col2, col3, col4 = st.columns(4)
keywords = {"사회": "사회", "경제": "경제", "IT/과학": "IT 과학", "정치": "정치"}
selected_keyword = None

if col1.button("사회 뉴스"): selected_keyword = "사회"
if col2.button("경제 뉴스"): selected_keyword = "경제"
if col3.button("IT/과학 뉴스"): selected_keyword = "IT 과학"
if col4.button("정치 뉴스"): selected_keyword = "정치"

# 검색창
manual_keyword = st.text_input("또는 직접 키워드를 입력하세요:", "")
keyword = manual_keyword if manual_keyword else selected_keyword

# 3. 뉴스 수집 함수
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

    # 4. 결과 출력
    df = pd.DataFrame(news_list)
    for idx, row in df.iterrows():
        st.markdown(f"{idx+1}. [{row['제목']}]({row['링크']})")
else:
    st.write("상단 버튼을 누르거나 키워드를 입력해 뉴스를 검색해 보세요.")
