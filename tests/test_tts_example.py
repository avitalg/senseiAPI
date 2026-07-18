import logging
from pathlib import Path

import pytest

from core.config import Settings
from tts import text_to_speech
from tts.errors import SpeechSynthesisFailedError

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = "<insert_your_elevenlabs_api_key>"
ELEVENLABS_VOICE_ID = "<insert_your_elevenlabs_voice_id>"
ELEVENLABS_TTS_MODEL = "eleven_v3"

EXAMPLE_TEXT = (
    "יש רגעים שבהם הדרך נפתחת דווקא כשאנחנו מפסיקים לדעת לאן היא מובילה. "
    "צעד קטן אל הלא־נודע יכול להפוך לחלון גדול של אור, סקרנות ותקווה."
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.integration
@pytest.mark.manual
@pytest.mark.anyio
async def test_generate_hebrew_tts_example() -> None:
    """Call ElevenLabs and leave a playable MP3 under the project artifacts directory."""
    assert not ELEVENLABS_API_KEY.startswith("<insert_your_"), (
        "replace ELEVENLABS_API_KEY with a valid ElevenLabs API key"
    )
    assert not ELEVENLABS_VOICE_ID.startswith("<insert_your_"), (
        "replace ELEVENLABS_VOICE_ID with a valid ElevenLabs voice ID"
    )

    settings = Settings(
        enable_security=False,
        tts_enabled=True,
        elevenlabs_api_key=ELEVENLABS_API_KEY,
        elevenlabs_tts_voice_id=ELEVENLABS_VOICE_ID,
        elevenlabs_tts_model=ELEVENLABS_TTS_MODEL,
        tts_default_language="he",
        tts_default_output_format="mp3",
    )

    try:
        audio = await text_to_speech(EXAMPLE_TEXT, settings=settings)
    except SpeechSynthesisFailedError as exc:
        raise AssertionError(
            "ElevenLabs rejected the TTS request; check the API key, voice ID, and model"
        ) from exc

    assert audio.data
    assert audio.media_type == "audio/mpeg"
    assert audio.file_extension == "mp3"

    project_root = Path(__file__).resolve().parents[1]
    output_path = project_root / "artifacts" / "hebrew_tts_example.mp3"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = output_path.write_bytes(audio.data)

    assert written == len(audio.data)
    assert output_path.is_file()
    logger.info("Playable TTS example saved to: %s", output_path.resolve())
