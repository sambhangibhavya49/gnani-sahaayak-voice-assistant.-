"""
tests.test_config
~~~~~~~~~~~~~~~~~
Unit tests for configuration loading, credential validation, and secret masking.
"""

import os
import tempfile
import unittest
from pathlib import Path

from gnani.config import ConfigError, GnaniConfig, load_config, mask_secret


class TestConfig(unittest.TestCase):

    def test_mask_secret(self):
        """Verifies that secret keys are safely masked and never printed in full."""
        self.assertEqual(mask_secret(None), "<NOT SET>")
        self.assertEqual(mask_secret(""), "<NOT SET>")
        self.assertEqual(mask_secret("12345"), "***")
        self.assertEqual(mask_secret("12345678"), "***")
        self.assertEqual(mask_secret("gnani-sahaayak-dev-key"), "gnan...-key")
        self.assertNotIn("sahaayak", mask_secret("gnani-sahaayak-dev-key"))

    def test_config_repr_does_not_leak_secret(self):
        """Verifies that repr() and str() mask the API key."""
        raw_key = "super-secret-production-key-9988"
        cfg = GnaniConfig(api_key=raw_key)

        repr_str = repr(cfg)
        self.assertNotIn(raw_key, repr_str)
        self.assertIn("supe...9988", repr_str)

        str_repr = str(cfg)
        self.assertNotIn(raw_key, str_repr)

    def test_sanitized_headers(self):
        """Verifies that sanitized headers use the masked key."""
        raw_key = "my-secret-key-12345"
        cfg = GnaniConfig(api_key=raw_key, auth_header="X-API-Key-ID")

        sanitized = cfg.get_sanitized_headers()
        self.assertEqual(sanitized["X-API-Key-ID"], "my-s...2345")
        self.assertNotIn(raw_key, str(sanitized))

        # Real headers still have the real key
        real_headers = cfg.get_headers()
        self.assertEqual(real_headers["X-API-Key-ID"], raw_key)

    def test_validate_raises_on_empty_key(self):
        """Verifies that validate() raises ConfigError if the key is empty."""
        cfg = GnaniConfig(api_key="")
        with self.assertRaises(ConfigError):
            cfg.validate()

        cfg_spaces = GnaniConfig(api_key="   ")
        with self.assertRaises(ConfigError):
            cfg_spaces.validate()

    def test_load_from_temp_env(self):
        """Verifies that load_config properly parses a local .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "GNANI_API_KEY=test-mock-api-key-12345\n"
                "GNANI_API_BASE_URL=https://api.vachana.ai\n"
                "GNANI_PRISMA_LANGUAGE=hi-IN\n"
                "GNANI_TIMBRE_VOICE=Nalini\n",
                encoding="utf-8"
            )

            # Clear os.environ to test file loading
            old_val = os.environ.pop("GNANI_API_KEY", None)
            try:
                cfg = load_config(env_path=env_file, require_key=True)
                self.assertEqual(cfg.api_key, "test-mock-api-key-12345")
                self.assertEqual(cfg.base_url, "https://api.vachana.ai")
                self.assertEqual(cfg.prisma_language, "hi-IN")
                self.assertEqual(cfg.timbre_voice, "Nalini")
                self.assertEqual(cfg.timbre_model, "timbre-v2.5")
            finally:
                if old_val is not None:
                    os.environ["GNANI_API_KEY"] = old_val

    def test_default_timeouts(self):
        """Verifies default connect and read timeouts and timeout tuple properties."""
        cfg = GnaniConfig(api_key="test-key-12345")
        self.assertEqual(cfg.connect_timeout, 10.0)
        self.assertEqual(cfg.prisma_read_timeout, 60.0)
        self.assertEqual(cfg.timbre_read_timeout, 60.0)
        self.assertEqual(cfg.timbre_sample_rate, 16000)
        self.assertEqual(cfg.prisma_timeout, (10.0, 60.0))
        self.assertEqual(cfg.timbre_timeout, (10.0, 60.0))

    def test_custom_env_timeouts(self):
        """Verifies custom timeout settings parsed from environment."""
        env_keys = [
            "GNANI_API_KEY",
            "GNANI_CONNECT_TIMEOUT",
            "GNANI_PRISMA_READ_TIMEOUT",
            "GNANI_TIMBRE_READ_TIMEOUT",
            "GNANI_TIMBRE_SAMPLE_RATE",
            "GNANI_READ_TIMEOUT",
            "GNANI_HTTP_TIMEOUT",
        ]
        saved_env = {k: os.environ.get(k) for k in env_keys}
        for k in env_keys:
            os.environ.pop(k, None)

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                env_file = Path(tmpdir) / ".env"
                env_file.write_text(
                    "GNANI_API_KEY=test-mock-api-key-12345\n"
                    "GNANI_CONNECT_TIMEOUT=5.5\n"
                    "GNANI_PRISMA_READ_TIMEOUT=45.0\n"
                    "GNANI_TIMBRE_READ_TIMEOUT=75.0\n"
                    "GNANI_TIMBRE_SAMPLE_RATE=22050\n",
                    encoding="utf-8",
                )
                cfg = load_config(env_path=env_file, require_key=True)
                self.assertEqual(cfg.connect_timeout, 5.5)
                self.assertEqual(cfg.prisma_read_timeout, 45.0)
                self.assertEqual(cfg.timbre_read_timeout, 75.0)
                self.assertEqual(cfg.timbre_sample_rate, 22050)
                self.assertEqual(cfg.prisma_timeout, (5.5, 45.0))
                self.assertEqual(cfg.timbre_timeout, (5.5, 75.0))
        finally:
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_invalid_env_timeouts_fallback(self):
        """Verifies invalid or non-numeric timeout values safely fall back to defaults."""
        env_keys = [
            "GNANI_API_KEY",
            "GNANI_CONNECT_TIMEOUT",
            "GNANI_PRISMA_READ_TIMEOUT",
            "GNANI_TIMBRE_READ_TIMEOUT",
            "GNANI_TIMBRE_SAMPLE_RATE",
            "GNANI_READ_TIMEOUT",
            "GNANI_HTTP_TIMEOUT",
        ]
        saved_env = {k: os.environ.get(k) for k in env_keys}
        for k in env_keys:
            os.environ.pop(k, None)

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                env_file = Path(tmpdir) / ".env"
                env_file.write_text(
                    "GNANI_API_KEY=test-mock-api-key-12345\n"
                    "GNANI_CONNECT_TIMEOUT=invalid_float\n"
                    "GNANI_PRISMA_READ_TIMEOUT=-10\n"
                    "GNANI_TIMBRE_READ_TIMEOUT=not_a_number\n"
                    "GNANI_TIMBRE_SAMPLE_RATE=bad_rate\n",
                    encoding="utf-8",
                )
                cfg = load_config(env_path=env_file, require_key=True)
                self.assertEqual(cfg.connect_timeout, 10.0)
                self.assertEqual(cfg.prisma_read_timeout, 60.0)
                self.assertEqual(cfg.timbre_read_timeout, 60.0)
                self.assertEqual(cfg.timbre_sample_rate, 16000)
        finally:
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
