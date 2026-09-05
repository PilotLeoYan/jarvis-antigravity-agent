import logging
from typing import Any

from jarvis_antigravity_agent.constants import Constants
from jarvis_antigravity_agent.messages import Messages

logger = logging.getLogger(Constants.LOGGER_NAME)

_whisper_model: Any = None


def get_whisper_model() -> Any:
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        logger.info(
            Messages.WHISPER_INIT.format(
                model=Constants.WHISPER_MODEL_SIZE,
                device=Constants.WHISPER_DEVICE,
                compute_type=Constants.WHISPER_COMPUTE_TYPE,
            )
        )
        _whisper_model = WhisperModel(
            Constants.WHISPER_MODEL_SIZE,
            device=Constants.WHISPER_DEVICE,
            compute_type=Constants.WHISPER_COMPUTE_TYPE,
        )
        logger.info(Messages.WHISPER_READY)
    return _whisper_model


def transcribe_audio_file(file_path: str) -> tuple[str, str]:
    model = get_whisper_model()
    segments, info = model.transcribe(file_path, beam_size=Constants.WHISPER_BEAM_SIZE)
    transcription: str = " ".join(str(seg.text).strip() for seg in segments).strip()
    language: str = str(info.language)
    return transcription, language


def is_model_loaded() -> bool:
    return _whisper_model is not None


def stt_status_label() -> str:
    if is_model_loaded():
        return str(Messages.STT_LOADED)
    return str(
        Messages.STT_READY.format(
            model=Constants.WHISPER_MODEL_SIZE,
            compute_type=Constants.WHISPER_COMPUTE_TYPE,
            device=Constants.WHISPER_DEVICE,
        )
    )
