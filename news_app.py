from bs4 import BeautifulSoup
import requests
import streamlit as st
import html
import calendar
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from streamlit_js_eval import streamlit_js_eval

# 1. 페이지 설정
st.set_page_config(page_title="뉴스 검색기", layout="wide")

# 2. 날짜/날씨/카테고리 정보
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
now = datetime.now()
current_time_str = now.strftime("%Y년 %m월 %d일") + f" ({WEEKDAY_KR[now.weekday()]}) " + now.strftime("%H:%M:%S")

ALL_QUERY = "__ALL__"  # '전체' 카테고리를 나타내는 특수 값 (모든 카테고리를 합쳐서 최신순 정렬)
MAIN_QUERY = "__MAIN__"  # '주요' 카테고리를 나타내는 특수 값 (구글이 선정한 톱헤드라인 피드)

# 세션 상태 (선택된 카테고리) - 처음 접속 시 기본값을 '전체'로 설정해서 바로 뉴스가 보이게 함
if "keyword" not in st.session_state:
    st.session_state.keyword = ALL_QUERY
if "label" not in st.session_state:
    st.session_state.label = "전체"
if "naver_target_total" not in st.session_state:
    st.session_state.naver_target_total = 100  # 네이버는 '더보기' 누를 때마다 100개씩 실제로 더 가져옴
if "nfinance_target_total" not in st.session_state:
    st.session_state.nfinance_target_total = 100  # 네이버 금융도 동일하게 '더보기'로 더 가져옴
if "gps_nonce" not in st.session_state:
    st.session_state.gps_nonce = 0  # 새로고침 버튼을 누를 때마다 증가시켜 GPS 위치를 다시 요청시킴

# 카테고리 라벨: 실제 검색에 쓸 키워드 (일반적인 포털 뉴스 분류 기준)
CATEGORIES = {
    "전체": ALL_QUERY,
    "주요": MAIN_QUERY,
    "정치": "정치",
    "경제": "경제",
    "사회": "사회",
    "생활/문화": "문화",
    "IT/과학": "IT",
    "세계": "국제",
    "스포츠": "스포츠",
    "연예": "연예",
}


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
                cell_style = "padding:2px; background:#4a90d9;"
                span_style = "color:white;"
            else:
                cell_style = "padding:2px;"
                if i == 0:
                    span_style = "color:#e74c3c;"
                elif i == 6:
                    span_style = "color:#3b82f6;"
                else:
                    span_style = ""
            rows.append(
                f'<td style="{cell_style}"><span style="{span_style} display:inline-block; '
                f'width:{cell_w}px; height:{cell_h}px; line-height:{cell_h}px;">{day}</span></td>'
            )
        rows.append("</tr>")
    rows.append("</table>")
    return "".join(rows)


st.title("📰 뉴스 검색기")

# 아래 컨텐츠 행(카테고리/달력/날씨)과 동일한 비율의 컬럼을 시간 행에도 그대로 사용해서,
# 시간+새로고침 버튼이 정확히 '달력' 컬럼 바로 위에 오도록 맞춤 (같은 비율 -> 같은 폭/위치).
LAYOUT_RATIOS = [39, 11, 25, 25]  # [카테고리(원래 폭), 빈 여백, 달력, 날씨] - 달력이 화면 중간(50%)부터 시작

_, _, time_slot_col, _ = st.columns(LAYOUT_RATIOS)
with time_slot_col:
    # 시간 텍스트와 새로고침 버튼을 나란히 배치.
    # 음수 margin-top으로 타이틀 줄 쪽으로 끌어올려서, 타이틀 밑부분과 이 줄의 밑부분이 같은 높이에 오도록 함.
    # 새로고침은 <a href> 링크 대신 st.button을 씀: 링크 방식은 iframe 환경(Streamlit 배포 시 자주 발생)에서
    # 새 창으로 열려버리는 문제가 있었는데, st.button은 페이지 이동 없이 같은 화면에서 다시 그려줘서 안전함.
    with st.container(key="time_row"):
        time_col, refresh_col = st.columns([10, 1])
        with time_col:
            st.markdown(
                f'<div style="font-size:30px; font-weight:700; line-height:1.3; white-space:nowrap;">🕐 {current_time_str}</div>',
                unsafe_allow_html=True,
            )
        with refresh_col:
            if st.button("↻", key="refresh_btn", help="새로고침 (기사/요약/위치 다시 받아오기)"):
                st.session_state.gps_nonce += 1  # GPS 좌표도 새로 요청하도록 트리거
                st.cache_data.clear()  # 기사/요약 캐시를 모두 지워서 최신 기사를 다시 받아옴
                st.rerun()

