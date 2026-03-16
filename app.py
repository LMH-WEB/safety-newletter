"""
건설안전 뉴스레터 — Flask 웹 대시보드

실행: python app.py
접속: http://localhost:5000
"""

import json
import logging
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import schedule
from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

from config import Config
from crawler import crawl_all
from mailer import send_newsletter
from newsletter import build_newsletter

# ---------------------------------------------------------------------------
# 앱 초기화
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = "safety-newsletter-secret"

ENV_PATH = Path(__file__).parent / ".env"

# ---------------------------------------------------------------------------
# 전역 상태
# ---------------------------------------------------------------------------
from typing import Any
_state: dict[str, Any] = {
    "articles": [],          # 마지막으로 수집된 기사 목록
    "last_sent": None,       # 마지막 발송 시각 (datetime)
    "scheduler_on": False,   # 스케줄러 실행 여부
    "job_running": False,    # 현재 파이프라인 실행 중 여부
}

# SSE 로그를 구독자들에게 전달하는 큐 목록
_log_queues: list[queue.Queue] = []
_log_lock = threading.Lock()


# ---------------------------------------------------------------------------
# 로깅 설정 — SSE 핸들러
# ---------------------------------------------------------------------------
class SSELogHandler(logging.Handler):
    """로그 레코드를 SSE 구독자 큐에 넣는 핸들러."""

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        level = record.levelname
        with _log_lock:
            for q in list(_log_queues):
                try:
                    q.put_nowait({"msg": msg, "level": level})
                except queue.Full:
                    pass


_sse_handler = SSELogHandler()
_sse_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger().addHandler(_sse_handler)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 파이프라인 (크롤링 → 뉴스레터 → 발송)
# ---------------------------------------------------------------------------
def run_pipeline(send: bool = True) -> None:
    """뉴스 수집 후 선택적으로 이메일 발송."""
    if _state["job_running"]:
        logger.warning("이미 실행 중입니다.")
        return

    _state["job_running"] = True
    cfg = Config()
    try:
        logger.info("=" * 50)
        logger.info("파이프라인 시작 (send=%s)", send)

        logger.info("▶ 뉴스 수집 중 (최근 %d개월)...", cfg.CRAWL_MONTHS)
        articles = crawl_all(months=cfg.CRAWL_MONTHS, top_n=cfg.TOP_NEWS_COUNT)
        _state["articles"] = articles

        if not articles:
            logger.warning("수집된 기사가 없습니다.")
            return

        logger.info("▶ %d건 수집 완료 (조회수 내림차순)", len(articles))
        for i, a in enumerate(articles, 1):
            view = f"{a.view_count:,}" if a.view_count else "-"
            logger.info("  %2d위 [%s] %s (조회 %s)", i, a.source, a.title[:35], view)

        if send:
            logger.info("▶ 뉴스레터 생성 중...")
            html_body, plain_body = build_newsletter(articles, months=cfg.CRAWL_MONTHS)

            logger.info("▶ 이메일 발송 중 → %s", ", ".join(cfg.RECIPIENT_EMAILS))
            ok = send_newsletter(html_body, plain_body)
            if ok:
                _state["last_sent"] = datetime.now()
                logger.info("✓ 발송 완료!")
            else:
                logger.error("✗ 발송 실패. 설정을 확인하세요.")

        logger.info("파이프라인 종료")
        logger.info("=" * 50)
    except Exception as exc:
        logger.exception("파이프라인 오류: %s", exc)
    finally:
        _state["job_running"] = False


# ---------------------------------------------------------------------------
# 스케줄러
# ---------------------------------------------------------------------------
def _scheduler_loop() -> None:
    while _state["scheduler_on"]:
        schedule.run_pending()
        time.sleep(30)


def start_scheduler() -> None:
    cfg = Config()
    schedule.clear()
    getattr(schedule.every(), cfg.SCHEDULE_DAY).at(cfg.SCHEDULE_TIME).do(
        lambda: threading.Thread(target=run_pipeline, daemon=True).start()
    )
    _state["scheduler_on"] = True
    t = threading.Thread(target=_scheduler_loop, daemon=True)
    t.start()
    logger.info("스케줄러 시작 — 매주 %s %s 자동 발송", cfg.SCHEDULE_DAY, cfg.SCHEDULE_TIME)


