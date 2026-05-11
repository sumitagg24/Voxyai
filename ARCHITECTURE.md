# Voxylis - Architecture & Design Documentation

## System Overview

Voxylis is built on a three-layer architecture with event-driven communication:

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                      │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ Floating Widget  │  │ Settings Window  │                 │
│  │ (Status/Levels)  │  │ (Configuration)  │                 │
│  └──────────────────┘  └──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Events
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  APPLICATION ORCHESTRATOR                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ AppOrchestrator - Central coordinator & state mgmt   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Events
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PROCESSING PIPELINE                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Hotkey     │  │   Audio      │  │ Transcriber  │      │
│  │  Listener    │→ │  Recorder    │→ │  (Whisper)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                              ▼               │
│                                      ┌──────────────┐        │
│                                      │  Enhancer    │        │
│                                      │   (GPT)      │        │
│                                      └──────────────┘        │
│                                              ▼               │
│                                      ┌──────────────┐        │
│                                      │  Injector    │        │
│                                      │  (System)    │        │
│                                      └──────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. Core Layer (`core/`)

#### AppOrchestrator
- **Purpose**: Central coordinator managing all components
- **Responsibilities**:
  - Initialize and manage all subsystems
  - Handle configuration loading/saving
  - Coordinate audio processing pipeline
  - Emit events for UI updates
  - Manage application lifecycle

#### HotkeyListener
- **Purpose**: Global hotkey detection
- **Responsibilities**:
  - Listen for system-wide hotkey presses
  - Trigger recording start/stop
  - Support hotkey reconfiguration
  - Handle multiple hotkey combinations

#### EventManager
- **Purpose**: Centralized event system
- **Responsibilities**:
  - Subscribe/unsubscribe to events
  - Emit events with data
  - Decouple components
  - Enable real-time UI updates

### 2. Audio Layer (`audio/`)

#### AudioRecorder
- **Purpose**: Real-time audio capture
- **Responsibilities**:
  - Record from microphone
  - Handle multiple audio devices
  - Apply noise filtering
  - Manage audio buffer
  - Calculate audio levels

#### AudioUtils
- **Purpose**: Audio processing utilities
- **Responsibilities**:
  - Noise gate filtering
  - Audio normalization
  - Audio level calculation
  - Silence detection
  - Audio resampling

### 3. AI Layer (`ai/`)

#### Transcriber
- **Purpose**: Speech-to-text conversion
- **Responsibilities**:
  - Call OpenAI Whisper API
  - Convert audio to WAV format
  - Handle multiple languages
  - Manage API errors
  - Return transcribed text

#### TextEnhancer
- **Purpose**: AI-powered text enhancement
- **Responsibilities**:
  - Call OpenAI GPT API
  - Apply enhancement modes
  - Process voice commands
  - Handle batch operations
  - Manage API errors

#### PromptTemplates
- **Purpose**: AI prompt management
- **Responsibilities**:
  - Store enhancement prompts
  - Store command prompts
  - Format prompts with text
  - Support multiple modes

### 4. System Layer (`system/`)

#### TextInjector
- **Purpose**: System-wide text injection
- **Responsibilities**:
  - Inject text at cursor position
  - Simulate keyboard input
  - Handle clipboard operations
  - Provide fallback typing mode
  - Manage injection delays

#### ClipboardManager
- **Purpose**: Clipboard operations
- **Responsibilities**:
  - Copy text to clipboard
  - Read clipboard content
  - Restore original content
  - Clear clipboard
  - Handle clipboard errors

### 5. UI Layer (`ui/`)

#### FloatingWidget
- **Purpose**: Real-time status overlay
- **Responsibilities**:
  - Display recording status
  - Show audio levels
  - Provide visual feedback
  - Support dragging
  - Theme support

#### SettingsWindow
- **Purpose**: Configuration UI
- **Responsibilities**:
  - Display settings tabs
  - Handle user input
  - Validate settings
  - Save configuration
  - Emit settings changes

### 6. Utility Layer (`utils/`)

#### Logger
- **Purpose**: Centralized logging
- **Responsibilities**:
  - Log to file and console
  - Support multiple log levels
  - Format log messages
  - Manage log files

#### Helpers
- **Purpose**: Common utilities
- **Responsibilities**:
  - JSON file operations
  - Directory management
  - Text formatting
  - File operations

## Data Flow

### Recording Pipeline
```
User presses hotkey
    ↓
HotkeyListener detects press
    ↓
AppOrchestrator.on_hotkey_pressed()
    ↓
AudioRecorder.start_recording()
    ↓
Audio captured in real-time
    ↓
User releases hotkey
    ↓
HotkeyListener detects release
    ↓
AppOrchestrator.on_hotkey_released()
    ↓
AudioRecorder.stop_recording()
    ↓
Audio processing begins
```

