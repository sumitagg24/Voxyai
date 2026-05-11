# 🌐 Voxylis Web Interface Guide

Complete guide to using the Voxylis web dashboard.

---

## 📱 Accessing the Web Interface

Once Voxylis is running:

1. Open your web browser (Chrome, Firefox, Safari, Edge)
2. Go to: **http://localhost:5000**
3. You'll see the Voxylis dashboard

---

## 🏠 Dashboard Overview

The dashboard has 6 main sections:

### 1. **Home Tab**
- Quick statistics (transcriptions today, languages used)
- Recent recordings
- Quick access buttons
- System status

### 2. **Recording Tab**
- Start/stop recording button
- Live transcription display
- Enhancement mode selector
- Copy/save options
- Language selector

### 3. **Q&A Tab**
- Ask questions
- Get instant answers
- View question history
- Save useful answers
- Export answers

### 4. **Settings Tab**
- Language selection
- Hotkey customization
- Wake word configuration
- Microphone testing
- API key management
- Theme selection

### 5. **History Tab**
- View all past recordings
- Search by date or keyword
- Export as text or PDF
- Delete old recordings
- Re-inject text

### 6. **Docs Tab**
- Installation guide
- Feature overview
- Troubleshooting
- Tips & tricks
- FAQ

---

## 🎤 Recording

### Start Recording

**Method 1: Click Button**
1. Go to **Recording** tab
2. Click **Start Recording** button
3. Speak clearly
4. Click **Stop Recording**

**Method 2: Use Hotkey**
1. Press your hotkey (Win+Shift by default)
2. Speak clearly
3. Release hotkey or wait 3 seconds

**Method 3: Wake Word**
1. Say your wake word ("Voxy" by default)
2. Voxylis starts listening
3. Speak your text
4. Say "Done" or wait 3 seconds

### View Live Transcription

- As you speak, text appears in real-time
- See confidence level for each word
- Corrections are made automatically

### Enhance Your Text

After recording, choose an enhancement mode:

- **Formal**: Professional, business-ready tone
- **Casual**: Friendly, conversational style
- **Technical**: Precise, technical terminology
- **Concise**: Short, to-the-point version
- **Creative**: Expanded, creative version

### Save or Copy

- **Copy**: Copy text to clipboard
- **Save**: Save to history
- **Export**: Export as text or PDF
- **Share**: Share via email or social media

---

## ❓ Q&A Feature

### Ask a Question

1. Go to **Q&A** tab
2. Type or speak your question
3. Click **Ask**
4. Get instant answer

### View Answer

- Answer appears on screen
- Auto-hides after 5 seconds
- Click to keep visible
- Copy answer to clipboard

### Save Answers

- Click **Save** to save useful answers
- View saved answers in history
- Export all saved answers

### Question History

- View all past questions
- Search by keyword
- Delete old questions
- Export question history

---

## ⚙️ Settings

### Language

1. Go to **Settings** tab
2. Click **Language**
3. Select your language
4. Click **Save**

### Hotkeys

1. Go to **Settings → Hotkeys**
2. Click on a hotkey to change
3. Press your new key combination
4. Click **Save**

Available hotkeys:
- **Record**: Win+Shift (default)
- **Casual Mode**: Win+Alt
- **Technical Mode**: Win+Ctrl
- **Settings**: Win+;

### Wake Word

1. Go to **Settings → Voice**
2. Enter your custom wake word
3. Set sensitivity (0-100%)
4. Click **Save**
5. Test by saying your wake word

### Microphone

1. Go to **Settings → Microphone**
2. Select your microphone
3. Click **Test Microphone**
4. Speak clearly: "Hello, this is a test"
5. Check if audio is captured

### API Keys

1. Go to **Settings → API**
2. Enter your API keys:
   - OpenAI API Key (for Q&A)
   - Groq API Key (for transcription)
3. Click **Save**

### Theme

1. Go to **Settings → Theme**
2. Choose **Light** or **Dark** mode
3. Click **Save**

---

## 📜 History

### View History

1. Go to **History** tab
2. See all past recordings
3. Click on any recording to view details

### Search History

1. Click **Search** button
2. Enter keyword or date
3. View matching recordings

### Export History

1. Select recordings
2. Click **Export**
3. Choose format:
   - **Text**: Plain text file
   - **PDF**: Formatted PDF
   - **CSV**: Spreadsheet format

