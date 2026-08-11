"""CLI wiring (no API key required)."""

from __future__ import annotations

import unittest
from io import StringIO
from unittest.mock import patch

from jarvis.__main__ import main


class CliTests(unittest.TestCase):
    def test_help_exits_zero(self) -> None:
        buf = StringIO()
        with self.assertRaises(SystemExit) as ctx, patch("sys.stdout", buf):
            main(["-h"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("listen", buf.getvalue())
        self.assertIn("demo", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