### Processing Pipeline
```
Raw audio data
    ↓
Transcriber.transcribe()
    ↓
Raw transcript
    ↓
TextEnhancer.enhance()
    ↓
Enhanced text
    ↓
TextInjector.inject_text()
    ↓
Text at cursor position
```

## Event System

### Event Types
```python
Events.RECORDING_STARTED
Events.RECORDING_STOPPED
Events.RECORDING_CANCELLED
Events.AUDIO_LEVEL_CHANGED
Events.TRANSCRIPTION_STARTED
Events.TRANSCRIPTION_COMPLETED
Events.TRANSCRIPTION_FAILED
Events.ENHANCEMENT_STARTED
Events.ENHANCEMENT_COMPLETED
Events.ENHANCEMENT_FAILED
Events.INJECTION_STARTED
Events.INJECTION_COMPLETED
Events.INJECTION_FAILED
Events.HOTKEY_PRESSED
Events.HOTKEY_RELEASED
Events.SETTINGS_CHANGED
Events.ERROR_OCCURRED
```

### Event Flow
```
Component emits event
    ↓
EventManager broadcasts to subscribers
    ↓
UI components update
    ↓
User sees real-time feedback
```

## Configuration System

### Settings Hierarchy
1. Default values (in code)
2. config/settings.json file
3. Environment variables
4. Runtime updates via UI

### Configuration Keys
```json
{
  "hotkey": "ctrl+shift+v",
  "language": "en",
  "enhancement_mode": "formal",
  "enable_ai_enhancement": true,
  "enable_cloud_mode": true,
  "openai_api_key": "",
  "audio_device": null,
  "sample_rate": 16000,
  "auto_inject": true,
  "show_floating_widget": true,
  "theme": "dark",
  "startup_on_boot": false,
  "log_level": "INFO",
  "privacy_mode": "cloud",
  "max_history": 100
}
```

## Error Handling

### Strategy
- Try-catch blocks in all critical sections
- Graceful degradation (fallback modes)
- Comprehensive logging
- User-friendly error messages
- Event-based error reporting

### Error Recovery
```
Error occurs
    ↓
Log error with context
    ↓
Emit ERROR_OCCURRED event
    ↓
UI displays error message
    ↓
System continues running
    ↓
User can retry operation
```

## Performance Optimization

### Latency Targets
- Hotkey detection: < 50ms
- Recording start: < 100ms
- Audio capture: Real-time
- Transcription: 2-5 seconds
- Enhancement: 1-3 seconds
- Text injection: < 500ms
- **Total pipeline: 3-8 seconds**

### Optimization Techniques
1. **Async Processing**: Non-blocking operations
2. **Threading**: Background recording and processing
3. **Buffering**: Efficient audio buffering
4. **Caching**: Configuration caching
5. **Lazy Loading**: Components initialized on demand

## Extensibility

### Plugin Architecture (Future)
```python
class Plugin:
    def on_transcription_complete(self, text):
        pass
    
    def on_enhancement_complete(self, text):
        pass
    
    def on_injection_complete(self, text):
        pass
```

### Custom Enhancement Modes
Edit `ai/prompt_templates.py`:
```python
ENHANCEMENT_PROMPTS["custom"] = "Your custom prompt..."
```

### Custom Voice Commands
Edit `ai/prompt_templates.py`:
```python
COMMAND_PROMPTS["custom_command"] = "Your command prompt..."
```

## Security Considerations

### API Key Management
- Never hardcode API keys
- Use environment variables
- Support settings file (with warnings)
- Mask in UI

### Data Privacy
- No permanent storage of audio
- No permanent storage of transcripts
- Clipboard restored after injection
- Optional local mode (future)

### System Integration
- Minimal system permissions
- No registry modifications
- No system file modifications
- Clean uninstallation

## Testing Strategy

### Unit Tests
- Audio processing functions
- Text enhancement logic
- Configuration management
- Event system

### Integration Tests
- Full recording pipeline
- Text injection in different apps
- Settings persistence
- Error recovery

### Manual Tests
- Different microphones
- Different applications
- Different languages
- Different enhancement modes

## Deployment

### Development
```bash
python main.py
```

### Production (Executable)
```bash
pyinstaller build_script.spec
```

### Distribution
- GitHub releases
- Installer package
- Portable executable
- System package (future)

## Future Enhancements

1. **Local Models**: Support for local Whisper/LLM
2. **Streaming**: Real-time transcription display
3. **Commands**: Voice command system
4. **History**: Text history and export
5. **Plugins**: Plugin system for extensions
6. **Cloud Sync**: Settings synchronization
7. **Analytics**: Usage analytics
8. **Multi-language**: Auto-language detection

---

**Architecture designed for scalability, maintainability, and extensibility.**
