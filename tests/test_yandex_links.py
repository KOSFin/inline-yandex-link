import unittest

from bot.yandex_links import LinkParseError, parse_track_link


class ParseTrackLinkTests(unittest.TestCase):
    def test_parse_web_link(self) -> None:
        link = parse_track_link(
            "https://music.yandex.ru/album/2448178/track/21404459?utm_source=desktop&utm_medium=copy_link"
        )

        self.assertEqual(link.album_id, "2448178")
        self.assertEqual(link.track_id, "21404459")
        self.assertEqual(link.web_url, "https://music.yandex.ru/album/2448178/track/21404459")
        self.assertEqual(link.app_url, "yandexmusic://album/2448178/track/21404459")

    def test_parse_app_link(self) -> None:
        link = parse_track_link("yandexmusic://album/2448178/track/21404459")

        self.assertEqual(link.album_id, "2448178")
        self.assertEqual(link.track_id, "21404459")

    def test_reject_unsupported_link(self) -> None:
        with self.assertRaises(LinkParseError) as context:
            parse_track_link("https://ya.ru")

        self.assertEqual(str(context.exception), "unsupported_link")


if __name__ == "__main__":
    unittest.main()

