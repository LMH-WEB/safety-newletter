"""
건설안전 뉴스 크롤러
대상 사이트:
  - 안전신문 (safetynews.co.kr)
  - 안전저널 (anjunj.com)
  - 한국산업안전뉴스 (kisnews.net)
"""

import re
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}


@dataclass
class Article:
    title: str
    url: str
    date: datetime
    view_count: int
    summary: str
    source: str


class BaseCrawler(ABC):
    name: str = ""
    base_url: str = ""

    def _get(self, url: str, **kwargs) -> BeautifulSoup | None:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15, **kwargs)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            return BeautifulSoup(resp.text, "lxml")
        except Exception as exc:
            logger.warning("[%s] GET 실패 %s: %s", self.name, url, exc)
            return None

    @staticmethod
    def _parse_date(text: str) -> datetime | None:
        text = text.strip()
        patterns = [
            r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})",
            r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                try:
                    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    pass
        return None

    @staticmethod
    def _parse_view_count(text: str) -> int:
        m = re.search(r"[\d,]+", text.replace(" ", ""))
        if m:
            try:
                return int(m.group().replace(",", ""))
            except ValueError:
                pass
        return 0

    @abstractmethod
    def fetch_articles(self, since: datetime) -> list[Article]:
        ...


# ---------------------------------------------------------------------------
# 안전신문 (safetynews.co.kr)
# ---------------------------------------------------------------------------
class SafetyNewsCrawler(BaseCrawler):
    name = "안전신문"
    base_url = "https://www.safetynews.co.kr"

    # 건설안전 관련 카테고리 목록 URL
    _list_urls = [
        "https://www.safetynews.co.kr/news/articleList.html?sc_section_code=S1N4&view_type=sm",
        "https://www.safetynews.co.kr/news/articleList.html?sc_section_code=S1N3&view_type=sm",
    ]

    def fetch_articles(self, since: datetime) -> list[Article]:
        articles: list[Article] = []
        for list_url in self._list_urls:
            for page in range(1, 6):
                url = f"{list_url}&page={page}"
                soup = self._get(url)
                if not soup:
                    break

                items = soup.select("ul.type2 li, div.list-block li")
                if not items:
                    items = soup.select("li.item")
                if not items:
                    break

                found_old = False
                for item in items:
                    article = self._parse_item(item)
                    if article is None:
                        continue
                    if article.date < since:
                        found_old = True
                        continue
                    articles.append(article)

                if found_old:
                    break
                time.sleep(0.5)

        return articles

    def _parse_item(self, item) -> Article | None:
        title_tag = item.select_one("h4.titles a, .titles a, strong a, h3 a, a.news-titles")
        if not title_tag:
            title_tag = item.select_one("a[href*='articleView']")
        if not title_tag:
            return None

        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        if not href:
            return None
        url = href if href.startswith("http") else self.base_url + href

        # 날짜
        date_tag = item.select_one("span.byline em, .dates, em.info-text")
        date = self._parse_date(date_tag.get_text()) if date_tag else None
        if date is None:
            date = datetime.now()

        # 조회수
        view_count = 0
        for tag in item.select("span, em, li"):
            text = tag.get_text()
            if "조회" in text or "view" in text.lower():
                view_count = self._parse_view_count(text)
                break

        # 요약
        summary_tag = item.select_one("p.lead, .desc, .article-summary")
        summary = summary_tag.get_text(strip=True) if summary_tag else ""

        return Article(
            title=title,
            url=url,
            date=date,
            view_count=view_count,
            summary=summary,
            source=self.name,
        )


