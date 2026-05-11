# Voxylis - API Reference

## Core Components API

### AppOrchestrator

Main application coordinator managing all components.

```python
from core.app_orchestrator import AppOrchestrator

# Initialize
orchestrator = AppOrchestrator(config_path="config/settings.json")

# Start application
orchestrator.start() -> bool

# Stop application
orchestrator.stop() -> bool

# Update configuration
orchestrator.update_config(key: str, value: Any) -> bool

# Get configuration
orchestrator.get_config(key: str = None) -> Any

# Get application status
orchestrator.get_status() -> dict
```

### HotkeyListener

Global hotkey detection and management.

```python
from core.hotkey_listener import HotkeyListener

# Initialize
listener = HotkeyListener(hotkey="ctrl+shift+v")

# Start listening
listener.start_listening() -> bool

# Stop listening
listener.stop_listening() -> bool

# Change hotkey
listener.set_hotkey(new_hotkey: str) -> bool

# Set callbacks
listener.on_hotkey_pressed = callback_function
listener.on_hotkey_released = callback_function
```

### EventManager

Centralized event system for component communication.

```python
from core.event_manager import event_manager, Events

# Subscribe to event
event_manager.subscribe(Events.RECORDING_STARTED, callback)

# Unsubscribe from event
event_manager.unsubscribe(Events.RECORDING_STARTED, callback)

# Emit event
event_manager.emit(Events.RECORDING_STARTED)

# Emit with data
event_manager.emit(Events.TRANSCRIPTION_COMPLETED, transcript_text)

# Clear listeners
event_manager.clear_listeners(event_name=None)
```

## Audio Components API

### AudioRecorder

Real-time audio recording from microphone.

```python
from audio.recorder import AudioRecorder
import numpy as np

# Initialize
recorder = AudioRecorder(device_id=None)

# List available devices
devices = recorder.list_devices() -> list

# Start recording
recorder.start_recording() -> bool

# Stop recording and get audio
audio_data = recorder.stop_recording() -> Optional[np.ndarray]

# Cancel recording
recorder.cancel_recording()

# Get recording duration
duration = recorder.get_recording_duration() -> float

# Set audio chunk callback
recorder.on_audio_chunk = lambda level: print(f"Level: {level}")
```

### AudioUtils

Audio processing utilities.

```python
from audio.audio_utils import (
    apply_noise_gate,
    normalize_audio,
    calculate_audio_level,
    detect_silence,
    resample_audio
)
import numpy as np

# Apply noise gate
filtered = apply_noise_gate(audio_data, threshold=0.02)

# Normalize audio
normalized = normalize_audio(audio_data)

# Calculate audio level (0-100)
level = calculate_audio_level(audio_data) -> float

# Detect silence
is_silent = detect_silence(audio_data, threshold=0.01) -> bool

# Resample audio
resampled = resample_audio(audio_data, orig_sr=16000, target_sr=8000)
```

## AI Components API

### Transcriber

Speech-to-text conversion using OpenAI Whisper.

```python
from ai.transcriber import Transcriber
import numpy as np

# Initialize
transcriber = Transcriber(api_key="your-api-key")

# Transcribe audio
text = transcriber.transcribe(
    audio_data: np.ndarray,
    language: str = "en",
    temperature: float = 0.0
) -> Optional[str]
```

### TextEnhancer

AI-powered text enhancement using GPT.

```python
from ai.enhancer import TextEnhancer

# Initialize
enhancer = TextEnhancer(api_key="your-api-key")

# Enhance text
enhanced = enhancer.enhance(
    text: str,
    mode: str = "formal"
) -> Optional[str]

# Process voice command
result = enhancer.process_command(
    text: str,
    command: str
) -> Optional[str]

# Batch enhance
results = enhancer.batch_enhance(
    texts: list,
    mode: str = "formal"
) -> list
```

### PromptTemplates

AI prompt management.

```python
from ai.prompt_templates import (
    get_enhancement_prompt,
    get_command_prompt,
    ENHANCEMENT_PROMPTS,
    COMMAND_PROMPTS
)

# Get enhancement prompt
prompt = get_enhancement_prompt(mode="formal", text="your text")

# Get command prompt
prompt = get_command_prompt(command="email", text="your text")

# Available modes
modes = list(ENHANCEMENT_PROMPTS.keys())
# ['formal', 'casual', 'technical', 'concise', 'creative']

# Available commands
commands = list(COMMAND_PROMPTS.keys())
# ['email', 'bullet_points', 'summary', 'code_comment']
```

