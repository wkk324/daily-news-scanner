from bs4 import BeautifulSoup
import requests
import streamlit as st
import xml.etree.ElementTree as ET
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


@st.cache_data(ttl=86400, show_spinner=False)  # 24시간 캐시: 같은 기사 요약을 매번 다시 가져오지 않음
def fetch_summary(link: str) -> str:
    """기사 원문 페이지의 og:description(또는 description) 메타태그에서 한 줄 요약을 가져온다."""
    if not link or link == "#":
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(link, headers=headers, timeout=5, allow_redirects=True)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, "html.parser")

        for attrs in (
            {"property": "og:description"},
            {"name": "description"},
            {"name": "twitter:description"},
        ):
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                summary = tag["content"].strip()
                if summary:
                    return summary
        return ""
    except Exception:
        # 언론사 페이지 구조가 다르거나 접속이 막힌 경우 등 - 조용히 실패하고 빈 값 반환
        return ""


@st.cache_data(ttl=300)  # 5분 캐시: 같은 키워드로 반복 검색해도 매번 요청하지 않음
def fetch_google_news(keyword: str, max_items: int = 10):
    """구글 뉴스 RSS에서 키워드 관련 뉴스를 가져온다."""
    url = f"https://news.google.com/rss/search?q={quote(keyword)}&hl=ko&gl=KR&ceid=KR:ko"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers, timeout=10)
    res.raise_for_status()

    # bs4의 html.parser는 <link>를 HTML의 self-closing 태그로 착각해서
    # <link>URL</link> 안의 URL 텍스트를 놓쳐버리는 문제가 있었음(빈 링크 -> 자기 페이지로 되돌아감).
    # RSS는 표준 XML이므로 파이썬 내장 xml.etree.ElementTree로 파싱하면 이 문제가 없고,
    # lxml 같은 추가 패키지 설치도 필요 없음.
    root = ET.fromstring(res.content)
    items = root.findall(".//item")

    news_list = []
    for item in items[:max_items]:
        title_el = item.find("title")
        link_el = item.find("link")
        pubdate_el = item.find("pubDate")
        source_el = item.find("source")
        desc_el = item.find("description")

        title = title_el.text if title_el is not None and title_el.text else "제목 없음"
        link = link_el.text.strip() if link_el is not None and link_el.text else "#"
        pub_date = format_pubdate(pubdate_el.text) if pubdate_el is not None and pubdate_el.text else ""
        source = source_el.text if source_el is not None and source_el.text else ""

        # 구글 뉴스 RSS의 description은 보통 제목을 감싼 <a> 태그 하나뿐이라
        # 실질적인 '요약'이 되지 못하는 경우가 많음. 있는 경우에만 사용.
        desc_text = ""
        if desc_el is not None and desc_el.text:
            desc_soup = BeautifulSoup(desc_el.text, "html.parser")
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
                # h3(###) 대신 커스텀 폰트 크기로 제목을 좀 더 작게 표시
                st.markdown(
                    f'<a href="{item["link"]}" target="_blank" '
                    f'style="font-size:17px; font-weight:600; text-decoration:none;">'
                    f'{item["title"]}</a>',
                    unsafe_allow_html=True,
                )
                meta = " | ".join(filter(None, [item["source"], f"⏰ {item['pub_date']}" if item["pub_date"] else ""]))
                if meta:
                    st.caption(meta)

                # 기사 원문에서 한 줄 요약(og:description)을 가져오고,
                # 없으면 RSS의 description으로 대체
                summary = fetch_summary(item["link"]) or item["desc"]
                if summary:
                    st.write(f"📝 {summary}")
    else:
        st.warning("검색된 뉴스가 없습니다. 다른 키워드를 입력해 보세요.")
else:
    st.write("상단 버튼을 누르거나 키워드를 입력해 뉴스를 검색해 보세요.")