# ---------------------------------------------------------------------------
# 안전저널 (anjunj.com)
# ---------------------------------------------------------------------------
class AnjunjCrawler(BaseCrawler):
    name = "안전저널"
    base_url = "http://www.anjunj.com"

    _list_url = "http://www.anjunj.com/news/articleList.html?sc_section_code=S1N2&view_type=sm"

    def fetch_articles(self, since: datetime) -> list[Article]:
        articles: list[Article] = []
        for page in range(1, 6):
            url = f"{self._list_url}&page={page}"
            soup = self._get(url)
            if not soup:
                break

            items = soup.select("ul.type2 li, .list-block li, li.item")
            if not items:
                break

            found_old = False
            for item in items:
                article = self._parse_item(item)
                if article is None:
                    continue
                if article.date < since:
                    found_old = True
                    continue
                articles.append(article)

            if found_old:
                break
            time.sleep(0.5)

        return articles

    def _parse_item(self, item) -> Article | None:
        title_tag = item.select_one("h4 a, h3 a, .titles a, a[href*='articleView']")
        if not title_tag:
            return None

        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        if not href:
            return None
        url = href if href.startswith("http") else self.base_url + href

        date_tag = item.select_one("span.byline em, .dates, em")
        date = self._parse_date(date_tag.get_text()) if date_tag else datetime.now()

        view_count = 0
        for tag in item.select("span, em, li"):
            text = tag.get_text()
            if "조회" in text or "view" in text.lower():
                view_count = self._parse_view_count(text)
                break

        summary_tag = item.select_one("p.lead, .desc")
        summary = summary_tag.get_text(strip=True) if summary_tag else ""

        return Article(
            title=title,
            url=url,
            date=date,
            view_count=view_count,
            summary=summary,
            source=self.name,
        )


# ---------------------------------------------------------------------------
# 한국산업안전뉴스 (kisnews.net)
# ---------------------------------------------------------------------------
class KisnewsCrawler(BaseCrawler):
    name = "한국산업안전뉴스"
    base_url = "https://www.kisnews.net"

    _list_url = "https://www.kisnews.net/news/articleList.html?view_type=sm"

    def fetch_articles(self, since: datetime) -> list[Article]:
        articles: list[Article] = []
        for page in range(1, 6):
            url = f"{self._list_url}&page={page}"
            soup = self._get(url)
            if not soup:
                break

            items = soup.select("ul.type2 li, .list li, li.item, article")
            if not items:
                break

            found_old = False
            for item in items:
                article = self._parse_item(item)
                if article is None:
                    continue
                if article.date < since:
                    found_old = True
                    continue
                articles.append(article)

            if found_old:
                break
            time.sleep(0.5)

        return articles

    def _parse_item(self, item) -> Article | None:
        title_tag = item.select_one("h4 a, h3 a, .titles a, a[href*='articleView'], a[href*='/news/']")
        if not title_tag:
            return None

        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        if not href:
            return None
        url = href if href.startswith("http") else self.base_url + href

        date_tag = item.select_one("span.byline em, .dates, .date, time")
        date = self._parse_date(date_tag.get_text()) if date_tag else datetime.now()

        view_count = 0
        for tag in item.select("span, em, li, td"):
            text = tag.get_text()
            if "조회" in text or "view" in text.lower():
                view_count = self._parse_view_count(text)
                break

        summary_tag = item.select_one("p.lead, .desc, .summary")
        summary = summary_tag.get_text(strip=True) if summary_tag else ""

        return Article(
            title=title,
            url=url,
            date=date,
            view_count=view_count,
            summary=summary,
            source=self.name,
        )


# ---------------------------------------------------------------------------
# 통합 크롤러
# ---------------------------------------------------------------------------
def crawl_all(months: int = 3, top_n: int = 15) -> list[Article]:
    since = datetime.now() - timedelta(days=30 * months)
    crawlers: list[BaseCrawler] = [
        SafetyNewsCrawler(),
        AnjunjCrawler(),
        KisnewsCrawler(),
    ]

    all_articles: list[Article] = []
    for crawler in crawlers:
        logger.info("[%s] 크롤링 시작...", crawler.name)
        try:
            articles = crawler.fetch_articles(since)
            logger.info("[%s] %d건 수집", crawler.name, len(articles))
            all_articles.extend(articles)
        except Exception as exc:
            logger.error("[%s] 크롤링 오류: %s", crawler.name, exc)

    # 중복 URL 제거
    seen: set[str] = set()
    unique: list[Article] = []
    for a in all_articles:
        if a.url not in seen:
            seen.add(a.url)
            unique.append(a)

    # 조회수 내림차순 정렬, 같으면 날짜 내림차순
    unique.sort(key=lambda a: (a.view_count, a.date), reverse=True)

    return unique[:top_n]
