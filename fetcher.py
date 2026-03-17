"""
fetcher.py - 코피아본드(KofiaBond) 국고채 10년물 데이터 수집 모듈

왜 이렇게 짰는가:
- kofiabond.or.kr은 WebSquare 기반의 동적 페이지라 단순 requests로는 불가
- Playwright로 브라우저를 실행해 세션 쿠키를 얻은 뒤, XML POST API를 직접 호출
- 이렇게 하면 속도가 빠르고(브라우저 전체 렌더링 불필요) 안정적
"""

import asyncio
import httpx
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import calendar
import pandas as pd
from playwright.async_api import async_playwright


# 코피아본드 API 엔드포인트
KOFIABOND_BASE_URL = "https://www.kofiabond.or.kr"
API_ENDPOINT = "/proframeWeb/XMLSERVICES/"

# 국고채 10년물 종목 코드 (BISLastAskPrcROPSrchSO 서비스 기준)
BOND_CODE_10Y = "3013"
# 오후 최종 호가 시간 코드
DATA_TIME_CODE = "1530"


def get_last_business_day(year: int, month: int) -> date:
    """
    해당 월의 마지막 영업일을 반환합니다.
    
    단순히 말일에서 역방향으로 토/일을 건너뜁니다.
    공휴일은 고려하지 않습니다(공휴일 API 별도 연동 필요 시 추가).
    """
    last_day = calendar.monthrange(year, month)[1]
    d = date(year, month, last_day)
    # 토요일(5), 일요일(6)이면 이전 평일로 이동
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def get_previous_month_range() -> tuple[date, date]:
    """
    전월의 시작일과 말일을 반환합니다.
    
    예: 현재 2026-03-17 → (2026-02-01, 2026-02-28)
    """
    today = date.today()
    first_of_this_month = today.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    first_of_prev_month = last_of_prev_month.replace(day=1)
    return first_of_prev_month, last_of_prev_month


def get_three_year_range() -> tuple[date, date]:
    """
    3년 전 같은 달 1일부터 전월 말일까지의 범위를 반환합니다.
    
    예: 현재 2026-03-17 → (2023-02-01, 2026-02-28)
    """
    _, end_date = get_previous_month_range()
    start_date = (end_date.replace(day=1) - relativedelta(years=3)).replace(day=1)
    return start_date, end_date


def build_xml_request(start_date: date, end_date: date, bond_code: str = BOND_CODE_10Y) -> str:
    """
    코피아본드 API 요청에 필요한 XML 바디를 생성합니다.
    
    서비스: BISLastAskPrcROPSrchSO (최종호가수익률)
    val1: 조회 단위 (DD=일별)
    val2: 시작일 (YYYYMMDD)
    val3: 종료일 (YYYYMMDD)
    val4: 시간 코드 (1530 = 오후 최종)
    val5: 국고채 10년물 코드 (3013)
    """
    xml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<message>
  <proframeHeader>
    <pfmAppName>BIS-KOFIABOND</pfmAppName>
    <pfmSvcName>BISLastAskPrcROPSrchSO</pfmSvcName>
    <pfmFnName>listTrm</pfmFnName>
  </proframeHeader>
  <systemHeader></systemHeader>
  <BISComDspDatDTO>
    <val1>DD</val1>
    <val2>{start_date.strftime('%Y%m%d')}</val2>
    <val3>{end_date.strftime('%Y%m%d')}</val3>
    <val4>{DATA_TIME_CODE}</val4>
    <val5>{bond_code}</val5>
  </BISComDspDatDTO>
