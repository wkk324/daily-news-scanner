from bs4 import BeautifulSoup
import requests
import streamlit as st
import xml.etree.ElementTree as ET
import re
import base64
import html
import calendar
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote

# 1. 페이지 설정
st.set_page_config(page_title="나만의 뉴스 탐색기", layout="wide")
st.title("📰 오늘의 뉴스 탐색기")

# 2. 날짜/날씨 정보
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
now = datetime.now()
current_time_str = now.strftime("%Y년 %m월 %d일") + f" ({WEEKDAY_KR[now.weekday()]}) " + now.strftime("%H:%M:%S")


def weather_emoji(code: int) -> str:
    """WMO 날씨 코드를 이모지로 변환."""
    if code == 0:
        return "☀️"
    if code in (1, 2):
        return "⛅"
    if code == 3:
        return "☁️"
    if code in (45, 48):
        return "🌫️"
    if code in (51, 53, 55, 56, 57, 80, 81, 82):
        return "🌦️"
    if code in (61, 63, 65, 66, 67):
        return "🌧️"
    if code in (71, 73, 75, 77, 85, 86):
        return "🌨️"
    if code in (95, 96, 99):
        return "⛈️"
    return "🌡️"


def build_mini_calendar_html(year: int, month: int, today_day: int, cell_w: int = 30, cell_h: int = 27) -> str:
    """작은 한 달 달력 HTML을 만든다. 오늘 날짜는 동그라미로 강조."""
    cal = calendar.Calendar(firstweekday=6)  # 일요일부터 시작
    weeks = cal.monthdayscalendar(year, month)
    headers = ["일", "월", "화", "수", "목", "금", "토"]

    rows = ['<table style="border-collapse:collapse; font-size:13px; table-layout:fixed; text-align:center;">']
    rows.append("<tr>")
    for i, h in enumerate(headers):
        color = "#e74c3c" if i == 0 else ("#3b82f6" if i == 6 else "#666")
        rows.append(f'<th style="padding:3px; color:{color}; font-weight:600;">{h}</th>')
    rows.append("</tr>")

    for week in weeks:
        rows.append("<tr>")
        for i, day in enumerate(week):
            if day == 0:
                rows.append('<td style="padding:2px;"></td>')
                continue
            is_today = day == today_day
            if is_today:
                style = "background:#4a90d9; color:white; border-radius:50%;"
            elif i == 0:
                style = "color:#e74c3c;"
            elif i == 6:
                style = "color:#3b82f6;"
            else:
                style = ""
            rows.append(
                f'<td style="padding:2px;"><span style="{style} display:inline-block; '
                f'width:{cell_w}px; height:{cell_h}px; line-height:{cell_h}px;">{day}</span></td>'
            )
        rows.append("</tr>")
    rows.append("</table>")
    return "".join(rows)


with st.container(key="time_row"):
    time_col, refresh_col = st.columns([1, 1])
    with time_col:
        st.markdown(
            f'<div style="font-size:30px; font-weight:700; line-height:1.3; white-space:nowrap;">🕐 {current_time_str}</div>',
            unsafe_allow_html=True,
        )
    with refresh_col:
        if st.button("🔄", key="refresh_btn", help="새로고침 (기사/요약 다시 받아오기)"):
            st.cache_data.clear()  # 기사/요약 캐시를 모두 지워서 최신 기사를 다시 받아옴
            st.rerun()

