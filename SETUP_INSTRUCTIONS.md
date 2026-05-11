# 🚀 Voxylis - Setup & Run Guide

Welcome to Voxylis! This guide will help you get up and running in just a few minutes.

---

## ⚡ Quick Start (3 Steps)

### Step 1: Download & Extract
1. Download Voxylis from the website
2. Extract the folder to your desired location
3. Open the folder in your file explorer

### Step 2: Install Dependencies
Choose your operating system:

**Windows:**
1. Open PowerShell in the Voxylis folder
2. Run: `python -m pip install -r requirements.txt`
3. Wait for installation to complete

**macOS/Linux:**
1. Open Terminal in the Voxylis folder
2. Run: `pip install -r requirements.txt`
3. Wait for installation to complete

### Step 3: Launch Voxylis
Choose your operating system:

**Windows:**
- Double-click `quick_start.bat`
- Or run in PowerShell: `python main.py`

**macOS/Linux:**
- Double-click `quick_start.sh`
- Or run in Terminal: `python main.py`

---

## 🌐 Access the Web Interface

Once Voxylis is running:

1. Open your web browser (Chrome, Firefox, Safari, Edge)
2. Go to: **http://localhost:5000**
3. You'll see the Voxylis dashboard

---

## 🎯 First Time Setup

### 1. Configure Your Settings
- Click **Settings** in the dashboard
- Set your preferred language
- Choose your enhancement mode
- Customize your hotkey (default: Win+Shift)

### 2. Set Your Wake Word
- Go to **Settings → Voice**
- Enter your custom wake word (default: "Voxy")
- Click **Save**

### 3. Test the Microphone
- Click **Test Microphone** in Settings
- Speak clearly: "Hello, this is a test"
- Check if audio is captured correctly

### 4. Try a Recording
- Press your hotkey (Win+Shift by default) or click the minion widget
- Speak naturally
- Wait 3-8 seconds for transcription
- See your text appear on screen

---

## 🎮 How to Use Voxylis

### Recording Methods

**Method 1: Hotkey (Fastest)**
- Press **Win+Shift** (Windows) or **Cmd+Shift** (macOS)
- Speak your text
- Release to stop recording

**Method 2: Wake Word**
- Say "Voxy" (or your custom wake word)
- Voxylis will start listening
- Speak your text
- Say "Done" or wait 3 seconds to stop

**Method 3: Click Widget**
- Click the minion widget on your screen
- Speak your text
- Click again to stop

### Enhancement Modes

After recording, choose how to enhance your text:

- **Formal**: Professional, business-ready tone
- **Casual**: Friendly, conversational style
- **Technical**: Precise, technical terminology
- **Concise**: Short, to-the-point version
- **Creative**: Expanded, creative version

### Q&A Feature

Ask Voxylis questions and get instant answers:

1. Click **Ask a Question** in the dashboard
2. Type or speak your question
3. Get an instant answer displayed on screen
4. Answer auto-hides after 5 seconds

---

## ⚙️ Configuration

### Change Hotkey

1. Open dashboard
2. Go to **Settings → Hotkeys**
3. Click on a hotkey to change it
4. Press your new key combination
5. Click **Save**

Available hotkeys:
- **Record**: Win+Shift (default)
- **Casual Mode**: Win+Alt
- **Technical Mode**: Win+Ctrl

### Change Wake Word

1. Open dashboard
2. Go to **Settings → Voice**
3. Enter new wake word
4. Click **Save**
5. Test by saying your new wake word

### Change Language

1. Open dashboard
2. Go to **Settings → Language**
3. Select your language
4. Click **Save**

---

## 🐛 Troubleshooting

### Issue: "Port 5000 already in use"
**Solution:**
1. Close other applications using port 5000
2. Or change the port in settings
3. Restart Voxylis

### Issue: "Microphone not detected"
**Solution:**
1. Check if microphone is connected
2. Go to Settings → Test Microphone
3. Allow Voxylis to access microphone (Windows/macOS will ask)
4. Try again

### Issue: "Hotkey not working"
**Solution:**
1. Check if hotkey is already used by another app
2. Change hotkey in Settings
3. Restart Voxylis
4. Try the new hotkey

### Issue: "Text not appearing"
**Solution:**
1. Check microphone volume
2. Speak clearly and slowly
3. Check internet connection (for AI enhancement)
4. Try a different language
5. Check logs for errors

