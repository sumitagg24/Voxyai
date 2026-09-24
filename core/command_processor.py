"""
Voxylis Command Processor
Handles real voice commands and executes them across multiple platforms
Supports: Web search, GitHub, Email, Text processing, Snippets, Slack, etc.
"""

import os
import re
import json
import webbrowser
from typing import Optional, Dict, Tuple
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

# Try to import optional dependencies
try:
    import requests  # noqa: F401 — availability probe, used via REQUESTS_AVAILABLE

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from slack_sdk import WebClient

    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False

try:
    from github import Github

    GITHUB_AVAILABLE = True
except ImportError:
    GITHUB_AVAILABLE = False


class CommandProcessor:
    """Process and execute voice commands"""

    def __init__(self):
        try:
            from utils.helpers import get_base_dir

            base = get_base_dir()
        except ImportError:
            base = Path(".")
        self.snippets_file = Path(base) / "config" / "snippets.json"
        self.snippets = self._load_snippets()
        self.command_history = []
        self.max_history = 100

    def _load_snippets(self) -> Dict[str, str]:
        """Load saved snippets from file"""
        if self.snippets_file.exists():
            try:
                with open(self.snippets_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_snippets(self):
        """Save snippets to file"""
        try:
            with open(self.snippets_file, "w") as f:
                json.dump(self.snippets, f, indent=2)
        except Exception as e:
            print(f"Error saving snippets: {e}")

    def process_command(self, text: str) -> Tuple[bool, str]:
        """
        Process a voice command and execute it
        Returns: (success, result_message)
        """
        text = text.strip()
        self.command_history.append({"command": text, "timestamp": datetime.now().isoformat()})

        # Keep history size manageable
        if len(self.command_history) > self.max_history:
            self.command_history = self.command_history[-self.max_history :]

        # Route to appropriate handler
        if self._is_web_search(text):
            return self._handle_web_search(text)
        elif self._is_github_command(text):
            return self._handle_github(text)
        elif self._is_email_command(text):
            return self._handle_email(text)
        elif self._is_text_processing(text):
            return self._handle_text_processing(text)
        elif self._is_snippet_command(text):
            return self._handle_snippet(text)
        elif self._is_slack_command(text):
            return self._handle_slack(text)
        else:
            return (
                False,
                "Command not recognized. Try: search, create issue, draft email, clean text, save snippet, or send Slack message",  # noqa: E501
            )

    # ── Web Search ──────────────────────────────────────────────────────────

    def _is_web_search(self, text: str) -> bool:
        """Check if command is a web search"""
        patterns = [
            r"search.*for",
            r"look.*up",
            r"find.*about",
            r"google",
            r"search the web",
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _handle_web_search(self, text: str) -> Tuple[bool, str]:
        """Handle web search command"""
        try:
            # Extract search query
            query = self._extract_search_query(text)
            if not query:
                return False, "Could not extract search query"

            # Open in default browser
            search_url = f"https://www.google.com/search?q={quote(query)}"
            webbrowser.open(search_url)

            return True, f"Searching for: {query}"
        except Exception as e:
            return False, f"Search failed: {str(e)}"

    def _extract_search_query(self, text: str) -> Optional[str]:
        """Extract search query from command"""
        # Remove common prefixes
        query = re.sub(
            r"^(search|look|find|google|search the web)\s+(for|about|up)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        query = query.strip()
        return query if query else None

    # ── GitHub ──────────────────────────────────────────────────────────────

    def _is_github_command(self, text: str) -> bool:
        """Check if command is GitHub-related"""
        patterns = [
            r"create.*issue",
            r"github",
            r"create.*bug",
            r"report.*issue",
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _handle_github(self, text: str) -> Tuple[bool, str]:
        """Handle GitHub commands"""
        if not GITHUB_AVAILABLE:
            return (
                False,
                "GitHub integration not available. Install: pip install PyGithub",
            )

        try:
            # Extract issue title
            title = self._extract_github_title(text)
            if not title:
                return False, "Could not extract issue title"

            # Get GitHub token
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                return False, "GITHUB_TOKEN environment variable not set"

            # Create issue
            g = Github(token)
            repo = g.get_user().get_repos()[0]  # Use first repo

            issue = repo.create_issue(
                title=title,
                body=f"Created via Voxylis voice command at {datetime.now().isoformat()}",
            )

            return True, f"Issue created: {issue.html_url}"
        except Exception as e:
            return False, f"GitHub error: {str(e)}"

    def _extract_github_title(self, text: str) -> Optional[str]:
        """Extract GitHub issue title"""
        # Remove common prefixes
        title = re.sub(
            r"^(create|report)\s+(a\s+)?(github\s+)?(issue|bug)\s+(titled|called)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        title = title.strip()
        return title if title else None

    # ── Email ───────────────────────────────────────────────────────────────

    def _is_email_command(self, text: str) -> bool:
        """Check if command is email-related"""
        patterns = [
            r"draft.*email",
            r"write.*email",
            r"email.*to",
            r"compose.*email",
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _handle_email(self, text: str) -> Tuple[bool, str]:
        """Handle email drafting"""
        try:
            # Extract recipient and subject
            recipient, subject = self._extract_email_info(text)

            if not recipient or not subject:
                return False, "Could not extract recipient or subject"

            # Create email draft
            email_draft = self._create_email_draft(recipient, subject)

            # Save to clipboard
            import subprocess

            if os.name == "nt":  # Windows
                process = subprocess.Popen(["clip"], stdin=subprocess.PIPE)
                process.communicate(email_draft.encode("utf-8"))
            else:  # macOS/Linux
                process = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                process.communicate(email_draft.encode("utf-8"))

            return (
                True,
                f"Email draft created and copied to clipboard:\n\nTo: {recipient}\nSubject: {subject}",  # noqa: E501
            )
        except Exception as e:
            return False, f"Email error: {str(e)}"

    def _extract_email_info(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract recipient and subject from email command"""
        # Pattern: "draft email to [recipient] about [subject]"
        match = re.search(
            r"to\s+(\w+)\s+(?:about|regarding|with subject)\s+(.+?)(?:\.|$)",
            text,
            re.IGNORECASE,
        )
        if match:
            recipient = match.group(1)
            subject = match.group(2).strip()
            return recipient, subject
        return None, None

    def _create_email_draft(self, recipient: str, subject: str) -> str:
        """Create email draft"""
        return f"""To: {recipient}
Subject: {subject}

Dear {recipient.capitalize()},

[Your message here]

Best regards,
[Your Name]
"""

    # ── Text Processing ─────────────────────────────────────────────────────

    def _is_text_processing(self, text: str) -> bool:
        """Check if command is text processing"""
        patterns = [
            r"clean.*sentence",
            r"make.*professional",
            r"polish.*text",
            r"improve.*writing",
            r"fix.*grammar",
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _handle_text_processing(self, text: str) -> Tuple[bool, str]:
        """Handle text processing/cleaning"""
        try:
            # Extract text to clean
            text_to_clean = self._extract_text_to_clean(text)
            if not text_to_clean:
                return False, "Could not extract text to clean"

            # Clean and improve text
            cleaned = self._clean_text(text_to_clean)

            return True, f"Cleaned text:\n\n{cleaned}"
        except Exception as e:
            return False, f"Text processing error: {str(e)}"

    def _extract_text_to_clean(self, text: str) -> Optional[str]:
        """Extract text to be cleaned"""
        # Pattern: "clean [text]" or "make [text] professional"
        match = re.search(
            r"(?:clean|make|polish|improve|fix)\s+(?:this\s+)?(?:sentence|text|message)?\s*[:\"]?\s*(.+?)(?:\.|$)",  # noqa: E501
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        return None

    def _clean_text(self, text: str) -> str:
        """Clean and improve text"""
        # Basic text cleaning
        cleaned = text.strip()

        # Capitalize first letter
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]

        # Add period if missing
        if cleaned and not cleaned.endswith((".", "!", "?")):
            cleaned += "."

        # Fix common issues
        cleaned = re.sub(r"\s+", " ", cleaned)  # Multiple spaces
        cleaned = re.sub(r"\s([.,!?])", r"\1", cleaned)  # Space before punctuation

        return cleaned

    # ── Snippets ────────────────────────────────────────────────────────────

    def _is_snippet_command(self, text: str) -> bool:
        """Check if command is snippet-related"""
        patterns = [
            r"save.*snippet",
            r"save.*as",
            r"store.*email",
            r"remember.*email",
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _handle_snippet(self, text: str) -> Tuple[bool, str]:
        """Handle snippet saving/retrieval"""
        try:
            if "save" in text.lower():
                return self._save_snippet(text)
            else:
                return self._retrieve_snippet(text)
        except Exception as e:
            return False, f"Snippet error: {str(e)}"

    def _save_snippet(self, text: str) -> Tuple[bool, str]:
        """Save a snippet"""
        # Pattern: "save [content] as [name]"
        match = re.search(r"save\s+(.+?)\s+as\s+(\w+)", text, re.IGNORECASE)
        if not match:
            return False, "Format: 'save [content] as [name]'"

        content = match.group(1).strip()
        name = match.group(2).strip().lower()

        self.snippets[name] = content
        self._save_snippets()

        return True, f"Snippet '{name}' saved: {content}"

    def _retrieve_snippet(self, text: str) -> Tuple[bool, str]:
        """Retrieve a snippet"""
        # Extract snippet name
        match = re.search(r"(?:get|retrieve|use)\s+(?:snippet\s+)?(\w+)", text, re.IGNORECASE)
        if not match:
            return False, "Snippet not found"

        name = match.group(1).strip().lower()

        if name in self.snippets:
            content = self.snippets[name]
            return True, f"Snippet '{name}': {content}"
        else:
            return False, f"Snippet '{name}' not found"

    # ── Slack ───────────────────────────────────────────────────────────────

    def _is_slack_command(self, text: str) -> bool:
        """Check if command is Slack-related"""
        patterns = [
            r"send.*slack",
            r"slack.*message",
            r"message.*slack",
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _handle_slack(self, text: str) -> Tuple[bool, str]:
        """Handle Slack message sending"""
        if not SLACK_AVAILABLE:
            return (
                False,
                "Slack integration not available. Install: pip install slack-sdk",
            )

        try:
            # Extract message
            message = self._extract_slack_message(text)
            if not message:
                return False, "Could not extract message"

            # Get Slack token
            token = os.getenv("SLACK_BOT_TOKEN")
            if not token:
                return False, "SLACK_BOT_TOKEN environment variable not set"

            # Get channel
            channel = os.getenv("SLACK_CHANNEL", "#general")

            # Send message
            client = WebClient(token=token)
            response = client.chat_postMessage(channel=channel, text=message)
            if not response.get("ok", True):
                return False, f"Slack API error: {response.get('error', 'unknown')}"

            return True, f"Slack message sent to {channel}"
        except Exception as e:
            return False, f"Slack error: {str(e)}"

    def _extract_slack_message(self, text: str) -> Optional[str]:
        """Extract Slack message"""
        # Pattern: "send slack message [message]" or "slack [message]"
        match = re.search(
            r"(?:send\s+)?slack\s+(?:message)?\s*[:\"]?\s*(.+?)(?:\.|$)",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        return None

    # ── Utility Methods ─────────────────────────────────────────────────────

    def get_command_history(self) -> list:
        """Get command history"""
        return self.command_history

    def clear_history(self):
        """Clear command history"""
        self.command_history = []

    def get_snippets(self) -> Dict[str, str]:
        """Get all snippets"""
        return self.snippets.copy()


# Global instance
command_processor = CommandProcessor()
