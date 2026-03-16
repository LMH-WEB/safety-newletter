"""
HTML 뉴스레터 생성 모듈
"""

from datetime import datetime

from jinja2 import Template

from crawler import Article

_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>건설안전 뉴스레터</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f6f8;font-family:'Apple SD Gothic Neo','Malgun Gothic',Arial,sans-serif;">

<!-- 래퍼 -->
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f8;">
<tr><td align="center" style="padding:30px 10px;">

  <!-- 컨테이너 -->
  <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;">

    <!-- 헤더 -->
    <tr>
      <td style="background:linear-gradient(135deg,#1a3c5e 0%,#2e6da4 100%);border-radius:12px 12px 0 0;padding:36px 40px;text-align:center;">
        <p style="margin:0 0 6px;color:#a8d4f5;font-size:13px;letter-spacing:2px;text-transform:uppercase;">CONSTRUCTION SAFETY</p>
        <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:700;line-height:1.3;">건설안전 뉴스레터</h1>
        <p style="margin:12px 0 0;color:#c8dff0;font-size:14px;">{{ issue_date }} 발행 · 최근 {{ months }}개월 뉴스 · 조회수 Top {{ total }}위</p>
      </td>
    </tr>

    <!-- 본문 배경 -->
    <tr>
      <td style="background:#ffffff;padding:32px 40px 0;">
        <p style="margin:0 0 24px;color:#555;font-size:14px;line-height:1.6;">
          안녕하세요. 이번 주 <strong>건설안전</strong> 주요 뉴스를 조회수 기준으로 정리해 드립니다.
        </p>
      </td>
    </tr>

    <!-- 기사 목록 -->
    {% for article in articles %}
    <tr>
      <td style="background:#ffffff;padding:0 40px;">
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border:1px solid #e8ecf0;border-radius:10px;margin-bottom:18px;overflow:hidden;">
          <tr>
            <!-- 순위 배지 -->
            <td width="56" valign="top"
                style="background:{% if loop.index <= 3 %}#1a3c5e{% else %}#e8ecf0{% endif %};
                       padding:20px 0;text-align:center;">
              <span style="color:{% if loop.index <= 3 %}#ffffff{% else %}#7a8899{% endif %};
                           font-size:20px;font-weight:700;line-height:1;">{{ loop.index }}</span>
            </td>
            <!-- 기사 내용 -->
            <td style="padding:16px 20px;">
              <a href="{{ article.url }}" target="_blank"
                 style="color:#1a3c5e;font-size:16px;font-weight:700;text-decoration:none;line-height:1.4;display:block;margin-bottom:8px;">
                {{ article.title }}
              </a>
              {% if article.summary %}
              <p style="margin:0 0 10px;color:#666;font-size:13px;line-height:1.6;">
                {{ article.summary[:120] }}{% if article.summary|length > 120 %}…{% endif %}
              </p>
              {% endif %}
              <table cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td style="vertical-align:middle;">
                    <span style="background:#eaf3fb;color:#2e6da4;font-size:11px;font-weight:600;
                                 padding:3px 8px;border-radius:4px;margin-right:6px;">{{ article.source }}</span>
                    <span style="color:#999;font-size:12px;">{{ article.date.strftime('%Y.%m.%d') }}</span>
                    {% if article.view_count > 0 %}
                    <span style="color:#999;font-size:12px;margin-left:10px;">
                      👁 {{ '{:,}'.format(article.view_count) }}
                    </span>
                    {% endif %}
                  </td>
                  <td align="right" style="vertical-align:middle;">
                    <a href="{{ article.url }}" target="_blank"
                       style="background:#2e6da4;color:#fff;font-size:12px;font-weight:600;
                              padding:6px 14px;border-radius:6px;text-decoration:none;white-space:nowrap;">
                      기사 보기 →
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    {% endfor %}

    <!-- 패딩 -->
    <tr>
      <td style="background:#ffffff;padding:8px 40px 32px;">
        <p style="margin:0;color:#aaa;font-size:12px;text-align:center;">
          총 {{ articles|length }}건의 기사가 수집되었습니다.
        </p>
      </td>
    </tr>

    <!-- 푸터 -->
    <tr>
      <td style="background:#2c3e50;border-radius:0 0 12px 12px;padding:24px 40px;text-align:center;">
        <p style="margin:0 0 6px;color:#a0aab4;font-size:12px;">
          본 뉴스레터는 건설안전 관련 뉴스를 자동으로 수집하여 발송됩니다.
        </p>
        <p style="margin:0;color:#6b7a8a;font-size:11px;">
          © {{ year }} 건설안전 뉴스레터 · 매주 월요일 자동 발송
        </p>
      </td>
    </tr>

  </table>
</td></tr>
</table>

</body>
</html>
"""

_PLAIN_TEMPLATE = """건설안전 뉴스레터 — {{ issue_date }}
최근 {{ months }}개월 · 조회수 Top {{ total }}위
=============================================

{% for article in articles %}
{{ loop.index }}. {{ article.title }}
   출처: {{ article.source }} | 날짜: {{ article.date.strftime('%Y.%m.%d') }}{% if article.view_count > 0 %} | 조회수: {{ '{:,}'.format(article.view_count) }}{% endif %}
   링크: {{ article.url }}
{% if article.summary %}   {{ article.summary[:100] }}{% if article.summary|length > 100 %}...{% endif %}
{% endif %}
{% endfor %}

---------------------------------------------
본 뉴스레터는 매주 월요일 자동 발송됩니다.
"""


def build_newsletter(articles: list[Article], months: int = 3) -> tuple[str, str]:
    """HTML 뉴스레터와 평문 버전을 함께 반환합니다."""
    now = datetime.now()
    ctx = {
        "articles": articles,
        "issue_date": now.strftime("%Y년 %m월 %d일"),
        "months": months,
        "total": len(articles),
        "year": now.year,
    }
    html = Template(_TEMPLATE).render(**ctx)
    plain = Template(_PLAIN_TEMPLATE).render(**ctx)
    return html, plain