</message>"""
    return xml_body


async def get_session_cookies() -> dict:
    """
    Playwright로 코피아본드 메인 페이지에 접속하여 세션 쿠키를 획득합니다.
    
    왜 필요한가: 서버가 유효한 세션 없이는 API 요청을 거부할 수 있습니다.
    """
    print("  [Playwright] 세션 쿠키 획득 중...")
    cookies = {}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        # 메인 페이지 접속하여 세션 생성
        await page.goto(KOFIABOND_BASE_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        
        # 쿠키 추출
        raw_cookies = await context.cookies()
        for cookie in raw_cookies:
            cookies[cookie["name"]] = cookie["value"]
        
        await browser.close()
    
    print(f"  [Playwright] 쿠키 획득 완료: {list(cookies.keys())}")
    return cookies


def parse_xml_response(xml_text: str) -> list[dict]:
    """
    API 응답 XML을 파싱하여 날짜/수익률 리스트로 변환합니다.
    
    응답 구조:
    - val1: 날짜 (YYYY-MM-DD)
    - val4: 국고채 10년물 수익률 (%)
    (요청 시 val7에 10년물만 넣었으므로 val2가 수익률)
    """
    records = []
    
    try:
        root = ET.fromstring(xml_text)
        # 응답에서 데이터 리스트 찾기
        items = root.findall(".//BISComDspDatDTO")
        
        for item in items:
            val1 = item.findtext("val1", "").strip()  # 날짜
            val2 = item.findtext("val2", "").strip()  # 국고채 10년물 수익률 (단일 항목 조회 시)
            
            # 날짜 행이 아닌 경우 건너뜀 (조회기간평균, 기타 메타 행)
            if not val1 or len(val1) < 8:
                continue
            
            # 빈 값(휴일 등) 건너뜀
            if not val2:
                continue
            
            try:
                rate = float(val2)
                records.append({
                    "날짜": val1,
                    "국고채10Y": rate
                })
            except ValueError:
                continue
    
    except ET.ParseError as e:
        print(f"  [오류] XML 파싱 실패: {e}")
        print(f"  응답 내용 일부: {xml_text[:200]}")
    
    return records


async def fetch_bond_data(start_date: date, end_date: date, cookies: dict) -> pd.DataFrame:
    """
    지정한 기간의 국고채 10년물 데이터를 API로 가져옵니다.
    
    반환: DataFrame (컬럼: 날짜, 국고채10Y)
    """
    xml_body = build_xml_request(start_date, end_date)
    
    headers = {
        "Content-Type": "application/xml; charset=UTF-8",
        "Accept": "application/xml, text/xml, */*",
        "Referer": f"{KOFIABOND_BASE_URL}/",
        "Origin": KOFIABOND_BASE_URL,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    url = f"{KOFIABOND_BASE_URL}{API_ENDPOINT}"
    
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        response = await client.post(
            url,
            content=xml_body.encode("utf-8"),
            headers=headers,
            cookies=cookies
        )
        response.raise_for_status()
    
    records = parse_xml_response(response.text)
    
    if not records:
        print(f"  [경고] {start_date} ~ {end_date} 기간 데이터 없음")
        return pd.DataFrame(columns=["날짜", "국고채10Y"])
    
    df = pd.DataFrame(records)
    df["날짜"] = pd.to_datetime(df["날짜"])
    df = df.sort_values("날짜").reset_index(drop=True)
    
    return df


async def fetch_all_data() -> dict:
    """
    전월 일별 데이터와 3년치 데이터를 모두 가져옵니다.
    
    반환:
        {
            "monthly": DataFrame,   # 전월 일별 데이터
            "three_year": DataFrame, # 최근 3년 데이터
            "prev_month_start": date,
            "prev_month_end": date,
            "three_year_start": date,
        }
    """
    # 날짜 범위 계산
    prev_start, prev_end = get_previous_month_range()
    three_start, three_end = get_three_year_range()
    
    print(f"📅 전월 범위: {prev_start} ~ {prev_end}")
    print(f"📅 3년 범위: {three_start} ~ {three_end}")
    
    # 세션 쿠키 획득
    cookies = await get_session_cookies()
    
    # 전월 데이터 수집
    print("  국고채 10년물 전월 데이터 수집 중...")
    monthly_df = await fetch_bond_data(prev_start, prev_end, cookies)
    print(f"  → {len(monthly_df)}건 수집")
    
    # 3년 데이터 수집 (평균 계산용)
    print("  국고채 10년물 3년 데이터 수집 중...")
    three_year_df = await fetch_bond_data(three_start, three_end, cookies)
    print(f"  → {len(three_year_df)}건 수집")
    
    return {
        "monthly": monthly_df,
        "three_year": three_year_df,
        "prev_month_start": prev_start,
        "prev_month_end": prev_end,
        "three_year_start": three_start,
    }


if __name__ == "__main__":
    # 단독 실행 테스트
    result = asyncio.run(fetch_all_data())
    monthly = result["monthly"]
    three_year = result["three_year"]
    
    print("\n=== 전월 일별 데이터 ===")
    print(monthly.to_string(index=False))
    
    if not three_year.empty:
        avg = three_year["국고채10Y"].mean()
        print(f"\n=== 3년 평균: {avg:.4f}% ===")
