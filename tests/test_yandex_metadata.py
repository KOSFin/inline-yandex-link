import unittest

from bot.models import TrackLink
from bot.yandex_metadata import extract_track_metadata, parse_iso_duration

SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="ru-RU">
  <head>
    <meta property="og:title" content="'Bout It" />
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

    def test_parse_iso_duration(self) -> None:
        self.assertEqual(parse_iso_duration("PT6M34S"), "06:34")
        self.assertEqual(parse_iso_duration("PT1H2M3S"), "1:02:03")


if __name__ == "__main__":
    unittest.main()
