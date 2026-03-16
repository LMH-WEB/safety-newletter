import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "")
    RECIPIENT_EMAILS: list[str] = [
        e.strip()
        for e in os.getenv("RECIPIENT_EMAILS", "").split(",")
        if e.strip()
    ]
    CRAWL_MONTHS: int = int(os.getenv("CRAWL_MONTHS", "3"))
    TOP_NEWS_COUNT: int = int(os.getenv("TOP_NEWS_COUNT", "15"))
    SCHEDULE_DAY: str = "monday"
    SCHEDULE_TIME: str = "09:00"
