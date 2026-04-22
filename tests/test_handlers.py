import unittest

from bot.handlers import (
    INLINE_TRACK_EMOJI,
    TRACK_CUSTOM_EMOJI_ID,
    TRACK_EMOJI,
    build_private_help_message,
    build_redirect_url,
    build_start_message,
    build_track_message_entities,
    build_track_result,
    render_inline_message,
    render_message,
)
from bot.models import TrackLink, TrackMetadata


class HandlerTests(unittest.TestCase):
    def test_build_track_result_uses_redirect_button_when_base_url_is_configured(self) -> None:
        link = TrackLink(
            album_id="5717491",
            track_id="43050400",
            web_url="https://music.yandex.ru/album/5717491/track/43050400",
            app_url="yandexmusic://album/5717491/track/43050400",
        )
        metadata = TrackMetadata(title="Miss Me", artist="Berner, Wiz Khalifa, Styles P", duration="04:32")

        result = build_track_result(link, metadata, app_redirect_base_url="https://music-links.example.com")

        self.assertIsNotNone(result.reply_markup)
        self.assertEqual(result.reply_markup.inline_keyboard[0][0].url, link.web_url)
        self.assertEqual(result.input_message_content.message_text, "🐈 Miss Me\nBerner, Wiz Khalifa, Styles P • 04:32")
        self.assertEqual(len(result.input_message_content.entities), 1)
        self.assertEqual(result.input_message_content.entities[0].type, "bold")
        self.assertEqual(
            result.reply_markup.inline_keyboard[1][0].url,
            "https://music-links.example.com/open?app=yandexmusic%3A%2F%2Falbum%2F5717491%2Ftrack%2F43050400",
        )

    def test_build_track_result_falls_back_to_copy_button_without_redirect_base_url(self) -> None:
        link = TrackLink(
            album_id="5717491",
            track_id="43050400",
            web_url="https://music.yandex.ru/album/5717491/track/43050400",
            app_url="yandexmusic://album/5717491/track/43050400",
        )
        metadata = TrackMetadata(title="Miss Me", artist="Berner, Wiz Khalifa, Styles P", duration="04:32")

        result = build_track_result(link, metadata)

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

        self.assertEqual(message, f"{TRACK_EMOJI} Miss Me\nBerner • 04:32")

    def test_render_inline_message_uses_cat_emoji(self) -> None:
        metadata = TrackMetadata(title="Miss Me", artist="Berner", duration="04:32")

        message = render_inline_message(metadata)

        self.assertEqual(message, f"{INLINE_TRACK_EMOJI} Miss Me\nBerner • 04:32")

    def test_render_message_does_not_escape_apostrophe_into_numeric_entity(self) -> None:
        link = TrackLink(
            album_id="2448178",
            track_id="21404459",
            web_url="https://music.yandex.ru/album/2448178/track/21404459",
            app_url="yandexmusic://album/2448178/track/21404459",
        )
        metadata = TrackMetadata(title="'Bout It", artist="JMSN", duration="06:34")

        message = render_message(link, metadata)

        self.assertEqual(message, f"{TRACK_EMOJI} 'Bout It\nJMSN • 06:34")
        self.assertNotIn("&#x27;", message)

    def test_build_track_message_entities_uses_custom_emoji_for_private_mode(self) -> None:
        metadata = TrackMetadata(title="Miss Me", artist="Berner", duration="04:32")

        entities = build_track_message_entities(
            metadata,
            emoji=TRACK_EMOJI,
            custom_emoji_id=TRACK_CUSTOM_EMOJI_ID,
        )

        self.assertEqual(entities[0].type, "custom_emoji")
        self.assertEqual(entities[0].custom_emoji_id, TRACK_CUSTOM_EMOJI_ID)
        self.assertEqual(entities[1].type, "bold")

    def test_build_start_message_mentions_private_and_inline_modes(self) -> None:
        message = build_start_message()

        self.assertIn("Личка", message)
        self.assertIn("Inline", message)

    def test_build_private_help_message_contains_supported_link_examples(self) -> None:
        message = build_private_help_message("unsupported_link")

        self.assertIn("https://music.yandex.ru/album/123/track/456", message)
        self.assertIn("yandexmusic://album/123/track/456", message)
        self.assertIn("unsupported_link", message)

    def test_build_redirect_url(self) -> None:
        link = TrackLink(
            album_id="5717491",
            track_id="43050400",
            web_url="https://music.yandex.ru/album/5717491/track/43050400",
            app_url="yandexmusic://album/5717491/track/43050400",
        )

        redirect_url = build_redirect_url(link, app_redirect_base_url="https://music-links.example.com/")

        self.assertEqual(
            redirect_url,
            "https://music-links.example.com/open?app=yandexmusic%3A%2F%2Falbum%2F5717491%2Ftrack%2F43050400",
        )


if __name__ == "__main__":
    unittest.main()
