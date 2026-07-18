class TTSError(Exception):
    """Base class for text-to-speech errors."""


class TTSConfigurationError(TTSError):
    """Raised when the text-to-speech service is configured incorrectly."""


class InvalidSpeechRequestError(TTSError):
    """Raised when a synthesis request cannot be processed."""


class EmptyTextError(InvalidSpeechRequestError):
    """Raised when text is empty or contains only whitespace."""


class TextTooLongError(InvalidSpeechRequestError):
    """Raised when text exceeds the configured synthesis limit."""

    def __init__(self, length: int, max_length: int) -> None:
        super().__init__(f"text is {length} characters; max allowed is {max_length}")
        self.length = length
        self.max_length = max_length


class InvalidLanguageError(InvalidSpeechRequestError):
    """Raised when no usable language code is supplied."""


class InvalidVoiceError(InvalidSpeechRequestError):
    """Raised when no usable voice identifier is supplied."""


class InvalidSpeechSpeedError(InvalidSpeechRequestError):
    """Raised when speech speed falls outside the supported range."""

    def __init__(self, speed: float, minimum: float, maximum: float) -> None:
        super().__init__(f"speech speed must be between {minimum} and {maximum}; got {speed}")
        self.speed = speed
        self.minimum = minimum
        self.maximum = maximum


class UnsupportedAudioFormatError(InvalidSpeechRequestError):
    """Raised when the requested audio format is not supported."""

    def __init__(self, output_format: str) -> None:
        super().__init__(f"unsupported speech audio format: {output_format!r}")
        self.output_format = output_format


class SpeechSynthesisFailedError(TTSError):
    """Raised when a text-to-speech provider cannot produce audio."""