# 새로고침 버튼을 시간 텍스트 바로 옆에 붙임: 컬럼이 각자 비율만큼 넓게 차지하는 대신
# 내용물 크기만큼만(shrink-to-fit) 차지하도록 강제해서 둘 사이 빈 여백을 없앰.
# 버튼은 브라우저 새로고침 아이콘처럼 - 테두리/배경 없이 검은 실루엣만, 크게.
# filter:brightness(0)로 원래 색깔 이모지를 검은 실루엣으로 강제 변환 (특정 유니코드 화살표 문자가
# 폰트에 따라 아예 안 보이는 문제를 피하기 위해, 확실히 렌더링되는 🔄 이모지를 사용)
st.markdown(
    """
    <style>
    .st-key-time_row [data-testid="stHorizontalBlock"] {
        gap: 6px !important;
    }
    .st-key-time_row [data-testid="stColumn"] {
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: 0 !important;
    }
    .st-key-refresh_btn button {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        box-shadow: none !important;
        font-size: 34px !important;
        line-height: 1 !important;
        filter: grayscale(100%) brightness(0);
        opacity: 0.85;
        margin-top: 4px;
    }
    .st-key-refresh_btn button:hover {
        opacity: 1;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

col_date, col_weather = st.columns([1, 1.3])

CALENDAR_WRAP_HEIGHT = 310  # 날씨란 전체 높이(현재기온 줄 + 시간대별 박스)에 맞춰 더 늘림

with col_date:
    st.markdown(
        f'<div style="height:{CALENDAR_WRAP_HEIGHT}px;">'
        + build_mini_calendar_html(now.year, now.month, now.day, cell_w=36)
        + "</div>",
        unsafe_allow_html=True,
    )

with col_weather:
    try:
        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=37.5665&longitude=126.9780"
            "&current=temperature_2m,weather_code"
            "&hourly=temperature_2m,weather_code,precipitation_probability"
            "&timezone=Asia/Seoul&forecast_days=1"
        )
        weather_res = requests.get(weather_url, timeout=5).json()
        current_temp = weather_res["current"]["temperature_2m"]
        current_code = weather_res["current"]["weather_code"]

        st.markdown(
            f"{weather_emoji(current_code)} **현재 서울 기온:** {current_temp}℃"
        )

        # 시간대별 예보를 3시간 간격으로 위에서 아래로 나열
        hourly = weather_res["hourly"]
        times = hourly["time"]  # "2026-08-07T00:00" 형식
        temps = hourly["temperature_2m"]
        codes = hourly["weather_code"]
        pops = hourly["precipitation_probability"]

        hour_rows = ""
        for i in range(0, len(times), 3):
            hour_only = times[i].split("T")[1][:2] + "시"
            hour_rows += f"""
<div style="display:flex; justify-content:space-between; align-items:center; padding:3px 8px; border-bottom:1px solid #f0f0f0; font-size:12px;">
    <span style="color:#666; width:32px;">{hour_only}</span>
    <span style="font-size:15px;">{weather_emoji(codes[i])}</span>
    <span style="font-weight:600; width:38px; text-align:right;">{temps[i]}℃</span>
    <span style="color:#4a90d9; width:48px; text-align:right;">💧{pops[i]}%</span>
</div>
"""
        st.markdown(
            f'<div style="border:1px solid #eee; border-radius:6px; '
            f'width:260px; max-height:220px; overflow-y:auto;">{hour_rows}</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        st.markdown("🌡️ **날씨 정보를 불러오지 못했습니다.**")

st.write("---")





# 3. 세션 상태 및 검색 기능
if "keyword" not in st.session_state:
    st.session_state.keyword = ""
if "label" not in st.session_state:
    st.session_state.label = ""

ALL_QUERY = "__ALL__"  # '전체' 카테고리를 나타내는 특수 값 (검색어 없이 전체 헤드라인)

# 카테고리 라벨: 실제 검색에 쓸 키워드 (일반적인 포털 뉴스 분류 기준)
CATEGORIES = {
    "전체": ALL_QUERY,
    "정치": "정치",
    "경제": "경제",
    "사회": "사회",
    "생활/문화": "문화",
    "IT/과학": "IT",
    "세계": "국제",
    "스포츠": "스포츠",
    "연예": "연예",
}

st.caption("📌 카테고리 선택")

cat_items = list(CATEGORIES.items())
for row_start in range(0, len(cat_items), 5):  # 5개씩 2줄로 배치
    row = cat_items[row_start:row_start + 5]
    cols = st.columns(5)
    for col, (label, query) in zip(cols, row):
        if col.button(label, use_container_width=True):
            st.session_state.keyword = query
            st.session_state.label = label

manual_keyword = st.text_input("직접 키워드 입력:", value=st.session_state.keyword)
if manual_keyword and manual_keyword != st.session_state.keyword:
    st.session_state.keyword = manual_keyword
    st.session_state.label = manual_keyword  # 직접 입력한 경우 라벨=검색어


def format_pubdate(raw: str) -> str:
    """RFC822 형식(pubDate)을 'YYYY-MM-DD HH:MM' 형태로 변환. 실패 시 원문 그대로 반환."""
    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return raw


GOOGLE_BOILERPLATE = "comprehensive up-to-date news coverage"
MIN_SUMMARY_LEN = 20  # 이보다 짧으면 '언론사 이름'류의 무의미한 텍스트로 간주하고 버림


def decode_google_news_link(google_link: str) -> str:
    """구글 뉴스 리다이렉트 링크(news.google.com/rss/articles/...) 안에 인코딩된
    실제 언론사 기사 URL을 추출한다. 디코딩에 실패하면 원래 링크를 그대로 반환."""
    try:
        match = re.search(r"/articles/([^?]+)", google_link)
        if not match:
            return google_link
        encoded = match.group(1)
        padded = encoded + "=" * (-len(encoded) % 4)  # base64 패딩 보정
        decoded_bytes = base64.urlsafe_b64decode(padded)
        url_match = re.search(rb"https?://[^\x00-\x1f\"'<>]+", decoded_bytes)
        if url_match:
            return url_match.group(0).decode("utf-8", errors="ignore")
    except Exception:
        pass
    return google_link


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
                is_boilerplate = GOOGLE_BOILERPLATE in summary.lower()
                is_too_short = len(summary) < MIN_SUMMARY_LEN
                if summary and not is_boilerplate and not is_too_short:
                    return summary
        return ""
    except Exception:
        # 언론사 페이지 구조가 다르거나 접속이 막힌 경우 등 - 조용히 실패하고 빈 값 반환
        return ""


@st.cache_data(ttl=300)  # 5분 캐시: 같은 키워드로 반복 검색해도 매번 요청하지 않음
def fetch_google_news(keyword: str, max_items: int = 10):
    """구글 뉴스 RSS에서 키워드 관련 뉴스를 가져온다.
    keyword가 ALL_QUERY이면 특정 주제 검색 없이 전체 헤드라인 피드를 사용한다."""
    if keyword == ALL_QUERY:
        url = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"
    else:
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
        raw_link = link_el.text.strip() if link_el is not None and link_el.text else "#"
        link = decode_google_news_link(raw_link)  # 구글 중간 리다이렉트 대신 실제 언론사 URL로 교체 시도
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

    # pub_date가 "YYYY-MM-DD HH:MM" 형식(0으로 채워진 고정 길이)이라 문자열 그대로
    # 내림차순 정렬해도 최신순이 됨. 날짜를 못 가져온 항목("")은 자동으로 맨 뒤로 감.
    news_list.sort(key=lambda x: x["pub_date"], reverse=True)
    return news_list


# 4. 구글 뉴스 RSS 연동
if st.session_state.keyword:
    header_text = "전체 최신 뉴스" if st.session_state.keyword == ALL_QUERY else f"'{st.session_state.label}' 관련 최신 뉴스"
    st.subheader(f"🔍 {header_text}")

    try:
        news_items = fetch_google_news(st.session_state.keyword)
    except requests.exceptions.RequestException as e:
        news_items = []
        st.error(f"뉴스를 불러오는 중 오류가 발생했습니다: {e}")

    if news_items:
        cards_html = ""
        for item in news_items:
            summary = fetch_summary(item["link"]) or item["desc"]
            meta = " | ".join(filter(None, [item["source"], item["pub_date"]]))

            title_esc = html.escape(item["title"])
            summary_esc = html.escape(summary) if summary else ""
            meta_esc = html.escape(meta)

            cards_html += f"""
<div style="border:1px solid #e0e0e0; border-radius:6px; padding:6px 12px; margin-bottom:4px;">
    <a href="{item['link']}" target="_blank"
       style="font-size:14px; font-weight:600; text-decoration:none; line-height:1.15;">
        {title_esc}
    </a>
    <div style="font-size:11px; color:#888; margin-top:1px; line-height:1.1;">{meta_esc}</div>
    {f'<div style="font-size:12.5px; color:#444; margin-top:1px; line-height:1.15;">📝 {summary_esc}</div>' if summary_esc else ''}
</div>
"""
        st.markdown(cards_html, unsafe_allow_html=True)
    else:
        st.warning("검색된 뉴스가 없습니다. 다른 키워드를 입력해 보세요.")
else:
    st.write("상단 버튼을 누르거나 키워드를 입력해 뉴스를 검색해 보세요.")