## System Components API

### TextInjector

System-wide text injection at cursor position.

```python
from system.injector import TextInjector

# Initialize
injector = TextInjector()

# Inject text
success = injector.inject_text(
    text: str,
    restore_clipboard: bool = True
) -> bool

# Inject with delay
success = injector.inject_text_with_delay(
    text: str,
    delay: float = 0.5,
    restore_clipboard: bool = True
) -> bool

# Type text character by character
success = injector.type_text(
    text: str,
    speed: float = 0.05
) -> bool

# Inject with fallback
success = injector.inject_with_fallback(text: str) -> bool
```

### ClipboardManager

Clipboard operations.

```python
from system.clipboard_manager import ClipboardManager

# Initialize
clipboard = ClipboardManager()

# Copy to clipboard
success = clipboard.copy_to_clipboard(text: str) -> bool

# Get clipboard content
content = clipboard.get_clipboard_content() -> Optional[str]

# Restore original clipboard
success = clipboard.restore_clipboard() -> bool

# Clear clipboard
success = clipboard.clear_clipboard() -> bool
```

## UI Components API

### FloatingWidget

Floating overlay widget for status display.

```python
from ui.overlay import FloatingWidget

# Initialize
widget = FloatingWidget()

# Show/hide
widget.show()
widget.hide()
widget.toggle_visibility()

# Set status
widget.set_status(status: str, info: str = "")

# Set audio level
widget.set_audio_level(level: float)

# Set recording state
widget.set_recording(is_recording: bool)

# Set processing state
widget.set_processing(is_processing: bool)

# Set theme
widget.set_theme(theme: str)  # "dark" or "light"
```

### SettingsWindow

Settings configuration window.

```python
from ui.settings_window import SettingsWindow

# Initialize
settings_window = SettingsWindow(config: dict)

# Show window
settings_window.show()

# Connect signals
settings_window.settings_changed.connect(on_settings_changed)
settings_window.closed.connect(on_window_closed)

# Save settings
settings_window.save_settings()
```

## Utility Components API

### Logger

Centralized logging system.

```python
from utils.logger import (
    log_info,
    log_error,
    log_warning,
    log_debug,
    logger
)

# Log messages
log_info("Information message")
log_error("Error message", exc_info=True)
log_warning("Warning message")
log_debug("Debug message")

# Get logger instance
logger = logger
logger.setLevel("DEBUG")
```

### Helpers

Common utility functions.

```python
from utils.helpers import (
    load_json,
    save_json,
    ensure_directories,
    format_duration,
    sanitize_filename,
    truncate_text
)

# JSON operations
config = load_json("config.json")
save_json("config.json", config)

# Directory management
ensure_directories()

# Text formatting
duration_str = format_duration(125.5)  # "2.1m"
filename = sanitize_filename("file<name>.txt")  # "file_name_.txt"
short_text = truncate_text("long text...", max_length=10)  # "long te..."
```

## Configuration API

### Constants

Global application constants.

```python
from config.constants import (
    APP_NAME,
    APP_VERSION,
    SAMPLE_RATE,
    CHUNK_SIZE,
    HOTKEY_DEFAULT,
    ENHANCEMENT_MODES,
    MAX_RECORDING_DURATION,
    TRANSCRIPTION_TIMEOUT,
    ENHANCEMENT_TIMEOUT
)

# Access constants
print(APP_NAME)  # "Voxylis"
print(SAMPLE_RATE)  # 16000
print(ENHANCEMENT_MODES)  # dict of modes
```

### Settings

User configuration management.

```python
# Load settings
from utils.helpers import load_json
settings = load_json("config/settings.json")

# Available settings
{
    "hotkey": "ctrl+shift+v",
    "language": "en",
    "enhancement_mode": "formal",
    "enable_ai_enhancement": True,
    "openai_api_key": "",
    "audio_device": None,
    "sample_rate": 16000,
    "auto_inject": True,
    "show_floating_widget": True,
    "theme": "dark",
    "startup_on_boot": False,
    "log_level": "INFO",
    "privacy_mode": "cloud",
    "max_history": 100
}
```