def stop_scheduler() -> None:
    _state["scheduler_on"] = False
    schedule.clear()
    logger.info("스케줄러 중지")


# ---------------------------------------------------------------------------
# 라우트
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    cfg = Config()
    next_run = None
    if _state["scheduler_on"] and schedule.jobs:
        next_run = schedule.jobs[0].next_run
    return render_template(
        "index.html",
        articles=_state["articles"],
        last_sent=_state["last_sent"],
        scheduler_on=_state["scheduler_on"],
        next_run=next_run,
        job_running=_state["job_running"],
        cfg=cfg,
    )


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        fields = {
            "SMTP_HOST": request.form.get("smtp_host", ""),
            "SMTP_PORT": request.form.get("smtp_port", "587"),
            "SMTP_USER": request.form.get("smtp_user", ""),
            "SMTP_PASSWORD": request.form.get("smtp_password", ""),
            "SENDER_EMAIL": request.form.get("sender_email", ""),
            "RECIPIENT_EMAILS": request.form.get("recipient_emails", ""),
            "CRAWL_MONTHS": request.form.get("crawl_months", "3"),
            "TOP_NEWS_COUNT": request.form.get("top_news_count", "15"),
        }
        _write_env(fields)
        logger.info("설정 저장 완료")
        return redirect(url_for("settings") + "?saved=1")

    cfg = Config()
    saved = request.args.get("saved") == "1"
    return render_template("settings.html", cfg=cfg, saved=saved)


@app.route("/api/crawl")
def api_crawl():
    """크롤링만 실행 (발송 없음), JSON 반환."""
    def _run():
        run_pipeline(send=False)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/run-now", methods=["POST"])
def api_run_now():
    """크롤링 + 이메일 발송 즉시 실행."""
    threading.Thread(target=run_pipeline, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/preview")
def api_preview():
    """현재 수집된 기사로 뉴스레터 HTML 미리보기."""
    cfg = Config()
    articles = _state["articles"]
    if not articles:
        return "<p style='padding:20px;color:#999'>먼저 뉴스를 수집해 주세요.</p>"
    html, _ = build_newsletter(articles, months=cfg.CRAWL_MONTHS)
    return html


@app.route("/api/status")
def api_status():
    next_run = None
    if _state["scheduler_on"] and schedule.jobs:
        next_run = schedule.jobs[0].next_run.isoformat()
    return jsonify(
        {
            "scheduler_on": _state["scheduler_on"],
            "job_running": _state["job_running"],
            "article_count": len(_state["articles"]),
            "last_sent": _state["last_sent"].isoformat() if _state["last_sent"] else None,
            "next_run": next_run,
        }
    )


@app.route("/api/scheduler/start", methods=["POST"])
def api_scheduler_start():
    start_scheduler()
    return jsonify({"status": "started"})


@app.route("/api/scheduler/stop", methods=["POST"])
def api_scheduler_stop():
    stop_scheduler()
    return jsonify({"status": "stopped"})


@app.route("/api/logs")
def api_logs():
    """Server-Sent Events 스트림으로 실시간 로그 전달."""
    q: queue.Queue = queue.Queue(maxsize=200)
    with _log_lock:
        _log_queues.append(q)

    def generate():
        try:
            while True:
                try:
                    record = q.get(timeout=20)
                    data = json.dumps(record, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            with _log_lock:
                if q in _log_queues:
                    _log_queues.remove(q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------
def _write_env(fields: dict[str, str]) -> None:
    """fields 딕셔너리를 .env 파일에 씁니다 (기존 파일 덮어쓰기)."""
    lines = []
    if ENV_PATH.exists():
        existing = {}
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()
        existing.update(fields)
        fields = existing

    for k, v in fields.items():
        lines.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import os
    start_scheduler()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