### Delete History

1. Select recordings
2. Click **Delete**
3. Confirm deletion

### Re-inject Text

1. Click on a recording
2. Click **Re-inject**
3. Text is inserted at cursor position

---

## 📚 Documentation

### Installation Guide
- System requirements
- Installation steps
- Troubleshooting

### Feature Overview
- All features explained
- How to use each feature
- Tips and tricks

### Troubleshooting
- Common issues
- Solutions
- FAQ

### Tips & Tricks
- Best practices
- Advanced features
- Keyboard shortcuts

---

## 🎨 Customization

### Change Theme

1. Settings → Theme
2. Choose Light or Dark
3. Click Save

### Customize Hotkeys

1. Settings → Hotkeys
2. Click on hotkey
3. Press new key combination
4. Click Save

### Set Wake Word

1. Settings → Voice
2. Enter custom word
3. Set sensitivity
4. Click Save

### Choose Language

1. Settings → Language
2. Select language
3. Click Save

---

## 🔐 Privacy & Security

### Your Data
- All recordings stored locally
- No data sent to external servers without permission
- You can delete recordings anytime

### API Keys
- Keep API keys private
- Never share with anyone
- Store securely in Settings
- Change if compromised

### Permissions
- Voxylis needs microphone access
- Voxylis needs internet for AI features
- You can revoke permissions anytime

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+C | Copy text |
| Ctrl+V | Paste text |
| Ctrl+Z | Undo |
| Ctrl+S | Save |
| Ctrl+H | Show history |
| Ctrl+, | Open settings |
| Ctrl+? | Show help |

---

## 🐛 Troubleshooting

### Issue: Web interface won't load
**Solution:**
1. Make sure Voxylis is running
2. Check if browser is up to date
3. Try a different browser
4. Clear browser cache (Ctrl+Shift+Delete)
5. Restart Voxylis

### Issue: Recording not working
**Solution:**
1. Check microphone connection
2. Go to Settings → Test Microphone
3. Allow Voxylis to access microphone
4. Try again

### Issue: Enhancement not working
**Solution:**
1. Check internet connection
2. Verify API key is set
3. Try a different enhancement mode
4. Check logs for errors

### Issue: Q&A not responding
**Solution:**
1. Check internet connection
2. Verify API key is set
3. Try a simpler question
4. Check logs for errors

### Issue: Hotkey not working
**Solution:**
1. Check if hotkey is used by another app
2. Change hotkey in Settings
3. Restart Voxylis
4. Try new hotkey

---

## 📊 Statistics

### View Statistics

1. Go to **Home** tab
2. See today's statistics:
   - Transcriptions today
   - Words transcribed
   - Languages used
   - Enhancement modes used

### Monthly Statistics

1. Go to **Settings → Statistics**
2. View monthly breakdown
3. Export statistics

---

## 🔄 Syncing

### Cloud Sync (Pro Plan)

1. Go to **Settings → Cloud**
2. Sign in to your account
3. Enable **Cloud Sync**
4. Your data syncs automatically

### Manual Backup

1. Go to **Settings → Backup**
2. Click **Backup Now**
3. Choose backup location
4. Backup is created

### Restore Backup

1. Go to **Settings → Backup**
2. Click **Restore**
3. Choose backup file
4. Data is restored

---

## 🎯 Tips & Tricks

### Tip 1: Use Punctuation
Say "period" or "comma" to add punctuation:
- "Hello period" → "Hello."
- "What question mark" → "What?"

### Tip 2: Speak Naturally
- Don't rush your words
- Speak at normal pace
- Use natural pauses

### Tip 3: Quiet Environment
- Record in quiet room
- Close background noise
- Use good microphone

### Tip 4: Batch Recording
- Record multiple sentences
- Use enhancement to format
- Copy all at once

### Tip 5: Custom Wake Word
- Choose unique word
- Avoid common words
- Test multiple times

### Tip 6: Keyboard Shortcuts
- Learn keyboard shortcuts
- Speed up workflow
- Increase productivity

---

## 🆘 Getting Help

### Documentation
- Check **Docs** tab in dashboard
- Read **FAQ** section
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

## 🎉 You're All Set!

Start using the web interface to transform your voice into text!

---

**Happy transcribing! 🎤**

*Transform Your Voice Into Text with Voxylis*

