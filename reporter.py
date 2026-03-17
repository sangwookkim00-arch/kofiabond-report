"""
reporter.py - 국고채 10년물 데이터 분석 및 HTML 리포트 생성 모듈

왜 이렇게 짰는가:
- 이메일로 보내기 좋게 HTML 테이블 형식으로 데이터를 정리
- 색상 강조(말일 금리, 평균 대비 현재 수준)로 한눈에 파악 가능하게 함
"""

import pandas as pd
from datetime import date
from typing import Optional


def calculate_stats(data: dict) -> dict:
    """
    수집된 데이터에서 핵심 통계를 계산합니다.
    
    반환:
        - last_business_day: 전월 마지막 영업일
        - last_rate: 전월 말일 기준 금리 (%)
        - monthly_avg: 전월 평균 금리
        - three_year_avg: 3년 평균 금리
        - three_year_min: 3년 최저 금리
        - three_year_max: 3년 최고 금리
    """
    monthly_df: pd.DataFrame = data["monthly"]
    three_year_df: pd.DataFrame = data["three_year"]
    
    stats = {}
    
    if not monthly_df.empty:
        last_row = monthly_df.iloc[-1]
        stats["last_business_day"] = last_row["날짜"].strftime("%Y-%m-%d")
        stats["last_rate"] = last_row["국고채10Y"]
        stats["monthly_avg"] = round(monthly_df["국고채10Y"].mean(), 4)
        stats["monthly_min"] = monthly_df["국고채10Y"].min()
        stats["monthly_max"] = monthly_df["국고채10Y"].max()
    else:
        stats["last_business_day"] = "N/A"
        stats["last_rate"] = None
        stats["monthly_avg"] = None
        stats["monthly_min"] = None
        stats["monthly_max"] = None
    
    if not three_year_df.empty:
        stats["three_year_avg"] = round(three_year_df["국고채10Y"].mean(), 4)
        stats["three_year_min"] = three_year_df["국고채10Y"].min()
        stats["three_year_max"] = three_year_df["국고채10Y"].max()
    else:
        stats["three_year_avg"] = None
        stats["three_year_min"] = None
        stats["three_year_max"] = None
    
    return stats


def format_rate_color(rate: Optional[float], avg: Optional[float]) -> str:
    """
    평균 대비 현재 금리의 색상 코드를 반환합니다.
    - 평균보다 높으면 빨간색 (금리 상승)
    - 평균보다 낮으면 파란색 (금리 하락)
    - 같으면 검정색
    """
    if rate is None or avg is None:
        return "#333333"
    if rate > avg:
        return "#C0392B"  # 빨간색
    elif rate < avg:
        return "#2980B9"  # 파란색
    return "#333333"


