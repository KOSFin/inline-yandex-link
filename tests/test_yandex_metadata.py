import unittest

from bot.models import ArtistLink, TrackLink
from bot.yandex_metadata import extract_artist_metadata, extract_track_metadata, parse_iso_duration

SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="ru-RU">
  <head>
    <meta property="og:title" content="&#x27;Bout It" />
    <meta property="og:description" content="JMSN • Трек • 2014" />
    <meta name="description" content="Слушать трек JMSN 'Bout It онлайн. Длительность дорожки 06:34, год выхода 2014." />
    <script type="application/ld+json">
      {
        "@context":"https://schema.org",
        "@type":"MusicAlbum",
        "tracks":[
          {"@type":"MusicRecording","name":"'Bout It","duration":"PT6M34S","url":"/album/2448178/track/21404459"}
        ]
      }
    </script>
  </head>
</html>
"""

STATE_SNAPSHOT_HTML = """
<!DOCTYPE html>
<html lang="ru-RU">
  <head></head>
  <body>
    <script>
      (window.__STATE_SNAPSHOT__ = window.__STATE_SNAPSHOT__ || []).push({
        "track": {
          "meta": {
            "id": "43050400",
            "realId": "43050400",
            "albumId": 5717491,
            "title": "Miss Me",
            "durationMs": 272780,
            "artists": [
              {"name": "Berner"},
              {"name": "Wiz Khalifa"},
              {"name": "Styles P"}
            ]
          }
        }
      });
    </script>
  </body>
</html>
"""

CAPTCHA_HTML = """
<!doctype html>
<html lang="ru">
  <head>
    <title>Вы не робот?</title>
  </head>
  <body>
    <form action="/checkcaptcha"></form>
    <div>Подтвердите, что запросы отправляли вы, а не робот</div>
  </body>
</html>
"""

ARTIST_HTML = """
<!DOCTYPE html>
<html lang="ru-RU">
  <head></head>
  <body>
    <script>
      (window.__STATE_SNAPSHOT__ = window.__STATE_SNAPSHOT__ || []).push({
        "artist": {
          "id": "23558757",
          "meta": {
            "artist": {
              "id": "23558757",
              "name": "Skyvault",
              "pendingLikesCount": 0
            },
            "lastMonthListeners": 1277692
          }
        }
      });
    </script>
    <script>
      self.__next_f.push([1,"2f:[\\"$\\",\\"$L6a\\",null,{\\"page\\":\\"artist\\",\\"children\\":[\\"$\\",\\"$L6b\\",null,{\\"artistId\\":\\"23558757\\",\\"preloadedArtist\\":{\\"artist\\":{\\"id\\":\\"23558757\\",\\"name\\":\\"Skyvault\\",\\"likesCount\\":22292}}}]}]"])
    </script>
    <h1><span>Skyvault</span></h1>
    <span>1&nbsp;277&nbsp;692 слушателя в месяц</span>
  </body>
</html>
"""


class TrackMetadataTests(unittest.TestCase):
    def test_extract_track_metadata(self) -> None:
        link = TrackLink(
            album_id="2448178",
            track_id="21404459",
            web_url="https://music.yandex.ru/album/2448178/track/21404459",
            app_url="yandexmusic://album/2448178/track/21404459",
        )

        metadata = extract_track_metadata(SAMPLE_HTML, link)

        self.assertEqual(metadata.title, "'Bout It")
        self.assertEqual(metadata.artist, "JMSN")
        self.assertEqual(metadata.duration, "06:34")
        self.assertIsNone(metadata.error_code)

    def test_extract_track_metadata_decodes_html_entities_in_title(self) -> None:
        link = TrackLink(
            album_id="2448178",
            track_id="21404459",
            web_url="https://music.yandex.ru/album/2448178/track/21404459",
            app_url="yandexmusic://album/2448178/track/21404459",
        )

        metadata = extract_track_metadata(SAMPLE_HTML, link)

        self.assertEqual(metadata.title, "'Bout It")
        self.assertNotIn("&#x27;", metadata.title)

    def test_extract_track_metadata_from_state_snapshot(self) -> None:
        link = TrackLink(
            album_id="5717491",
            track_id="43050400",
            web_url="https://music.yandex.ru/album/5717491/track/43050400",
            app_url="yandexmusic://album/5717491/track/43050400",
        )

        metadata = extract_track_metadata(STATE_SNAPSHOT_HTML, link)

        self.assertEqual(metadata.title, "Miss Me")
        self.assertEqual(metadata.artist, "Berner, Wiz Khalifa, Styles P")
        self.assertEqual(metadata.duration, "04:32")
        self.assertIsNone(metadata.error_code)

    def test_extract_track_metadata_reports_captcha(self) -> None:
        link = TrackLink(
            album_id="2448178",
            track_id="21404459",
            web_url="https://music.yandex.ru/album/2448178/track/21404459",
            app_url="yandexmusic://album/2448178/track/21404459",
        )

        metadata = extract_track_metadata(CAPTCHA_HTML, link)

        self.assertEqual(metadata.title, "ТРЕК")
        self.assertEqual(metadata.error_code, "captcha_required")

    def test_extract_artist_metadata(self) -> None:
        link = ArtistLink(
            artist_id="23558757",
            web_url="https://music.yandex.ru/artist/23558757",
            app_url="yandexmusic://artist/23558757",
        )

        metadata = extract_artist_metadata(ARTIST_HTML, link)

        self.assertEqual(metadata.title, "Skyvault")
        self.assertEqual(metadata.likes_count, 22292)
        self.assertEqual(metadata.last_month_listeners, 1277692)
        self.assertIsNone(metadata.error_code)

    def test_parse_iso_duration(self) -> None:
        self.assertEqual(parse_iso_duration("PT6M34S"), "06:34")
        self.assertEqual(parse_iso_duration("PT1H2M3S"), "1:02:03")


if __name__ == "__main__":
    unittest.main()
