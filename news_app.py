from bs4 import BeautifulSoup
import requests
import streamlit as st
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote

# 1. 페이지 설정
st.set_page_config(page_title="나만의 뉴스 탐색기", layout="wide")
st.title("📰 오늘의 뉴스 탐색기")

# 2. 날짜/날씨 정보
today = datetime.now().strftime("%Y년 %m월 %d일")
try:
    weather_url = "https://api.open-meteo.com/v1/forecast?latitude=37.5665&longitude=126.9780&current=temperature_2m,weather_code"
    weather_res = requests.get(weather_url, timeout=5).json()
    temp = weather_res["current"]["temperature_2m"]
    st.info(f"📅 **오늘 날짜:** {today}  |  🌡️ **현재 서울 기온:** {temp}℃")
except Exception:
    st.info(f"📅 **오늘 날짜:** {today}  |  🌡️ **현재 서울 기온:** 정보를 불러오지 못했습니다.")

st.write("---")

# 3. 세션 상태 및 검색 기능
if "keyword" not in st.session_state:
    st.session_state.keyword = ""

col1, col2, col3, col4 = st.columns(4)
if col1.button("사회 뉴스"):
    st.session_state.keyword = "사회"
if col2.button("경제 뉴스"):
    st.session_state.keyword = "경제"
if col3.button("IT/과학 뉴스"):
    st.session_state.keyword = "IT"
if col4.button("정치 뉴스"):
    st.session_state.keyword = "정치"

manual_keyword = st.text_input("직접 키워드 입력:", value=st.session_state.keyword)
if manual_keyword:
    st.session_state.keyword = manual_keyword


def format_pubdate(raw: str) -> str:
    """RFC822 형식(pubDate)을 'YYYY-MM-DD HH:MM' 형태로 변환. 실패 시 원문 그대로 반환."""
    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return raw


@st.cache_data(ttl=300)  # 5분 캐시: 같은 키워드로 반복 검색해도 매번 요청하지 않음
def fetch_google_news(keyword: str, max_items: int = 10):
    """구글 뉴스 RSS에서 키워드 관련 뉴스를 가져온다."""
    url = f"https://news.google.com/rss/search?q={quote(keyword)}&hl=ko&gl=KR&ceid=KR:ko"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers, timeout=10)
    res.raise_for_status()

    # "xml" 파서는 lxml 패키지가 필요한데 Streamlit Cloud 기본 환경엔 없는 경우가 많아
    # FeatureNotFound 에러가 남. 표준 라이브러리만으로 동작하는 html.parser 사용.
    # (html.parser는 태그명을 전부 소문자로 바꿔서 파싱하므로 find()도 소문자로 맞춰야 함)
    soup = BeautifulSoup(res.content, "html.parser")
    items = soup.find_all("item")

    news_list = []
    for item in items[:max_items]:
        title = item.find("title").text if item.find("title") else "제목 없음"
        link = item.find("link").text.strip() if item.find("link") else "#"
        pub_date = format_pubdate(item.find("pubdate").text) if item.find("pubdate") else ""
        source = item.find("source").text if item.find("source") else ""

        # 구글 뉴스 RSS의 description은 보통 제목을 감싼 <a> 태그 하나뿐이라
        # 실질적인 '요약'이 되지 못하는 경우가 많음. 있는 경우에만 사용.
        desc_text = ""
        if item.find("description"):
            desc_soup = BeautifulSoup(item.find("description").text, "html.parser")
            # 제목과 중복되는 링크 텍스트는 제외하고 나머지 텍스트만 추출
            for a_tag in desc_soup.find_all("a"):
                a_tag.decompose()
            desc_text = desc_soup.get_text(" ", strip=True)

        news_list.append({
            "title": title,
            "link": link,
            "pub_date": pub_date,
            "source": source,
            "desc": desc_text,
        })
    return news_list


# 4. 구글 뉴스 RSS 연동
if st.session_state.keyword:
    st.subheader(f"🔍 '{st.session_state.keyword}' 관련 최신 뉴스")

    try:
        news_items = fetch_google_news(st.session_state.keyword)
    except requests.exceptions.RequestException as e:
        news_items = []
        st.error(f"뉴스를 불러오는 중 오류가 발생했습니다: {e}")

    if news_items:
        for item in news_items:
            with st.container(border=True):
                st.markdown(f"### [{item['title']}]({item['link']})")
                meta = " | ".join(filter(None, [item["source"], f"⏰ {item['pub_date']}" if item["pub_date"] else ""]))
                if meta:
                    st.caption(meta)
                if item["desc"]:
                    st.write(item["desc"])
    else:
        st.warning("검색된 뉴스가 없습니다. 다른 키워드를 입력해 보세요.")
else:
    st.write("상단 버튼을 누르거나 키워드를 입력해 뉴스를 검색해 보세요.")