def build_html_report(data: dict) -> str:
    """
    수집된 데이터를 기반으로 HTML 이메일 본문을 생성합니다.
    """
    monthly_df: pd.DataFrame = data["monthly"]
    prev_start: date = data["prev_month_start"]
    prev_end: date = data["prev_month_end"]
    three_start: date = data["three_year_start"]
    
    stats = calculate_stats(data)
    
    # 전월 연/월 텍스트
    prev_month_label = prev_end.strftime("%Y년 %m월")
    three_year_label = f"{three_start.strftime('%Y-%m')} ~ {prev_end.strftime('%Y-%m')}"
    
    # 금리 색상
    last_rate_color = format_rate_color(stats.get("last_rate"), stats.get("three_year_avg"))
    
    # 일별 테이블 HTML 생성
    daily_rows_html = ""
    if not monthly_df.empty:
        for _, row in monthly_df.iterrows():
            date_str = row["날짜"].strftime("%Y-%m-%d")
            rate = row["국고채10Y"]
            # 말일(마지막 행)은 강조 표시
            is_last = (row["날짜"] == monthly_df["날짜"].max())
            bg_color = "#FFF9C4" if is_last else "white"
            font_weight = "bold" if is_last else "normal"
            daily_rows_html += f"""
            <tr style="background-color:{bg_color};">
                <td style="padding:6px 12px; font-weight:{font_weight};">{date_str}</td>
                <td style="padding:6px 12px; text-align:right; font-weight:{font_weight};">{rate:.4f}%</td>
            </tr>"""
    
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Malgun Gothic', 맑은고딕, Arial, sans-serif; color: #333; background: #f5f5f5; }}
    .container {{ max-width: 700px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #1a237e, #283593); color: white; padding: 24px 32px; }}
    .header h1 {{ margin: 0; font-size: 22px; }}
    .header p {{ margin: 6px 0 0; font-size: 13px; opacity: 0.85; }}
    .section {{ padding: 20px 32px; border-bottom: 1px solid #eee; }}
    .section-title {{ font-size: 16px; font-weight: bold; color: #1a237e; margin-bottom: 14px; }}
    .stat-box {{ display: inline-block; background: #f8f9ff; border: 1px solid #c5cae9; border-radius: 6px; padding: 12px 24px; margin-right: 12px; margin-bottom: 8px; text-align: center; }}
    .stat-label {{ font-size: 12px; color: #666; }}
    .stat-value {{ font-size: 24px; font-weight: bold; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th {{ background: #283593; color: white; padding: 8px 12px; text-align: left; }}
    tr:nth-child(even) {{ background: #f5f5f5; }}
    .footer {{ padding: 16px 32px; font-size: 12px; color: #999; text-align: center; }}
  </style>
</head>
<body>
<div class="container">

  <!-- 헤더 -->
  <div class="header">
    <h1>📊 국고채 10년물 금리 현황</h1>
    <p>{prev_month_label} 기준 | 출처: 코피아본드(KofiaBond) 장외거래대표수익률</p>
  </div>

  <!-- 핵심 지표 -->
  <div class="section">
    <div class="section-title">📌 핵심 지표</div>
    <div class="stat-box">
      <div class="stat-label">📅 전월 말일 기준 ({stats.get('last_business_day', 'N/A')})</div>
      <div class="stat-value" style="color:{last_rate_color};">
        {f"{stats['last_rate']:.4f}%" if stats.get('last_rate') is not None else 'N/A'}
      </div>
    </div>
    <div class="stat-box">
      <div class="stat-label">전월 평균</div>
      <div class="stat-value" style="color:#2c3e50;">
        {f"{stats['monthly_avg']:.4f}%" if stats.get('monthly_avg') is not None else 'N/A'}
      </div>
    </div>
    <div class="stat-box">
      <div class="stat-label">3년 평균 ({three_year_label})</div>
      <div class="stat-value" style="color:#27ae60;">
        {f"{stats['three_year_avg']:.4f}%" if stats.get('three_year_avg') is not None else 'N/A'}
      </div>
    </div>
  </div>

  <!-- 전월 범위 -->
  <div class="section">
    <div class="section-title">📉 전월 금리 범위</div>
    <table>
      <tr>
        <th>항목</th><th>금리 (%)</th>
      </tr>
      <tr>
        <td style="padding:7px 12px;">전월 최고</td>
        <td style="padding:7px 12px; text-align:right; color:#C0392B; font-weight:bold;">
          {f"{stats['monthly_max']:.4f}%" if stats.get('monthly_max') is not None else 'N/A'}
        </td>
      </tr>
      <tr>
        <td style="padding:7px 12px;">전월 말일 (기준값)</td>
        <td style="padding:7px 12px; text-align:right; font-weight:bold; color:{last_rate_color};">
          {f"{stats['last_rate']:.4f}%" if stats.get('last_rate') is not None else 'N/A'}
        </td>
      </tr>
      <tr>
        <td style="padding:7px 12px;">전월 최저</td>
        <td style="padding:7px 12px; text-align:right; color:#2980B9; font-weight:bold;">
          {f"{stats['monthly_min']:.4f}%" if stats.get('monthly_min') is not None else 'N/A'}
        </td>
      </tr>
      <tr style="background:#f8f9ff;">
        <td style="padding:7px 12px;">3년 최고</td>
        <td style="padding:7px 12px; text-align:right; color:#922B21;">
          {f"{stats['three_year_max']:.4f}%" if stats.get('three_year_max') is not None else 'N/A'}
        </td>
      </tr>
      <tr style="background:#f8f9ff;">
        <td style="padding:7px 12px;">3년 최저</td>
        <td style="padding:7px 12px; text-align:right; color:#1A5276;">
          {f"{stats['three_year_min']:.4f}%" if stats.get('three_year_min') is not None else 'N/A'}
        </td>
      </tr>
    </table>
  </div>

  <!-- 전월 일별 상세 -->
  <div class="section">
    <div class="section-title">📅 {prev_month_label} 일별 국고채 10년물 금리</div>
    <table>
      <tr>
        <th>영업일</th>
        <th style="text-align:right;">국고채 10년물 (%)</th>
      </tr>
      {daily_rows_html}
    </table>
    <p style="font-size:12px; color:#999; margin-top:8px;">※ 노란 음영: 전월 말일(기준값) | 영업일 기준</p>
  </div>

  <div class="footer">
    본 리포트는 코피아본드(www.kofiabond.or.kr) 장외거래대표수익률 데이터를 기반으로 자동 생성되었습니다.<br>
    생성일시: {date.today().strftime('%Y-%m-%d')}
  </div>

</div>
</body>
</html>"""
    
    return html


def build_text_report(data: dict) -> str:
    """
    텍스트 형식의 간단한 리포트를 생성합니다 (이메일 대체 텍스트용).
    """
    monthly_df: pd.DataFrame = data["monthly"]
    prev_end: date = data["prev_month_end"]
    three_start: date = data["three_year_start"]
    
    stats = calculate_stats(data)
    prev_month_label = prev_end.strftime("%Y년 %m월")
    three_year_label = "{} ~ {}".format(
        three_start.strftime("%Y-%m"), prev_end.strftime("%Y-%m")
    )
    
    # f-string 중첩 이스케이프 문제를 피하기 위해 미리 변수에 담음
    last_bd = stats.get("last_business_day", "N/A")
    last_rate_str = f"{stats['last_rate']:.4f}%" if stats.get("last_rate") is not None else "N/A"
    monthly_avg_str = f"{stats['monthly_avg']:.4f}%" if stats.get("monthly_avg") is not None else "N/A"
    three_avg_str = f"{stats['three_year_avg']:.4f}%" if stats.get("three_year_avg") is not None else "N/A"
    
    lines = [
        f"[국고채 10년물 금리 현황] {prev_month_label} 기준",
        "=" * 50,
        "",
        f"▶ 전월 말일 기준 ({last_bd}): {last_rate_str}",
        f"▶ 전월 평균: {monthly_avg_str}",
        f"▶ 3년 평균 ({three_year_label}): {three_avg_str}",
        "",
        f"=== {prev_month_label} 일별 국고채 10년물 금리 ===",
        f"{'영업일':<14} {'금리(%)':<10}",
        "-" * 26,
    ]
    
    if not monthly_df.empty:
        for _, row in monthly_df.iterrows():
            date_str = row["날짜"].strftime("%Y-%m-%d")
            rate = row["국고채10Y"]
            lines.append(f"{date_str:<14} {rate:.4f}%")
    
    lines.append("")
    lines.append("출처: 코피아본드(www.kofiabond.or.kr) 장외거래대표수익률")
    
    return "\n".join(lines)
