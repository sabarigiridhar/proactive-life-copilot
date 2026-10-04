import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.core.settings import Settings
from backend.main import create_app
from life_copilot.agent.provider import (
    ProviderCallError,
    ProviderErrorInfo,
    ProviderFailureKind,
)


def wav_bytes(duration_seconds: float, sample_rate: int = 8_000) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00\x00" * int(sample_rate * duration_seconds))
    return output.getvalue()


def image_bytes(size=(32, 24), image_format="PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color=(24, 96, 160)).save(output, format=image_format)
    return output.getvalue()


class MediaApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp_dir.name)
        self.settings = Settings(
            environment="test",
            database_path=root / "media-api.db",
            chroma_path=root / "chroma",
            cors_origins=[],
            max_audio_bytes=100_000,
            max_audio_duration_seconds=2,
            max_image_bytes=100_000,
            max_image_dimension=64,
            max_image_pixels=3_000,
        )
        self.client = TestClient(create_app(self.settings))

    def tearDown(self):
        self.temp_dir.cleanup()

    def _record_temp_files(self):
        paths = []

        def create(suffix):
            temporary = tempfile.NamedTemporaryFile(
                mode="w+b",
                prefix="media-api-test-",
                suffix=suffix,
                dir=self.temp_dir.name,
                delete=False,
            )
            paths.append(Path(temporary.name))
            return temporary

        return paths, create

    def test_openapi_documents_multipart_media_routes(self):
        paths = self.client.get("/openapi.json").json()["paths"]

        for route in (
            "/api/v1/media/transcriptions",
            "/api/v1/media/extractions",
        ):
            self.assertIn(route, paths)
            content = paths[route]["post"]["requestBody"]["content"]
            self.assertIn("multipart/form-data", content)

    def test_audio_is_transcribed_and_temporary_file_is_removed(self):
        paths, create_temp = self._record_temp_files()
        with patch(
            "backend.services.media._new_temp_file", side_effect=create_temp
        ), patch(
            "backend.services.media.transcribe_groq_audio",
            return_value="I worked out for thirty minutes.",
        ) as transcribe:
            response = self.client.post(
                "/api/v1/media/transcriptions",
                files={"file": ("recording.wav", wav_bytes(1), "audio/wav")},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["media_type"], "audio")
        self.assertEqual(data["content_type"], "audio/wav")
        self.assertAlmostEqual(data["duration_seconds"], 1.0, places=2)
        self.assertIn("worked out", data["text"])
        self.assertEqual(len(paths), 1)
        self.assertFalse(paths[0].exists())
        transcribe.assert_called_once()

    def test_audio_limits_and_invalid_types_are_rejected_before_provider(self):
        with patch("backend.services.media.transcribe_groq_audio") as transcribe:
            unsupported = self.client.post(
                "/api/v1/media/transcriptions",
                files={"file": ("audio.webm", b"data", "audio/webm")},
            )
            oversized = self.client.post(
                "/api/v1/media/transcriptions",
                files={"file": ("audio.wav", b"0" * 100_001, "audio/wav")},
            )
            too_long = self.client.post(
                "/api/v1/media/transcriptions",
                files={"file": ("audio.wav", wav_bytes(3), "audio/wav")},
            )

        self.assertEqual(unsupported.status_code, 415)
        self.assertEqual(oversized.status_code, 413)
        self.assertEqual(too_long.status_code, 413)
        transcribe.assert_not_called()

    def test_malformed_audio_is_rejected_and_temporary_file_is_removed(self):
        paths, create_temp = self._record_temp_files()
        with patch(
            "backend.services.media._new_temp_file", side_effect=create_temp
        ), patch("backend.services.media.transcribe_groq_audio") as transcribe:
            response = self.client.post(
                "/api/v1/media/transcriptions",
                files={"file": ("broken.wav", b"not a wav file", "audio/wav")},
            )

        self.assertEqual(response.status_code, 422)
        transcribe.assert_not_called()
        self.assertEqual(len(paths), 1)
        self.assertFalse(paths[0].exists())

    def test_audio_provider_failure_is_sanitized_and_cleans_up(self):
        paths, create_temp = self._record_temp_files()
        provider_error = ProviderCallError(
            "groq",
            "audio_transcription",
            ProviderErrorInfo(ProviderFailureKind.SERVER, True),
            3,
        )
        with patch(
            "backend.services.media._new_temp_file", side_effect=create_temp
        ), patch(
            "backend.services.media.transcribe_groq_audio",
            side_effect=provider_error,
        ):
            response = self.client.post(
                "/api/v1/media/transcriptions",
                files={"file": ("recording.wav", wav_bytes(1), "audio/wav")},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "http_error")
        self.assertIn("temporarily unavailable", response.json()["error"]["message"])
        self.assertNotIn("groq", response.text.lower())
        self.assertEqual(len(paths), 1)
        self.assertFalse(paths[0].exists())

    def test_missing_groq_configuration_returns_safe_error(self):
        paths, create_temp = self._record_temp_files()
        with patch(
            "backend.services.media._new_temp_file", side_effect=create_temp
        ), patch("life_copilot.agent.provider.os.getenv", return_value=None):
            response = self.client.post(
                "/api/v1/media/transcriptions",
                files={"file": ("recording.wav", wav_bytes(1), "audio/wav")},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured correctly", response.json()["error"]["message"])
        self.assertEqual(len(paths), 1)
        self.assertFalse(paths[0].exists())

    def test_image_is_validated_and_extracted(self):
        with patch(
            "backend.services.media.generate_gemini_content",
            return_value="Receipt: INR 450 for groceries.",
        ) as extract:
            response = self.client.post(
                "/api/v1/media/extractions",
                files={"file": ("receipt.png", image_bytes(), "image/png")},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["media_type"], "image")
        self.assertEqual((data["width"], data["height"]), (32, 24))
        self.assertIn("450", data["text"])
        extract.assert_called_once()

    def test_image_limits_content_and_provider_errors_are_safe(self):
        with patch("backend.services.media.generate_gemini_content") as extract:
            unsupported = self.client.post(
                "/api/v1/media/extractions",
                files={"file": ("file.gif", b"data", "image/gif")},
            )
            mismatched = self.client.post(
                "/api/v1/media/extractions",
                files={"file": ("file.jpg", image_bytes(), "image/jpeg")},
            )
            too_wide = self.client.post(
                "/api/v1/media/extractions",
                files={
                    "file": ("wide.png", image_bytes(size=(65, 20)), "image/png")
                },
            )
            too_many_pixels = self.client.post(
                "/api/v1/media/extractions",
                files={
                    "file": (
                        "dense.png",
                        image_bytes(size=(60, 60)),
                        "image/png",
                    )
                },
            )
            oversized = self.client.post(
                "/api/v1/media/extractions",
                files={"file": ("large.png", b"0" * 100_001, "image/png")},
            )

        self.assertEqual(unsupported.status_code, 415)
        self.assertEqual(mismatched.status_code, 422)
        self.assertEqual(too_wide.status_code, 413)
        self.assertEqual(too_many_pixels.status_code, 413)
        self.assertEqual(oversized.status_code, 413)
        extract.assert_not_called()

        provider_error = ProviderCallError(
            "gemini",
            "image_extraction",
            ProviderErrorInfo(ProviderFailureKind.AUTHENTICATION, False),
            1,
        )
        with patch(
            "backend.services.media.generate_gemini_content",
            side_effect=provider_error,
        ):
            provider_failure = self.client.post(
                "/api/v1/media/extractions",
                files={"file": ("receipt.png", image_bytes(), "image/png")},
            )

        self.assertEqual(provider_failure.status_code, 503)
        self.assertIn(
            "not configured correctly",
            provider_failure.json()["error"]["message"],
        )


if __name__ == "__main__":
    unittest.main()
