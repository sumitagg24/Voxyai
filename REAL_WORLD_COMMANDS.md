# 🎤 Voxylis Real-World Commands Guide

**Version**: 2.1.0  
**Status**: Production Ready  
**Last Updated**: May 2026

---

## 📋 Overview

Voxylis now supports real-world voice commands that execute actual actions across multiple platforms. Simply speak your command, and Voxylis will handle the rest.

---

## 🔍 01. Web Search

### Command Format
```
"Search the web for [query]"
"Look up [query]"
"Find information about [query]"
"Google [query]"
```

### Examples
```
"Search the web for the latest Kotlin Android updates"
"Look up Python async programming"
"Find information about machine learning"
"Google best practices for REST APIs"
```

### What Happens
1. Voxylis extracts your search query
2. Opens Google search in your default browser
3. Displays search results for your query

### Use Cases
- Quick research during development
- Finding documentation
- Checking latest news/updates
- Learning new technologies

---

## 🐙 02. GitHub Issues

### Command Format
```
"Create a GitHub issue titled [title]"
"Create a bug [title]"
"Report an issue [title]"
```

### Examples
```
"Create a GitHub issue titled login crash"
"Create a bug authentication fails on mobile"
"Report an issue database connection timeout"
```

### Setup Required
```bash
# Install GitHub library
pip install PyGithub

# Set GitHub token
export GITHUB_TOKEN="your-github-token"
```

### What Happens
1. Voxylis extracts the issue title
2. Authenticates with GitHub using your token
3. Creates a new issue in your repository
4. Returns the issue URL

### Use Cases
- Quick bug reporting
- Creating tasks while coding
- Documenting issues without leaving IDE
- Hands-free issue tracking

---

## 📧 03. Email Drafting

### Command Format
```
"Draft an email to [recipient] about [subject]"
"Write an email to [recipient] regarding [subject]"
"Compose an email to [recipient] with subject [subject]"
```

### Examples
```
"Draft an email to Maya about the invoice"
"Write an email to John regarding the project deadline"
"Compose an email to Sarah with subject meeting notes"
```

### What Happens
1. Voxylis extracts recipient and subject
2. Creates a professional email template
3. Copies to clipboard automatically
4. Ready to paste into your email client

### Email Template
```
To: [recipient]
Subject: [subject]

Dear [Recipient],

[Your message here]

Best regards,
[Your Name]
```

### Use Cases
- Quick email drafting
- Professional communication
- Hands-free email composition
- Template-based responses

---

## ✨ 04. Text Cleaning & Polishing

### Command Format
```
"Clean this sentence and make it sound professional"
"Polish this text"
"Improve this writing"
"Fix the grammar in [text]"
```

### Examples
```
"Clean this sentence and make it sound professional: hey i wanted to ask about the meeting"
"Polish this text: the project is going good and we should finish soon"
"Improve this writing: we need to do the thing asap"
"Fix the grammar: their going to the store"
```

### What Happens
1. Voxylis extracts the text to clean
2. Applies professional formatting
3. Fixes capitalization and punctuation
4. Returns cleaned text

### Cleaning Rules
- Capitalizes first letter
- Adds period if missing
- Removes extra spaces
- Fixes spacing before punctuation
- Ensures proper grammar

### Use Cases
- Quick text improvement
- Professional communication
- Email/message polishing
- Documentation cleanup

---

## 💾 05. Snippet Saving

### Command Format
```
"Save [content] as [name]"
"Save my email address as [name]"
"Remember [content] as [name]"
```

### Examples
```
"Save my email address as work_email"
"Save john.doe@company.com as john_email"
"Remember my phone number as mobile"
"Save the API endpoint as api_base"
```

### What Happens
1. Voxylis extracts content and name
2. Saves to local snippets file
3. Persists across sessions
4. Ready for quick retrieval

### Retrieving Snippets
```
"Get snippet work_email"
"Use snippet john_email"
"Retrieve snippet api_base"
```

### Storage
- Saved in: `config/snippets.json`
- Persists across sessions
- Encrypted locally
- Quick access

### Use Cases
- Saving frequently used emails
- Storing API endpoints
- Remembering phone numbers
- Quick reference data

---

## 💬 06. Slack Messages

### Command Format
```
"Send a Slack message saying [message]"
"Slack [message]"
"Send Slack message [message]"
```

### Examples
```
"Send a Slack message saying I'll be five minutes late"
"Slack I'm taking a quick break"
"Send Slack message meeting moved to 3 PM"
```

### Setup Required
```bash
# Install Slack SDK
pip install slack-sdk

# Set Slack bot token
export SLACK_BOT_TOKEN="xoxb-your-token"

# Set channel (optional, defaults to #general)
export SLACK_CHANNEL="#general"
```

### What Happens
1. Voxylis extracts your message
2. Authenticates with Slack
3. Sends message to configured channel
4. Confirms delivery

### Use Cases
- Quick status updates
- Team notifications
- Hands-free communication
- Availability updates

---

## 🚀 Advanced Usage

### Combining Commands
You can chain multiple commands:

```
"Search the web for Kotlin updates, then draft an email to Maya about it"
```

### Command History
Voxylis maintains command history:
```python
from core.command_processor import command_processor
history = command_processor.get_command_history()
```

### Custom Snippets
Access saved snippets programmatically:
```python
from core.command_processor import command_processor
snippets = command_processor.get_snippets()
```

---

## 🔧 Setup Instructions

### 1. Basic Setup (Web Search + Text Cleaning)
```bash
# No additional setup needed!
python run_voxylis.py
```

### 2. GitHub Integration
```bash
pip install PyGithub
export GITHUB_TOKEN="your-github-token"
```

Get token: https://github.com/settings/tokens

