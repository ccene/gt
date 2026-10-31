"""Local speech-to-text via faster-whisper (runs on the host, audio never leaves the LAN).

The model is downloaded lazily on first use and cached under ./data/models.
Audio bytes are accepted in memory only and never written to disk.
"""

import threading
from pathlib import Path

from config import settings

_lock = threading.Lock()
_model = None


def _model_dir() -> Path:
    d = settings.data_dir / "models"
    d.mkdir(parents=True, exist_ok=True)
    try:
        import os

        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def _load_model():
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel

            _model = WhisperModel(
                settings.whisper_model,
                device="cpu",
                compute_type="int8",
                download_root=str(_model_dir()),
            )
    return _model


def transcribe(audio_bytes: bytes) -> dict:
    """Transcribe webm/ogg/wav bytes. Returns text + segments.

    Audio stays in memory: faster-whisper decodes from a BytesIO stream, so
    nothing is ever written to disk (the privacy promise in MASTER_PLAN §10).
    """
    import io

    model = _load_model()
    segments, info = model.transcribe(io.BytesIO(audio_bytes), vad_filter=True)
    text = " ".join(s.text.strip() for s in segments).strip()
    return {
        "provider": "local-whisper",
        "language": info.language,
        "duration_s": round(info.duration, 2),
        "text": text,
    }


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except ImportError:
        return False
