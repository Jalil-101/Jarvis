"""Audio playback helpers."""

from __future__ import annotations

import unittest
from pathlib import Path

from jarvis.voice.playback import play_audio


class PlaybackTests(unittest.TestCase):
    def test_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            play_audio(Path("definitely-not-a-real-file.mp3"))


if __name__ == "__main__":
    unittest.main()
