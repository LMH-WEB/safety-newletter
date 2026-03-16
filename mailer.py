"""
SMTP 이메일 발송 모듈 (Gmail / 일반 SMTP 지원)
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import Config

logger = logging.getLogger(__name__)


def send_newsletter(html_body: str, plain_body: str) -> bool:
    """
    HTML + 평문 멀티파트 뉴스레터 이메일을 발송합니다.
    성공 시 True, 실패 시 False 반환.
    """
    cfg = Config()

    if not cfg.SMTP_USER or not cfg.SMTP_PASSWORD:
        logger.error("SMTP 계정 정보가 설정되지 않았습니다. .env 파일을 확인하세요.")
        return False

    if not cfg.RECIPIENT_EMAILS:
        logger.error("수신자 이메일이 설정되지 않았습니다.")
        return False

    subject = f"[건설안전 뉴스레터] {datetime.now().strftime('%Y년 %m월 %d일')} 주간 뉴스"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.SENDER_EMAIL
    msg["To"] = ", ".join(cfg.RECIPIENT_EMAILS)

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
            server.sendmail(
                cfg.SENDER_EMAIL,
                cfg.RECIPIENT_EMAILS,
                msg.as_bytes(),
            )
        logger.info(
            "뉴스레터 발송 완료 → %s", ", ".join(cfg.RECIPIENT_EMAILS)
        )
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "SMTP 인증 실패. Gmail 사용 시 앱 비밀번호를 사용하세요.\n"
            "앱 비밀번호 발급: https://myaccount.google.com/apppasswords"
        )
    except smtplib.SMTPException as exc:
        logger.error("SMTP 오류: %s", exc)
    except Exception as exc:
        logger.error("이메일 발송 중 예외 발생: %s", exc)

    return False
