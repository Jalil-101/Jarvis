"""TTS / STT helpers (no network)."""

from __future__ import annotations

import unittest

from jarvis.voice.stt import cleanup_transcript
from jarvis.voice.tts import _for_speech, _use_elevenlabs


class SpeechPrepTests(unittest.TestCase):
    def test_strips_markdown(self) -> None:
        text = _for_speech("**Hello** — see [docs](https://x.test) and `code`.")
        self.assertNotIn("**", text)
        self.assertNotIn("https://", text)
        self.assertIn("Hello", text)
        self.assertIn("docs", text)
        self.assertIn("code", text)

    def test_truncates_long_replies(self) -> None:
        long = "word " * 200
        out = _for_speech(long)
        self.assertLessEqual(len(out), 610)

    def test_elevenlabs_needs_key(self) -> None:
        import os

        prev = os.environ.pop("ELEVENLABS_API_KEY", None)
        try:
            self.assertFalse(_use_elevenlabs("auto"))
            os.environ["ELEVENLABS_API_KEY"] = "test-key"
            self.assertTrue(_use_elevenlabs("auto"))
            self.assertTrue(_use_elevenlabs("elevenlabs"))
            self.assertFalse(_use_elevenlabs("edge-tts"))
        finally:
            if prev is None:
                os.environ.pop("ELEVENLABS_API_KEY", None)
            else:
                os.environ["ELEVENLABS_API_KEY"] = prev


class TranscriptCleanupTests(unittest.TestCase):
    def test_fixes_jarvis_misspellings(self) -> None:
        self.assertIn("Jarvis", cleanup_transcript("hey jarves create a folder"))

    def test_drops_hallucination(self) -> None:
        self.assertEqual(cleanup_transcript("you"), "")

    def test_capitalizes(self) -> None:
        out = cleanup_transcript("what is the weather")
        self.assertTrue(out.startswith("W"))


if __name__ == "__main__":
    unittest.main()
