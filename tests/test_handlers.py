import unittest

from bot.handlers import build_track_result, render_message
from bot.models import TrackLink, TrackMetadata


class HandlerTests(unittest.TestCase):
    def test_build_track_result_uses_keyboard_for_links(self) -> None:
        link = TrackLink(
            album_id="5717491",
            track_id="43050400",
            web_url="https://music.yandex.ru/album/5717491/track/43050400",
            app_url="yandexmusic://album/5717491/track/43050400",
        )
        metadata = TrackMetadata(title="Miss Me", artist="Berner, Wiz Khalifa, Styles P", duration="04:32")

        result = build_track_result(link, metadata)

        self.assertIsNotNone(result.reply_markup)
        self.assertEqual(result.reply_markup.inline_keyboard[0][0].url, link.web_url)
        self.assertEqual(
            result.reply_markup.inline_keyboard[1][0].copy_text.text,
            link.app_url,
        )

    def test_render_message_keeps_track_text_clean(self) -> None:
        link = TrackLink(
            album_id="5717491",
            track_id="43050400",
            web_url="https://music.yandex.ru/album/5717491/track/43050400",
            app_url="yandexmusic://album/5717491/track/43050400",
        )
        metadata = TrackMetadata(title="Miss Me", artist="Berner", duration="04:32")

        message = render_message(link, metadata)

        self.assertEqual(message, "🎵 <b>Miss Me</b>\nBerner • 04:32")


if __name__ == "__main__":
    unittest.main()
