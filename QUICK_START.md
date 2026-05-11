# 🚀 Voxylis Quick Start Guide

**Get started in 5 minutes!**

---

## 1️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install PyQt5 pynput groq openai numpy
```

---

## 2️⃣ Get API Key

1. Visit [https://console.groq.com](https://console.groq.com)
2. Sign up (free)
3. Create API key
4. Copy your key

---

## 3️⃣ Set Environment Variable

### Windows (PowerShell)
```powershell
$env:GROQ_API_KEY = "your-groq-api-key"
```

### Windows (CMD)
```cmd
set GROQ_API_KEY=your-groq-api-key
```

### macOS/Linux
```bash
export GROQ_API_KEY="your-groq-api-key"
```

---

## 4️⃣ Launch Application

```bash
python run_voxylis.py
```

Or directly:
```bash
python ui/voxylis_app.py
```

---

## 5️⃣ Start Using

1. **Activate**: Press and hold `Ctrl + Win`
2. **Speak**: Say "Hey Voxy" + your command
3. **Release**: Release the hotkey
4. **Copy**: Click "Copy" button to copy result

---

## 📝 Example Commands

```
"Hey Voxy, write an email to my client thanking for connecting on zoom call"

"Hey Voxy, draft a message asking team to gather in pantry area at 3PM"

"Hey Voxy, what is the capital of France?"
```

---

## ⚙️ Settings

### Change Language
1. Go to Settings page
2. Select language from chips
3. Supports 99+ languages

### Change Hotkey
1. Go to Settings
2. Click "Change" next to Keyboard Shortcuts
3. Enter new hotkey

### Enable Privacy Mode
1. Go to Settings
2. Toggle "Privacy Mode"
3. Transcripts won't be stored

---

## 🐛 Troubleshooting

### Hotkey Not Working
- Check if another app uses Ctrl+Win
- Try a different hotkey in settings
- Restart the application

### No Transcription
- Verify GROQ_API_KEY is set
- Check internet connection
- Check microphone settings

### Application Won't Start
```bash
# Check Python version
python --version

# Check dependencies
pip list | grep PyQt5

# Run with error output
python ui/voxylis_app.py
```

---

## 📚 Full Documentation

- [Complete README](VOXYLIS_README.md)
- [Setup Guide](VOXYLIS_PRODUCTION_SETUP.md)
- [API Reference](API_REFERENCE.md)
- [Architecture](ARCHITECTURE.md)

---

## 🎯 Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Start/Stop Recording | `Ctrl + Win` (hold/release) |
| Open Voxylis | `Ctrl + Win` (double tap) |
| Copy Last Result | `Ctrl + Win + C` |

---

## 🌍 Supported Languages

**Primary**: English, Spanish, French, German, Portuguese  
**Indian**: Hindi, Punjabi, Bengali, Gujarati, Tamil, Telugu  
**Middle East**: Arabic, Urdu, Farsi  
**Asian**: Japanese, Chinese, Korean, Thai, Vietnamese  
**And 70+ more languages**

---

## 💡 Tips

1. **Speak clearly** - Better audio = better transcription
2. **Use specific language** - Select language for better accuracy
3. **Try different styles** - Professional, Casual, Technical, Minimal
4. **Add custom words** - Use Dictionary for domain-specific terms
5. **Enable privacy mode** - For sensitive information

---

## 🆘 Need Help?

1. Check logs: `logs/voxylis.log`
2. Review settings: `config/settings.json`
3. Read documentation: [VOXYLIS_README.md](VOXYLIS_README.md)
4. Test hotkey: `python -c "from core.hotkey_listener import HotkeyListener; h = HotkeyListener(); h.start_listening()"`

---

## ✨ You're All Set!

Press `Ctrl + Win` and start speaking! 🎤

---

**Voxylis v2.1.0 - Production Ready**