## Event Types

```python
from core.event_manager import Events

# Recording events
Events.RECORDING_STARTED
Events.RECORDING_STOPPED
Events.RECORDING_CANCELLED

# Audio events
Events.AUDIO_LEVEL_CHANGED

# Transcription events
Events.TRANSCRIPTION_STARTED
Events.TRANSCRIPTION_COMPLETED
Events.TRANSCRIPTION_FAILED

# Enhancement events
Events.ENHANCEMENT_STARTED
Events.ENHANCEMENT_COMPLETED
Events.ENHANCEMENT_FAILED

# Injection events
Events.INJECTION_STARTED
Events.INJECTION_COMPLETED
Events.INJECTION_FAILED

# Hotkey events
Events.HOTKEY_PRESSED
Events.HOTKEY_RELEASED

# System events
Events.SETTINGS_CHANGED
Events.ERROR_OCCURRED
```

## Usage Examples

### Example 1: Basic Recording and Transcription

```python
from core.app_orchestrator import AppOrchestrator
from core.event_manager import event_manager, Events

# Initialize
orchestrator = AppOrchestrator()

# Subscribe to events
def on_transcription_complete(text):
    print(f"Transcribed: {text}")

event_manager.subscribe(Events.TRANSCRIPTION_COMPLETED, on_transcription_complete)

# Start application
orchestrator.start()

# User presses hotkey, speaks, releases hotkey
# Transcription event fires automatically
```

### Example 2: Custom Enhancement

```python
from ai.enhancer import TextEnhancer

# Initialize
enhancer = TextEnhancer(api_key="your-key")

# Enhance text
text = "um hello world this is a test"
enhanced = enhancer.enhance(text, mode="formal")
print(enhanced)  # "Hello world, this is a test."
```

### Example 3: Text Injection

```python
from system.injector import TextInjector

# Initialize
injector = TextInjector()

# Inject text at cursor
text = "This is the injected text"
success = injector.inject_text(text)

if success:
    print("Text injected successfully")
else:
    print("Injection failed")
```

### Example 4: Configuration Management

```python
from core.app_orchestrator import AppOrchestrator

# Initialize
orchestrator = AppOrchestrator()

# Get current config
hotkey = orchestrator.get_config("hotkey")
print(f"Current hotkey: {hotkey}")

# Update config
orchestrator.update_config("hotkey", "alt+shift+v")
orchestrator.update_config("enhancement_mode", "casual")

# Get all config
all_config = orchestrator.get_config()
print(all_config)
```

### Example 5: Event Handling

```python
from core.event_manager import event_manager, Events

# Define callbacks
def on_recording_started():
    print("Recording started")

def on_recording_stopped():
    print("Recording stopped")

def on_audio_level_changed(level):
    print(f"Audio level: {level}%")

# Subscribe
event_manager.subscribe(Events.RECORDING_STARTED, on_recording_started)
event_manager.subscribe(Events.RECORDING_STOPPED, on_recording_stopped)
event_manager.subscribe(Events.AUDIO_LEVEL_CHANGED, on_audio_level_changed)

# Emit events
event_manager.emit(Events.RECORDING_STARTED)
event_manager.emit(Events.AUDIO_LEVEL_CHANGED, 75.5)
event_manager.emit(Events.RECORDING_STOPPED)
```

## Error Handling

All components use try-catch blocks and return None or False on error.

```python
# Check for errors
transcript = transcriber.transcribe(audio_data)
if transcript is None:
    print("Transcription failed")

# Check success
success = injector.inject_text(text)
if not success:
    print("Injection failed")

# Check logs for details
from utils.logger import logger
# Check logs/voxylis.log for error details
```

## Performance Considerations

- Audio recording: Real-time, non-blocking
- Transcription: 2-5 seconds (API dependent)
- Enhancement: 1-3 seconds (API dependent)
- Text injection: < 500ms
- Total pipeline: 3-8 seconds

## Thread Safety

- AudioRecorder uses threading for recording
- EventManager is thread-safe
- All API calls are blocking (consider async in future)

## Dependencies

- numpy: Audio processing
- sounddevice: Audio recording
- openai: API client
- PyQt5: UI framework
- pynput: Hotkey detection
- keyboard: Keyboard automation
- pyperclip: Clipboard management

---

**Complete API Reference for Voxylis**
