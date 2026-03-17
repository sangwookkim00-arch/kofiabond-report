"""
main.py - 국고채 10년물 자동 리포트 발송 메인 실행 파일

사용법:
    python main.py              # 실제 이메일 발송
    python main.py --dry-run    # 이메일 발송 없이 콘솔 출력만

GitHub Actions에서 매월 초 자동 실행됩니다.
"""

import asyncio
import sys
# Windows cp949 터미널 한글/이모지 깨짐 방지
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from fetcher import fetch_all_data
from reporter import build_html_report, build_text_report
from emailer import send_report_email


async def run(dry_run: bool = False):
    """
    전체 파이프라인을 실행합니다:
    1. 코피아본드에서 국고채 10년물 데이터 수집
    2. 리포트 생성 (HTML + 텍스트)
    3. 이메일 발송
    """
    print("=" * 60)
    print("[START] 국고채 10년물 자동 리포트 시작")
    print("=" * 60)
    
    # Step 1: 데이터 수집
    print("\n[1/3] 코피아본드 데이터 수집 중...")
    try:
        data = await fetch_all_data()
    except Exception as e:
        print(f"[ERROR] 데이터 수집 실패: {e}")
        sys.exit(1)
    
    monthly_df = data["monthly"]
    three_year_df = data["three_year"]
    
    if monthly_df.empty:
        print("[WARN] 전월 데이터가 없습니다. 영업일이 없는 달이거나 사이트 오류일 수 있습니다.")
        sys.exit(1)
    
    print(f"  [OK] 전월 데이터: {len(monthly_df)}건")
    print(f"  [OK] 3년 데이터: {len(three_year_df)}건")
    
    # Step 2: 리포트 생성
    print("\n[2/3] 리포트 생성 중...")
    html_report = build_html_report(data)
    text_report = build_text_report(data)
    print("  [OK] HTML/텍스트 리포트 생성 완료")
    
    # Step 3: 이메일 발송
    mode_label = "DRY RUN (발송 없음)" if dry_run else "발송"
    print(f"\n[3/3] 이메일 {mode_label} 중...")
    success = send_report_email(
        html_content=html_report,
        text_content=text_report,
        prev_month_end=data["prev_month_end"],
        dry_run=dry_run
    )
    
    if success:
        print("\n[DONE] 전체 프로세스 완료!")
    else:
        print("\n[ERROR] 이메일 발송 실패. 설정을 확인하세요.")
        sys.exit(1)


def main():
    # 명령줄 인수 파싱
    dry_run = "--dry-run" in sys.argv
    
    if dry_run:
        print("[DRY RUN] 이메일이 실제로 발송되지 않습니다.")
    
    asyncio.run(run(dry_run=dry_run))


if __name__ == "__main__":
    main()
