"""
Global constants and configuration for Voxylis
"""

# Application metadata
APP_NAME = "Voxylis"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Voxylis Team"

# Audio settings
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
AUDIO_FORMAT = "int16"
CHANNELS = 1
AUDIO_DEVICE = None  # None = default device

# Recording settings
MAX_RECORDING_DURATION = 600  # 10 minutes in seconds
MIN_RECORDING_DURATION = 1.0  # 1 second minimum

# API settings
OPENAI_API_TIMEOUT = 30
WHISPER_MODEL = "whisper-1"
GPT_MODEL = "gpt-4-turbo-preview"

# UI settings
HOTKEY_DEFAULT = "ctrl+shift+v"
FLOATING_WIDGET_WIDTH = 200
FLOATING_WIDGET_HEIGHT = 100
WINDOW_OPACITY = 0.95

# Enhancement modes
ENHANCEMENT_MODES = {
    "formal": "Make this text formal and professional",
    "casual": "Keep this text casual and friendly",
    "technical": "Make this text technical and precise",
    "concise": "Make this text concise and brief",
    "creative": "Make this text creative and engaging",
}

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "voxylis.log"

# Paths
CONFIG_DIR = "config"
TEMP_DIR = "temp"
LOGS_DIR = "logs"

# Timeouts
TRANSCRIPTION_TIMEOUT = 120  # 2 minutes for long audio
ENHANCEMENT_TIMEOUT = 60     # 1 minute for long text
INJECTION_TIMEOUT = 5

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds
