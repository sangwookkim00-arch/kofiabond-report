"""
emailer.py - 국고채 10년물 리포트 이메일 발송 모듈

왜 이렇게 짰는가:
- Gmail SMTP (SSL 465포트)를 사용하여 HTML 이메일을 발송
- 환경 변수(또는 .env 파일)에서 계정 정보를 읽어 보안을 유지
- HTML + 텍스트 대체본(multipart/alternative)을 함께 첨부하여 호환성 확보
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()


def get_email_config() -> dict:
    """
    환경 변수에서 이메일 설정을 읽어옵니다.
    필수 변수가 없으면 ValueError를 발생시킵니다.
    """
    config = {
        "sender_email": os.getenv("SENDER_EMAIL"),
        "sender_password": os.getenv("SENDER_PASSWORD"),
        # 쉼표로 구분된 수신자 목록을 리스트로 변환
        "receiver_emails": [
            e.strip() for e in os.getenv("RECEIVER_EMAIL", "").split(",") if e.strip()
        ],
        "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", "465")),
    }
    
    # 필수 값 검증
    missing = []
    if not config["sender_email"]:
        missing.append("SENDER_EMAIL")
    if not config["sender_password"]:
        missing.append("SENDER_PASSWORD")
    if not config["receiver_emails"]:
        missing.append("RECEIVER_EMAIL")
    if missing:
        raise ValueError(
            f"이메일 설정 누락: {missing}\n"
            ".env 파일에 SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL을 설정하세요."
        )
    
    return config


def build_email_subject(prev_month_end: date) -> str:
    """
    이메일 제목을 생성합니다.
    예: [국고채 10년물] 2026년 02월 금리 현황 리포트
    """
    return f"[국고채 10년물] {prev_month_end.strftime('%Y년 %m월')} 금리 현황 리포트"


def send_report_email(
    html_content: str,
    text_content: str,
    prev_month_end: date,
    dry_run: bool = False
) -> bool:
    """
    HTML 리포트를 이메일로 발송합니다.
    
    매개변수:
        html_content: HTML 형식의 이메일 본문
        text_content: 텍스트 형식의 대체 본문 (HTML 미지원 클라이언트용)
        prev_month_end: 전월 말일 (제목 생성에 사용)
        dry_run: True이면 실제 발송 없이 내용만 출력 (테스트용)
    
    반환:
        True: 발송 성공 / False: 발송 실패
    """
    try:
        config = get_email_config()
    except ValueError as e:
        print(f"❌ [이메일 설정 오류] {e}")
        return False
    
    subject = build_email_subject(prev_month_end)
    
    # dry_run 모드: 실제 발송 없이 미리보기만
    if dry_run:
        receivers_str = ", ".join(config['receiver_emails'])
        print("\n" + "=" * 60)
        print("[DRY RUN] 이메일 미리보기")
        print(f"From: {config['sender_email']}")
        print(f"To: {receivers_str}")
        print(f"Subject: {subject}")
        print("=" * 60)
        print("[텍스트 본문]")
        print(text_content)
        print("=" * 60)
        print("DRY RUN 완료 - 실제 이메일은 발송되지 않았습니다.")
        return True
    
    # 이메일 메시지 구성 (multipart/alternative: HTML + 텍스트 대체본)
    receivers_list = config["receiver_emails"]
    receivers_str = ", ".join(receivers_list)
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["sender_email"]
    msg["To"] = receivers_str  # 헤더에는 전체 수신자 표시
    
    # 텍스트 대체본 첨부 (먼저 추가, HTML이 우선 표시됨)
    part_text = MIMEText(text_content, "plain", "utf-8")
    part_html = MIMEText(html_content, "html", "utf-8")
    msg.attach(part_text)
    msg.attach(part_html)
    
    # Gmail SMTP SSL로 발송
    try:
        print(f"이메일 발송 중... ({config['sender_email']} → {receivers_str})")
        with smtplib.SMTP_SSL(config["smtp_host"], config["smtp_port"]) as server:
            server.login(config["sender_email"], config["sender_password"])
            server.sendmail(
                config["sender_email"],
                receivers_list,  # 리스트로 전달해야 여러 명에게 발송
                msg.as_string()
            )
        print(f"이메일 발송 성공! 제목: {subject}")
        print(f"수신자 ({len(receivers_list)}명): {receivers_str}")
        return True
    
    except smtplib.SMTPAuthenticationError:
        print("❌ [발송 실패] Gmail 인증 오류. 앱 비밀번호를 확인하세요.")
        print("   → Google 계정 > 보안 > 2단계 인증 > 앱 비밀번호 생성")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ [발송 실패] SMTP 오류: {e}")
        return False
    except Exception as e:
        print(f"❌ [발송 실패] 예상치 못한 오류: {e}")
        return False
