"""
건설안전 뉴스레터 자동 발송 시스템

실행 방법:
  python main.py          # 스케줄러 시작 (매주 월요일 09:00 자동 발송)
  python main.py --now    # 즉시 한 번 실행 (테스트 / 수동 발송)
"""

import argparse
import logging
import sys
import time

import schedule

from config import Config
from crawler import crawl_all
from mailer import send_newsletter
from newsletter import build_newsletter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run_job() -> None:
    """뉴스 수집 → 뉴스레터 생성 → 이메일 발송 파이프라인."""
    cfg = Config()

    logger.info("=" * 60)
    logger.info("건설안전 뉴스레터 파이프라인 시작")
    logger.info("=" * 60)

    # 1. 크롤링
    logger.info("▶ 뉴스 수집 중 (최근 %d개월)...", cfg.CRAWL_MONTHS)
    articles = crawl_all(months=cfg.CRAWL_MONTHS, top_n=cfg.TOP_NEWS_COUNT)

    if not articles:
        logger.warning("수집된 기사가 없습니다. 발송을 중단합니다.")
        return

    logger.info("▶ 총 %d건 수집 완료 (조회수 내림차순 정렬)", len(articles))
    for i, a in enumerate(articles, 1):
        view_info = f"조회수 {a.view_count:,}" if a.view_count > 0 else "조회수 없음"
        logger.info(
            "  %2d위 | %-8s | %s | %s | %s",
            i,
            a.source,
            a.date.strftime("%Y-%m-%d"),
            view_info,
            a.title[:40],
        )

    # 2. 뉴스레터 HTML 생성
    logger.info("▶ 뉴스레터 HTML 생성 중...")
    html_body, plain_body = build_newsletter(articles, months=cfg.CRAWL_MONTHS)

    # 3. 이메일 발송
    logger.info("▶ 이메일 발송 중 → %s", ", ".join(cfg.RECIPIENT_EMAILS))
    success = send_newsletter(html_body, plain_body)

    if success:
        logger.info("✓ 뉴스레터 발송 성공!")
    else:
        logger.error("✗ 뉴스레터 발송 실패. 로그를 확인하세요.")


def start_scheduler() -> None:
    cfg = Config()
    schedule_time = cfg.SCHEDULE_TIME  # 기본값 "09:00"

    schedule.every().monday.at(schedule_time).do(run_job)

    logger.info(
        "스케줄러 시작 — 매주 월요일 %s에 자동 발송됩니다. (Ctrl+C로 종료)",
        schedule_time,
    )

    while True:
        schedule.run_pending()
        time.sleep(60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="건설안전 뉴스레터 자동 발송 시스템"
    )
    parser.add_argument(
        "--now",
        action="store_true",
        help="즉시 한 번 실행 (테스트 / 수동 발송)",
    )
    args = parser.parse_args()

    if args.now:
        run_job()
    else:
        start_scheduler()


if __name__ == "__main__":
    main()
