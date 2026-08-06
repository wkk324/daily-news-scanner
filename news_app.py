from bs4 import BeautifulSoup
import pandas as pd
import requests
import streamlit as st

# 1. 웹페이지 화면 구성 (Streamlit)
st.title("📰 나만의 맞춤형 뉴스 키워드 탐색기")
st.write(
    "관심 있는 키워드를 입력하시면 네이버 최신 뉴스를 싹 긁어와서 보여드립니다!"
)

# 사용자 입력 받기
keyword = st.text_input("검색할 키워드를 입력하세요 (예: 금리, 인공지능, 부동산)", "인공지능")

if st.button("뉴스 검색하기"):
  if not keyword:
    st.warning("검색어를 입력해주세요!")
  else:
    with st.spinner(
        "네이버에서 최신 뉴스를 수집하고 있습니다 잠시만 기다려주세요..."
    ):
      # 2. 네이버 뉴스 검색 URL 생성
      url = f"https://search.naver.com/search.naver?where=news&query={keyword}"

      # 3. 헤더 설정 (네이버가 봇 차단하지 않도록 일반 브라우저인 것처럼 위장)
      headers = {
          "User-Agent": (
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
              " like Gecko) Chrome/120.0.0.0 Safari/537.36"
          )
      }

      response = requests.get(url, headers=headers)
      soup = BeautifulSoup(response.text, "html.parser")

      # 4. 뉴스 기사 제목과 링크 추출
      news_list = []
      articles = soup.select(".news_tit")

      for article in articles:
        title = article.get_text()
        link = article["href"]
        news_list.append({"제목": title, "링크": link})

      # 5. 결과 화면에 출력
      if len(news_list) > 0:
        st.success(f"총 {len(news_list)}개의 뉴스를 찾아냈습니다!")

        # 보기 좋게 표 형태로 출력 (링크 클릭 가능)
        df = pd.DataFrame(news_list)

        for idx, row in df.iterrows():
          st.markdown(f"**{idx+1}. [{row['제목']}]({row['링크']})**")
          st.write("---")
      else:
        st.info("검색 결과가 없습니다. 다른 키워드로 시도해 보세요.")