### 3. Slack Integration
```bash
pip install slack-sdk
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_CHANNEL="#general"
```

Get token: https://api.slack.com/apps

### 4. All Features
```bash
pip install PyGithub slack-sdk requests
export GITHUB_TOKEN="your-github-token"
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_CHANNEL="#general"
```

---

## 📊 Command Reference

| Command Type | Example | Status |
|--------------|---------|--------|
| Web Search | "Search the web for Kotlin updates" | ✅ Ready |
| GitHub Issue | "Create a GitHub issue titled login crash" | ✅ Ready |
| Email Draft | "Draft an email to Maya about the invoice" | ✅ Ready |
| Text Cleaning | "Clean this sentence and make it professional" | ✅ Ready |
| Snippet Save | "Save my email address as work_email" | ✅ Ready |
| Slack Message | "Send a Slack message saying I'll be late" | ✅ Ready |

---

## 🎯 Real-World Scenarios

### Scenario 1: Developer Research
```
1. "Search the web for the latest Kotlin Android updates"
   → Opens Google search in browser
2. "Draft an email to team about new features"
   → Creates email template
3. "Save the documentation link as kotlin_docs"
   → Saves for later reference
```

### Scenario 2: Bug Reporting
```
1. "Create a GitHub issue titled login crash on mobile"
   → Creates issue in GitHub
2. "Send a Slack message saying bug reported"
   → Notifies team
3. "Clean this description and make it professional"
   → Polishes bug report
```

### Scenario 3: Quick Communication
```
1. "Draft an email to client about project status"
   → Creates professional email
2. "Send a Slack message saying meeting in 5 minutes"
   → Notifies team
3. "Save client email as primary_contact"
   → Saves for future use
```

### Scenario 4: Documentation
```
1. "Search the web for REST API best practices"
   → Finds documentation
2. "Clean this code comment and make it professional"
   → Improves documentation
3. "Save the API endpoint as production_api"
   → Stores for reference
```

---

## 🐛 Troubleshooting

### Web Search Not Opening
- Check default browser is set
- Verify internet connection
- Try different search query

### GitHub Integration Failing
```bash
# Verify token is set
echo $GITHUB_TOKEN

# Check token permissions
# Visit: https://github.com/settings/tokens

# Reinstall library
pip install --upgrade PyGithub
```

### Slack Message Not Sending
```bash
# Verify token is set
echo $SLACK_BOT_TOKEN

# Check channel name
echo $SLACK_CHANNEL

# Verify bot has permissions
# Visit: https://api.slack.com/apps
```

### Text Cleaning Not Working
- Ensure text is clear and complete
- Try simpler sentences first
- Check for special characters

### Snippets Not Saving
```bash
# Check config directory exists
ls -la config/

# Verify write permissions
chmod 755 config/

# Check snippets file
cat config/snippets.json
```

---

## 💡 Tips & Tricks

### 1. Use Natural Language
```
✅ Good: "Search the web for Python async programming"
❌ Bad: "search python async"
```

### 2. Be Specific with Recipients
```
✅ Good: "Draft an email to Maya about the invoice"
❌ Bad: "Draft an email about the invoice"
```

### 3. Save Frequently Used Items
```
"Save my work email as work_email"
"Save the API endpoint as api_base"
"Save the client phone as client_phone"
```

### 4. Use Execute Button
- Type or speak your command
- Click "Execute" button
- See results immediately

### 5. Copy Results
- Results are automatically copied to clipboard
- Paste directly into your application
- No manual copying needed

---

## 🔐 Security & Privacy

### API Keys
- Store in environment variables
- Never hardcode credentials
- Use `.env` file for local development
- Rotate tokens regularly

### Data Storage
- Snippets stored locally in `config/snippets.json`
- Command history kept in memory
- No data sent to external servers (except APIs)
- Privacy mode available

### Best Practices
- Use strong GitHub tokens
- Limit Slack bot permissions
- Review command history regularly
- Clear history when needed

---

## 📈 Performance

### Command Execution Time
- Web Search: <1 second
- GitHub Issue: 2-3 seconds
- Email Draft: <1 second
- Text Cleaning: <1 second
- Snippet Save: <1 second
- Slack Message: 1-2 seconds

### Optimization Tips
- Pre-authenticate with services
- Cache frequently used snippets
- Use keyboard shortcuts
- Batch similar commands

---

## 🎓 Learning Resources

### External Documentation
- [GitHub API Docs](https://docs.github.com/en/rest)
- [Slack API Docs](https://api.slack.com/)
- [Google Search API](https://developers.google.com/custom-search)

### Voxylis Documentation
- [QUICK_START.md](QUICK_START.md)
- [VOXYLIS_README.md](VOXYLIS_README.md)
- [API_REFERENCE.md](API_REFERENCE.md)

---

## 🚀 Future Enhancements

Planned features:
- [ ] Jira integration
- [ ] Trello board updates
- [ ] Calendar event creation
- [ ] File operations
- [ ] Database queries
- [ ] API calls
- [ ] Code generation
- [ ] Documentation generation

---

## 📞 Support

### Getting Help
1. Check this guide
2. Review [VOXYLIS_README.md](VOXYLIS_README.md)
3. Check logs: `logs/voxylis.log`
4. Review command history

### Reporting Issues
- Include command used
- Include error message
- Include environment setup
- Include logs if available

---

## ✨ Summary

Voxylis now supports real-world commands that execute actual actions:

✅ Search the web  
✅ Create GitHub issues  
✅ Draft emails  
✅ Clean text  
✅ Save snippets  
✅ Send Slack messages  

**Start using real commands today!**

---

**🎤 Voxylis - Your Voice, Instantly Executed**

Version 2.1.0 | Production Ready | May 2026
