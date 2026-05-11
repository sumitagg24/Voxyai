# 🚀 Voxylis - How to Run

This guide shows you exactly how to launch Voxylis on your computer.

---

## ⚡ Fastest Way (Recommended)

### Windows
1. Open the Voxylis folder
2. Double-click **`run.bat`**
3. Wait for the message: "📱 Web Interface: http://localhost:5000"
4. Open your browser and go to: **http://localhost:5000**

### macOS/Linux
1. Open Terminal in the Voxylis folder
2. Run: `bash run.sh`
3. Wait for the message: "📱 Web Interface: http://localhost:5000"
4. Open your browser and go to: **http://localhost:5000**

---

## 📋 Step-by-Step Setup (First Time Only)

### Step 1: Install Python

**Windows:**
1. Go to https://www.python.org/downloads/
2. Download Python 3.9 or later
3. Run the installer
4. **IMPORTANT**: Check the box "Add Python to PATH"
5. Click "Install Now"
6. Wait for installation to complete

**macOS:**
1. Open Terminal
2. Run: `brew install python3`
3. Wait for installation to complete

**Linux (Ubuntu/Debian):**
1. Open Terminal
2. Run: `sudo apt-get install python3 python3-pip`
3. Enter your password when prompted

### Step 2: Install Dependencies

**Windows:**
1. Open PowerShell in the Voxylis folder
2. Run: `pip install -r requirements.txt`
3. Wait for all packages to install

**macOS/Linux:**
1. Open Terminal in the Voxylis folder
2. Run: `pip3 install -r requirements.txt`
3. Wait for all packages to install

### Step 3: Run Voxylis

**Windows:**
- Double-click `run.bat`

**macOS/Linux:**
- Run: `bash run.sh`

---

## 🌐 Access the Web Interface

Once Voxylis is running:

1. Open your web browser (Chrome, Firefox, Safari, Edge)
2. Go to: **http://localhost:5000**
3. You should see the Voxylis dashboard

---

## 🎯 What to Do Next

### First Launch
1. The web interface will load
2. You'll see the Voxylis dashboard
3. Go to **Settings** to configure your preferences
4. Test your microphone
5. Try recording your first message

### Common Tasks

**Change Hotkey:**
- Settings → Hotkeys → Click to change

**Set Wake Word:**
- Settings → Voice → Enter custom word

**Test Microphone:**
- Settings → Test Microphone → Speak clearly

**View History:**
- History tab → See all past recordings

---

## 🐛 Troubleshooting

### Issue: "Python not found"
**Solution:**
1. Install Python from https://www.python.org/downloads/
2. Make sure to check "Add Python to PATH"
3. Restart your computer
4. Try again

### Issue: "Port 5000 already in use"
**Solution:**
1. Close other applications using port 5000
2. Or change the port in `web/app.py` (line 45)
3. Restart Voxylis

### Issue: "Module not found"
**Solution:**
1. Run: `pip install -r requirements.txt` (Windows)
2. Or: `pip3 install -r requirements.txt` (macOS/Linux)
3. Restart Voxylis

### Issue: "Microphone not detected"
**Solution:**
1. Check if microphone is connected
2. Go to Settings → Test Microphone
3. Allow Voxylis to access microphone (system will ask)
4. Try again

### Issue: "Web interface won't load"
**Solution:**
1. Make sure Voxylis is running (check terminal)
2. Try a different browser
3. Clear browser cache (Ctrl+Shift+Delete)
4. Restart Voxylis

---

## 🔧 Manual Start (Advanced)

If the startup scripts don't work, you can start manually:

**Windows (PowerShell):**
```powershell
python main.py
```

**macOS/Linux (Terminal):**
```bash
python3 main.py
```

---

## 📊 Checking if Voxylis is Running

### Windows
1. Open PowerShell
2. Run: `netstat -ano | findstr :5000`
3. If you see a result, Voxylis is running

### macOS/Linux
1. Open Terminal
2. Run: `lsof -i :5000`
3. If you see a result, Voxylis is running

---

## 🛑 Stopping Voxylis

### Windows
1. In the terminal/PowerShell window, press **Ctrl+C**
2. Type **Y** and press Enter
3. The application will stop

### macOS/Linux
1. In the Terminal window, press **Ctrl+C**
2. The application will stop

---

## 🔄 Restarting Voxylis

1. Stop Voxylis (see above)
2. Wait 2 seconds
3. Start Voxylis again (double-click run.bat or run.sh)

---

## 📱 Accessing from Other Devices

To access Voxylis from another computer on your network:

1. Find your computer's IP address:
   - Windows: Run `ipconfig` in PowerShell, look for "IPv4 Address"
   - macOS/Linux: Run `ifconfig` in Terminal, look for "inet"

2. On another device, go to: `http://YOUR_IP:5000`
   - Replace YOUR_IP with your computer's IP address

---

## 🔐 Security Notes

- Voxylis runs locally on your computer
- Your data is stored locally
- No data is sent to external servers without your permission
- Keep your API keys private (in Settings)

---

## 📞 Getting Help

If you're stuck:

1. Check the **Troubleshooting** section above
2. Read the **SETUP_INSTRUCTIONS.md** file
3. Check the **Docs** tab in the dashboard
4. Contact support: support@voxylis.com

---

## ✅ Checklist

Before you start, make sure you have:

- [ ] Python 3.9 or later installed
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Microphone connected and working
- [ ] Internet connection (for AI features)
- [ ] Modern web browser (Chrome, Firefox, Safari, Edge)

---

## 🎉 You're Ready!

Once you see "📱 Web Interface: http://localhost:5000" in the terminal, Voxylis is running and ready to use!

Open your browser and start transforming your voice into text.

---

**Happy transcribing! 🎤**

*Transform Your Voice Into Text with Voxylis*

