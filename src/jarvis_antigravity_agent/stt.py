import logging
from typing import Any

from jarvis_antigravity_agent.config import get_settings
from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.messages import Messages

logger = logging.getLogger(Constants.LOGGER_NAME)

_whisper_model: Any = None


def get_whisper_model() -> Any:
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        settings = get_settings()
        whisper_cfg = settings.whisper

        logger.info(
            Messages.WHISPER_INIT.format(
                model=whisper_cfg.model_size,
                device=whisper_cfg.device,
                compute_type=whisper_cfg.compute_type,
            )
        )
        _whisper_model = WhisperModel(
            whisper_cfg.model_size,
            device=whisper_cfg.device,
            compute_type=whisper_cfg.compute_type,
        )
        logger.info(Messages.WHISPER_READY)
    return _whisper_model


def transcribe_audio_file(file_path: str) -> tuple[str, str]:
    settings = get_settings()
    model = get_whisper_model()
    segments, info = model.transcribe(file_path, beam_size=settings.whisper.beam_size)
    transcription: str = " ".join(str(seg.text).strip() for seg in segments).strip()
    language: str = str(info.language)
    return transcription, language


def is_model_loaded() -> bool:
    return _whisper_model is not None


def stt_status_label() -> str:
    settings = get_settings()
    whisper_cfg = settings.whisper
    if is_model_loaded():
        return str(Messages.STT_LOADED)
    return str(
        Messages.STT_READY.format(
            model=whisper_cfg.model_size,
            compute_type=whisper_cfg.compute_type,
            device=whisper_cfg.device,
        )
    )