### Issue: "Web interface not loading"
**Solution:**
1. Make sure Voxylis is running
2. Check if browser is up to date
3. Try a different browser
4. Clear browser cache (Ctrl+Shift+Delete)
5. Restart Voxylis

### Issue: "Enhancement not working"
**Solution:**
1. Check internet connection
2. Verify API key is set (Settings → API)
3. Try a different enhancement mode
4. Check logs for errors

---

## 📊 Dashboard Overview

### Home Tab
- Quick stats (transcriptions today, languages used)
- Recent recordings
- Quick access buttons

### Recording Tab
- Start/stop recording
- View live transcription
- Choose enhancement mode
- Copy or save text

### Q&A Tab
- Ask questions
- Get instant answers
- View question history
- Save useful answers

### Settings Tab
- Language selection
- Hotkey customization
- Wake word configuration
- Microphone testing
- API key management

### History Tab
- View all past recordings
- Search by date or keyword
- Export as text or PDF
- Delete old recordings

### Docs Tab
- Installation guide
- Feature overview
- Troubleshooting
- Tips & tricks
- FAQ

---

## 🔐 Privacy & Security

### Your Data
- All recordings are stored locally on your computer
- No data is sent to external servers without your permission
- You can delete recordings anytime

### API Keys
- Keep your API keys private
- Never share them with anyone
- Store them securely in Settings
- Change them if compromised

### Permissions
- Voxylis needs microphone access to record
- Voxylis needs internet access for AI enhancement
- You can revoke permissions anytime in system settings

---

## 📱 System Requirements

### Windows
- Windows 10 or later
- 4GB RAM minimum (8GB recommended)
- 500MB free disk space
- Microphone (built-in or external)
- Internet connection (for AI features)

### macOS
- macOS 10.14 or later
- 4GB RAM minimum (8GB recommended)
- 500MB free disk space
- Microphone (built-in or external)
- Internet connection (for AI features)

### Linux
- Ubuntu 18.04 or later
- 4GB RAM minimum (8GB recommended)
- 500MB free disk space
- Microphone (built-in or external)
- Internet connection (for AI features)

---

## 🎓 Tips & Tricks

### Tip 1: Use Punctuation
Say "period" or "comma" to add punctuation:
- "Hello period" → "Hello."
- "What question mark" → "What?"

### Tip 2: Speak Naturally
- Don't rush your words
- Speak at normal pace
- Use natural pauses between sentences

### Tip 3: Quiet Environment
- Record in a quiet room
- Close background noise sources
- Use a good quality microphone

### Tip 4: Custom Wake Word
- Choose a unique word
- Avoid common words
- Test it multiple times

### Tip 5: Batch Recording
- Record multiple sentences at once
- Use enhancement to format them
- Copy all at once

### Tip 6: Keyboard Shortcuts
- **Ctrl+C**: Copy text
- **Ctrl+V**: Paste text
- **Ctrl+Z**: Undo last action
- **Ctrl+S**: Save recording

---

## 🆘 Getting Help

### Documentation
- Check the **Docs** tab in the dashboard
- Read the **FAQ** section
- View **Tips & Tricks**

### Troubleshooting
- See **Troubleshooting** section above
- Check application logs
- Try restarting Voxylis

### Contact Support
- Email: support@voxylis.com
- Discord: discord.gg/voxylis
- GitHub: github.com/voxylis/voxylis

---

## 🔄 Updating Voxylis

### Check for Updates
1. Open dashboard
2. Go to **Settings → About**
3. Click **Check for Updates**
4. Follow the prompts

### Manual Update
1. Download latest version from website
2. Extract to a new folder
3. Copy your settings from old folder
4. Delete old folder
5. Use new folder

---

## 🎉 You're All Set!

Congratulations! Voxylis is now ready to use. Start recording and transforming your voice into text!

### Next Steps
1. Try recording your first message
2. Explore different enhancement modes
3. Customize your hotkey
4. Set your wake word
5. Check out the Q&A feature

---

## 📞 Quick Links

- **Website**: https://voxylis.com
- **Documentation**: https://voxylis.com/docs
- **Support**: support@voxylis.com
- **Discord**: discord.gg/voxylis
- **GitHub**: github.com/voxylis/voxylis

---

**Happy transcribing! 🎤**

*Transform Your Voice Into Text with Voxylis*