# time_row 컨테이너 자체에 직접 margin을 줘서 위치 조정.
# 새로고침 버튼은 title 속성(help 파라미터로 생성됨 - Streamlit 버전과 무관하게 항상 존재하는
# 표준 HTML 속성)을 직접 타겟팅: 배경/테두리를 없애서 네모 버튼 모양이 안 보이게 하고,
# 글자를 검은색·크게 키움.
st.markdown(
    """
    <style>
    .st-key-time_row {
        margin-top: -55px;
        margin-bottom: -8px;
    }
    /* 새로고침 버튼(refresh_col)이 [10,1] 비율 컬럼의 오른쪽 끝에 고정되면서
       시간 텍스트와 멀리 떨어져 보이던 문제 - 두 컬럼을 내용 크기만큼만 차지하게 줄여서
       버튼이 텍스트 바로 옆에 붙게 함 */
    .st-key-time_row [data-testid="stHorizontalBlock"] {
        justify-content: flex-start !important;
        flex-wrap: nowrap !important;
        gap: 20px !important;
    }
    .st-key-time_row [data-testid="stColumn"] {
        width: auto !important;
        flex: 0 0 auto !important;
        min-width: 0 !important;
    }
    /* GPS 위치 컴포넌트(눈에는 안 보이지만 레이아웃 공간은 차지함)를 접어서,
       "현재 OO 기온" 줄이 '카테고리 선택'/'달력' 타이틀과 같은 높이에서 시작하게 함.
       margin-bottom을 음수로 줘서 부모 stVerticalBlock의 flex gap(16px)까지 상쇄함. */
    .st-key-geo {
        height: 0 !important;
        min-height: 0 !important;
        overflow: hidden !important;
        margin: 0 0 -16px 0 !important;
        padding: 0 !important;
    }
    button[title="새로고침 (기사/요약/위치 다시 받아오기)"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        color: #000 !important;
        font-size: 40px !important;
        font-weight: 700 !important;
        line-height: 1 !important;
    }
    button[title="새로고침 (기사/요약/위치 다시 받아오기)"]:hover {
        color: #444 !important;
        background: transparent !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


outer_left, _, col_date, col_weather = st.columns(LAYOUT_RATIOS)

CALENDAR_CELL_H = 32  # 원래 27에서 조금 키움 - 날씨 표와 길이를 맞추기 위함
# 요일 헤더 행(패딩+13px 폰트로 실측 약 28px)과 날짜 행(cell_h + td 패딩/보더로 실측 cell_h+5px) 6줄을
# 더한 실제 렌더링 높이. 이 값을 그대로 날씨 예보 표 높이로도 써서 두 표의 길이를 맞춤.
CALENDAR_WRAP_HEIGHT = 28 + 6 * (CALENDAR_CELL_H + 5)

with col_date:
    st.markdown("📅 **달력**")
    st.markdown(
        f'<div style="height:{CALENDAR_WRAP_HEIGHT}px;">'
        + build_mini_calendar_html(now.year, now.month, now.day, cell_w=36, cell_h=CALENDAR_CELL_H)
        + "</div>",
        unsafe_allow_html=True,
    )

@st.cache_data(ttl=600, show_spinner=False)  # 10분 캐시: 리런/버튼클릭마다 재호출하지 않음 (API 일일 한도 보호)
def fetch_weather(lat: float, lon: float):
    """지정한 좌표의 현재 날씨 + 시간대별 예보를 가져온다."""
    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,weather_code"
        "&hourly=temperature_2m,weather_code,precipitation_probability"
        "&timezone=auto&forecast_days=1"
    )
    weather_response = requests.get(weather_url, timeout=10)
    weather_res = weather_response.json()
    if "current" not in weather_res:
        # API가 200을 줬지만 기대한 형식이 아님 - 실제 응답을 그대로 보여줘서 원인 파악
        raise ValueError(f"API 응답 이상 (status={weather_response.status_code}): {weather_res}")
    return weather_res


@st.cache_data(ttl=3600, show_spinner=False)  # 1시간 캐시 - 같은 IP를 반복 조회하지 않음
def locate_by_ip(ip: str):
    """접속 IP 주소로 대략적인 위치(도시 단위)를 추정한다 (ip-api.com, 무료).
    (라벨, 위도, 경도) 튜플을 반환. 실패하면 서울 기본값을 반환."""
    default = ("서울", 37.5665, 126.9780)
    if not ip:
        return default
    try:
        url = f"http://ip-api.com/json/{ip}"
        params = {"lang": "ko", "fields": "status,city,regionName,lat,lon"}
        res = requests.get(url, params=params, timeout=5)
        res.raise_for_status()
        data = res.json()
        if data.get("status") != "success":
            return default
        city = data.get("city") or ""
        region = data.get("regionName") or ""
        label = " ".join(p for p in (region, city) if p) or "내 위치"
        return label, data["lat"], data["lon"]
    except Exception:
        return default


def _simplify_si_name(si: str) -> str:
    """'서울특별시' -> '서울', '부산광역시' -> '부산' 처럼 시/도 이름을 짧게 줄인다."""
    for suffix in ("특별자치시", "특별자치도", "광역시", "특별시"):
        if si.endswith(suffix):
            return si[: -len(suffix)]
    return si


@st.cache_data(ttl=3600, show_spinner=False)  # 1시간 캐시 - 같은 좌표를 반복 조회하지 않음
def reverse_geocode_si(lat: float, lon: float) -> str:
    """좌표를 '서울', '부산' 같은 시/도 단위 이름으로 변환한다 (OpenStreetMap Nominatim, 키 불필요).
    구/동까지 보여주면 표시가 지저분해서 시/도까지만 씀. 실패 시 빈 문자열 반환 (호출부에서 대체 라벨을 씀)."""
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 18, "accept-language": "ko"}
        # Nominatim 사용 정책상 식별 가능한 User-Agent가 필요함 (익명 UA는 차단될 수 있음)
        headers = {"User-Agent": "daily-news-scanner/1.0 (personal streamlit weather widget)"}
        res = requests.get(url, params=params, headers=headers, timeout=5)
        res.raise_for_status()
        addr = res.json().get("address", {})
        si = addr.get("city") or addr.get("town") or addr.get("county") or ""
        return _simplify_si_name(si)
    except Exception:
        return ""


# 접속 IP로 위치 추정 (기본값 - GPS 권한을 아직 못 받았거나 거부됐을 때 쓰는 fallback)
weather_location_label, weather_lat, weather_lon = locate_by_ip(st.context.ip_address)

with col_weather:
    # 브라우저 GPS: streamlit-js-eval로 getLocation()을 실행한다. 버튼 클릭 없이
    # 컴포넌트가 렌더링되는 즉시 navigator.geolocation을 호출하며, 위치 권한 팝업은
    # 오리진당 최초 1회만 뜨고 그 이후엔 조용히 좌표를 반환한다. js_expressions
    # 문자열에 gps_nonce를 섞어 넣어서, 이 값이 바뀔 때(= 새로고침 버튼을 눌렀을 때)만
    # 컴포넌트가 재평가하도록 함 (동일 문자열이면 프론트엔드가 재평가를 건너뛰고
    # 이전에 받아온 좌표를 세션 상태에서 그대로 재사용함).
    gps_result = streamlit_js_eval(
        js_expressions=f"getLocation() /* nonce:{st.session_state.gps_nonce} */",
        key="geo",
    )
    if gps_result and gps_result.get("coords"):
        weather_lat = gps_result["coords"]["latitude"]
        weather_lon = gps_result["coords"]["longitude"]
        si_label = reverse_geocode_si(weather_lat, weather_lon)
        weather_location_label = si_label or "내 위치"

    try:
        weather_res = fetch_weather(weather_lat, weather_lon)
        current_temp = weather_res["current"]["temperature_2m"]
        current_code = weather_res["current"]["weather_code"]

        st.markdown(
            f"{weather_emoji(current_code)} **현재 {weather_location_label} 기온:** {current_temp}℃"
        )

        # 시간대별 예보를 3시간 간격으로 위에서 아래로 나열
        hourly = weather_res["hourly"]
        times = hourly["time"]  # "2026-08-07T00:00" 형식
        temps = hourly["temperature_2m"]
        codes = hourly["weather_code"]
        pops = hourly["precipitation_probability"]

        hour_indices = list(range(0, len(times), 3))
        # 행 개수만큼 나눠서 각 행 높이를 고정해두면, 캘린더와 같은 높이(282px) 안에
        # 빈 공간 없이 딱 채워짐 (padding만으로는 이모지/줄바꿈에 따라 실제 높이가
        # 들쭉날쭉해서 box-sizing:border-box + 고정 height로 맞춤).
        row_height = CALENDAR_WRAP_HEIGHT / len(hour_indices)

        hour_rows = ""
        for i in hour_indices:
            hour_only = times[i].split("T")[1][:2] + "시"
            hour_rows += f"""
<div style="display:flex; justify-content:space-between; align-items:center; height:{row_height}px; box-sizing:border-box; padding:0 8px; border-bottom:1px solid #f0f0f0; font-size:12px;">
    <span style="color:#666; width:32px;">{hour_only}</span>
    <span style="font-size:15px;">{weather_emoji(codes[i])}</span>
    <span style="font-weight:600; width:38px; text-align:right;">{temps[i]}℃</span>
    <span style="color:#4a90d9; width:48px; display:inline-flex; justify-content:flex-end; gap:2px;">
        <span>💧</span><span style="width:26px; text-align:right;">{pops[i]}%</span>
    </span>
</div>
"""
        st.markdown(
            f'<div style="border:1px solid #eee; border-radius:6px; '
            f'width:50%; height:{CALENDAR_WRAP_HEIGHT}px; overflow:hidden; box-sizing:border-box;">{hour_rows}</div>',
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.markdown("🌡️ **날씨 정보를 불러오지 못했습니다.**")
        st.caption(f"(오류 상세: {e})")  # 원인 파악용 - 문제 없으면 나중에 지워도 됨

with outer_left:
    st.markdown("📌 **카테고리 선택**")

    cat_items = list(CATEGORIES.items())
    for row_start in range(0, len(cat_items), 5):  # 5개씩 2줄로 배치
        row = cat_items[row_start:row_start + 5]
        cols = st.columns(5)
        for col, (label, query) in zip(cols, row):
            if col.button(label, use_container_width=True):
                st.session_state.keyword = query
                st.session_state.label = label
                st.session_state.naver_target_total = 100
                st.session_state.nfinance_target_total = 100

st.write("---")

# 3. 구글 뉴스 RSS 연동에 필요한 함수 정의


def format_pubdate(raw: str) -> str:
    """RFC822 형식(pubDate)을 'YYYY-MM-DD HH:MM' 형태로 변환. 실패 시 원문 그대로 반환."""
    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return raw


@st.cache_data(ttl=300)  # 5분 캐시
def fetch_naver_finance_news(target_total: int = 100):
    """네이버 금융의 '실시간속보'(증권/시황 전문) 뉴스 목록을 스크래핑한다.
    한국어라 번역이 필요 없고, 제목/언론사/정확한 시각까지 페이지에 이미 다 있음.
    공식 API가 아니라 페이지 구조에 의존 - 네이버가 마크업을 바꾸면 이 파싱이 깨질 수 있음.
    page 파라미터가 새 기사를 순차적으로 주는 게 아니라 최근 기사들을 뒤섞어 반복해서 보여주는
    방식이라, 여러 페이지를 모아 링크 기준 중복 제거해가며 target_total개가 모일 때까지 이어붙인다.
    페이지를 계속 넘겨도 새 기사가 하나도 안 나오면(그 시점의 '실시간속보' 목록이 바닥난 것)
    조기 종료한다. 검색어 없이 네이버가 자체 선정한 목록이라, 카테고리 선택과 무관하게 항상
    같은 목록을 준다."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }
    base_url = "https://finance.naver.com"
    news_list = []
    seen_links = set()
    max_pages = (target_total // 20 + 2) * 2  # 페이지당 대략 20개씩 오므로 넉넉히 상한을 둠
    for page in range(1, max_pages + 1):
        if len(news_list) >= target_total:
            break
        before_count = len(news_list)
        res = requests.get(
            f"{base_url}/news/news_list.naver",
            params={"mode": "LSS2D", "section_id": 101, "section_id2": 258, "page": page},
            headers=headers, timeout=10,
        )
        res.raise_for_status()
        res.encoding = "euc-kr"
        soup = BeautifulSoup(res.text, "html.parser")

        for subject_dd in soup.select("dd.articleSubject"):
            a = subject_dd.find("a")
            if not a or not a.get("href"):
                continue
            link = base_url + a["href"]
            if link in seen_links:
                continue
            seen_links.add(link)

            summary_dd = subject_dd.find_next_sibling("dd", class_="articleSummary")
            press_el = summary_dd.select_one(".press") if summary_dd else None
            wdate_el = summary_dd.select_one(".wdate") if summary_dd else None

            news_list.append({
                "title": a.get_text(strip=True),
                "link": link,
                "pub_date": wdate_el.get_text(strip=True) if wdate_el else "",
                "source": press_el.get_text(strip=True) if press_el else "",
                "desc": "",
            })

        if len(news_list) == before_count:
            break  # 이 페이지에서 새 기사가 하나도 없었음 - 더 넘겨도 소용없으므로 중단

    news_list.sort(key=lambda x: x["pub_date"], reverse=True)
    return news_list[:target_total]


try:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
except Exception:
    # secrets.toml이 없는 환경(예: 남이 이 repo를 클론한 경우)에서도 앱 전체가
    # 죽지 않도록 조용히 빈 값으로 처리 - 네이버 쪽만 "키 없음" 안내로 대체됨
    NAVER_CLIENT_ID = ""
    NAVER_CLIENT_SECRET = ""


def clean_naver_html(text: str) -> str:
    """네이버 검색 API의 title/description은 검색어 강조용 <b> 태그가 섞여 있고
    나머지 특수문자는 HTML 엔티티(&quot; 등)로 이스케이프돼 있다. 전체를 다시
    이스케이프한 뒤 <b> 태그만 살려서, 강조 표시는 유지하되 다른 HTML 삽입은 막는다."""
    text = html.unescape(text)
    text = html.escape(text)
    return text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")


@st.cache_data(ttl=300, show_spinner=False)  # 5분 캐시
def fetch_naver_news(query: str, target_total: int = 100):
    """NAVER API HUB의 뉴스 검색 API에서 키워드 관련 뉴스를 가져온다.
    한 번 호출에 최대 100개까지만 주므로(display 파라미터 상한), target_total을 늘리면
    start를 1→101→201로 옮겨가며 여러 번 호출해서 이어붙인다(지금은 100개라 호출 1번).
    (검색 결과가 그보다 적으면 API가 빈 배열을 줘서 자동으로 멈춤)"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET,
    }

    news_list = []
    for start in range(1, target_total + 1, 100):
        params = {
            "query": query,
            "display": min(100, target_total - start + 1),
            "start": start,
            "sort": "date",
            "format": "json",
        }
        res = requests.get(
            "https://naverapihub.apigw.ntruss.com/search/v1/news",
            params=params, headers=headers, timeout=10,
        )
        res.raise_for_status()
        page_items = res.json().get("items", [])
        if not page_items:
            break  # 더 이상 결과 없음 - 조기 종료

        for item in page_items:
            raw_link = item.get("originallink") or item.get("link") or "#"
            source = urlparse(raw_link).netloc.replace("www.", "")
            news_list.append({
                "title": clean_naver_html(item.get("title", "")),
                "link": raw_link,
                "pub_date": format_pubdate(item.get("pubDate", "")),
                "source": source,
                "desc": clean_naver_html(item.get("description", "")),
            })
    return news_list


def render_card_list(items, title_is_html: bool):
    """뉴스 카드 목록만 그린다 ('더보기' 버튼은 호출부에서 각자 다르게 처리).
    title_is_html=True면 title을 (clean_naver_html로 이미 이스케이프된) HTML로 그대로 쓰고,
    False면 새로 이스케이프한다."""
    if not items:
        st.warning("검색된 뉴스가 없습니다.")
        return

    cards_html = ""
    for i, item in enumerate(items, start=1):
        meta = " | ".join(filter(None, [item["source"], item["pub_date"]]))
        title_html = item["title"] if title_is_html else html.escape(item["title"])
        cards_html += f"""
<div style="border:1px solid #e0e0e0; border-radius:6px; padding:6px 12px; margin-bottom:4px; display:flex; align-items:baseline; gap:8px; flex-wrap:wrap;">
    <span style="font-size:13px; color:#aaa; font-weight:600; min-width:1.6em;">{i}.</span>
    <a href="{item['link']}" target="_blank"
       style="font-size:16px; font-weight:600; text-decoration:none; line-height:1.3;">
        {title_html}
    </a>
    <span style="font-size:13px; color:#888; white-space:nowrap;">{html.escape(meta)}</span>
</div>
"""
    st.markdown(cards_html, unsafe_allow_html=True)


# 4. 뉴스 표시: 왼쪽엔 네이버 뉴스(검색), 오른쪽엔 네이버 금융(증권 전문)
if st.session_state.keyword:
    if st.session_state.keyword == ALL_QUERY:
        header_text = "전체 최신 뉴스"
        naver_query = "속보"  # 네이버 검색 API는 검색어가 필수라, '전체'/'주요'엔 대체 검색어를 씀
    elif st.session_state.keyword == MAIN_QUERY:
        header_text = "주요 뉴스"
        naver_query = "속보"
    else:
        header_text = f"'{st.session_state.label}' 관련 최신 뉴스"
        naver_query = st.session_state.keyword

    try:
        naver_items = fetch_naver_news(naver_query, target_total=st.session_state.naver_target_total)
    except requests.exceptions.RequestException as e:
        naver_items = []
        st.error(f"네이버 뉴스를 불러오는 중 오류가 발생했습니다: {e}")

    # 네이버 금융은 검색어 없이 자체 선정한 증권/시황 목록을 주는 구조라, 카테고리
    # 선택과 무관하게 항상 같은 목록을 보여줌
    try:
        nfinance_items = fetch_naver_finance_news(target_total=st.session_state.nfinance_target_total)
    except requests.exceptions.RequestException as e:
        nfinance_items = []
        st.error(f"네이버 금융 뉴스를 불러오는 중 오류가 발생했습니다: {e}")

    naver_col, nfinance_col = st.columns(2)
    with naver_col:
        st.subheader(f"🟢 네이버 - {header_text}")
        if not NAVER_CLIENT_ID:
            st.info("네이버 API 키가 설정되지 않았습니다 (.streamlit/secrets.toml 확인).")
        else:
            render_card_list(naver_items, title_is_html=True)
            # len(naver_items)가 요청한 target_total만큼 꽉 찼다는 건 더 있을 수도 있다는 뜻.
            # 그보다 적게 왔다면 API가 이미 바닥까지 준 것이므로 버튼을 숨김.
            if len(naver_items) >= st.session_state.naver_target_total:
                if st.button("더보기 (100개 더 가져오기)", key="naver_more", use_container_width=True):
                    st.session_state.naver_target_total += 100
                    st.rerun()
    with nfinance_col:
        st.subheader("🟠 네이버 금융 - 증권 뉴스")
        render_card_list(nfinance_items, title_is_html=False)
        # 페이지네이션이 도중에 바닥나면(더 이상 새 기사가 없으면) 요청한 개수보다 적게 오므로,
        # 그럴 땐 버튼을 숨김 (naver_col과 동일한 방식)
        if len(nfinance_items) >= st.session_state.nfinance_target_total:
            if st.button("더보기 (100개 더 가져오기)", key="nfinance_more", use_container_width=True):
                st.session_state.nfinance_target_total += 100
                st.rerun()
else:
    st.write("상단 버튼을 누르거나 키워드를 입력해 뉴스를 검색해 보세요.")
