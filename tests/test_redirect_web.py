import asyncio
import unittest

from aiohttp.test_utils import make_mocked_request

from redirect_web.app import healthcheck_handler, open_handler, render_redirect_page


class RedirectWebTests(unittest.TestCase):
    def test_open_handler_renders_redirect_page(self) -> None:
        request = make_mocked_request(
            "GET",
            "/open?app=yandexmusic://album/5717491/track/43050400",
        )

        response = asyncio.run(open_handler(request))

        self.assertEqual(response.status, 200)
        body = response.text
        self.assertIn("yandexmusic://album/5717491/track/43050400", body)
        self.assertIn("https://music.yandex.ru/album/5717491/track/43050400", body)

    def test_open_handler_rejects_invalid_link(self) -> None:
        request = make_mocked_request("GET", "/open?app=https://ya.ru")

        response = asyncio.run(open_handler(request))

        self.assertEqual(response.status, 400)
        self.assertEqual(response.text, "Unsupported app link")

    def test_healthcheck_handler(self) -> None:
        request = make_mocked_request("GET", "/healthz")

        response = asyncio.run(healthcheck_handler(request))

        self.assertEqual(response.status, 200)
        self.assertEqual(response.text, '{"ok": true}')

    def test_render_redirect_page_contains_both_targets(self) -> None:
        html = render_redirect_page(
            app_url="yandexmusic://album/5717491/track/43050400",
            web_url="https://music.yandex.ru/album/5717491/track/43050400",
        )

        self.assertIn("ОТКРЫТЬ В ПРИЛОЖЕНИИ", html)
        self.assertIn("ОТКРЫТЬ В ВЕБ", html)
        self.assertIn("window.location.href = appUrl;", html)
        self.assertNotIn("window.location.replace(webUrl);", html)


if __name__ == "__main__":
    unittest.main()
