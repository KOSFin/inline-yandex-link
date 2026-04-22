from __future__ import annotations

import json
from html import escape

from aiohttp import web

from bot.yandex_links import LinkParseError, parse_track_link


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/healthz", healthcheck_handler)
    app.router.add_get("/open", open_handler)
    return app


async def healthcheck_handler(_: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def open_handler(request: web.Request) -> web.Response:
    raw_app_url = request.query.get("app", "").strip()
    if not raw_app_url:
        return web.Response(status=400, text="Missing app query parameter", content_type="text/plain")

    try:
        link = parse_track_link(raw_app_url)
    except LinkParseError:
        return web.Response(status=400, text="Unsupported app link", content_type="text/plain")

    return web.Response(
        text=render_redirect_page(app_url=link.app_url, web_url=link.web_url),
        content_type="text/html",
    )


def render_redirect_page(*, app_url: str, web_url: str) -> str:
    escaped_app_url = escape(app_url)
    escaped_web_url = escape(web_url)
    app_url_json = json.dumps(app_url)

    return f"""<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex,nofollow">
    <title>Открываем Яндекс Музыку</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f4f1ea;
        --text: #1f1f1f;
        --muted: #66604f;
        --primary: #ffcc00;
        --primary-text: #1f1f1f;
        --secondary: #ffffff;
        --secondary-border: #d7cfbf;
      }}
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 24px;
        background:
          radial-gradient(circle at top, rgba(255, 204, 0, 0.32), transparent 38%),
          linear-gradient(180deg, #fbf7ef 0%, var(--bg) 100%);
        color: var(--text);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      .card {{
        width: min(100%, 440px);
        padding: 28px;
        border-radius: 24px;
        background: rgba(255, 255, 255, 0.84);
        border: 1px solid rgba(31, 31, 31, 0.08);
        box-shadow: 0 18px 60px rgba(0, 0, 0, 0.12);
        backdrop-filter: blur(14px);
      }}
      h1 {{
        margin: 0 0 10px;
        font-size: 28px;
        line-height: 1.05;
      }}
      p {{
        margin: 0;
        color: var(--muted);
        line-height: 1.45;
      }}
      .actions {{
        display: grid;
        gap: 12px;
        margin-top: 22px;
      }}
      .button {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 48px;
        padding: 12px 18px;
        border-radius: 14px;
        text-decoration: none;
        font-weight: 700;
      }}
      .button-primary {{
        background: var(--primary);
        color: var(--primary-text);
      }}
      .button-secondary {{
        background: var(--secondary);
        color: var(--text);
        border: 1px solid var(--secondary-border);
      }}
      code {{
        display: block;
        margin-top: 16px;
        word-break: break-all;
        white-space: pre-wrap;
        font-size: 13px;
        color: var(--muted);
      }}
    </style>
  </head>
  <body>
    <main class="card">
      <h1>Открываем Яндекс Музыку</h1>
      <p>Пробуем открыть трек в приложении. Если не сработало, нажми кнопку ещё раз или открой веб-версию вручную.</p>
      <div class="actions">
        <a class="button button-primary" href="{escaped_app_url}">ОТКРЫТЬ В ПРИЛОЖЕНИИ</a>
        <a class="button button-secondary" href="{escaped_web_url}">ОТКРЫТЬ В ВЕБ</a>
      </div>
      <code>{escaped_app_url}</code>
    </main>
    <script>
      const appUrl = {app_url_json};
      window.location.href = appUrl;
    </script>
  </body>
</html>
"""
