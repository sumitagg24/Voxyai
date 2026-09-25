# Voxylis Privacy

This document describes what the **desktop application** actually does. It is
written against the code in this repository, and the in-app Privacy page and
website blog post say the same thing.

## What leaves your machine

One HTTPS request per utterance, to the provider whose key **you** configured:

| Action | Destination | When |
|---|---|---|
| Speech-to-text | Groq, or OpenAI as fallback | every recording you keep |
| Text enhancement | the same provider | only if AI enhancement is enabled |
| Translation / Q&A | the same provider | only when you use that feature |
| Voice commands (`new line`, `clear that`, …) | nothing – handled locally | – |
| Update check | GitHub Releases | on start, once, can be disabled |
| Crash report | Sentry (a third-party error service) | **only** if you enable *Settings → Privacy → Send a diagnostic report*, and only when something fails |

If you only dictate and disable enhancement, exactly one request per utterance
is made. There is no Voxylis server in this path.

**No analytics and no usage tracking.** The app never contacts a
Voxylis-operated endpoint, has no install ping and no session reporting. There
is no "phone home" on start.

The one optional exception is **crash reporting**, and it is off until you turn
it on in *Settings → Privacy*. When it is on and something fails, one report is
sent to Sentry containing:

* the exception type and stack trace;
* an error category (`pipeline`, `transcription`, `updater`, `hotkey`,
  `microphone`, `injection`, `startup`, `auth`) and the error code for
  recognised failures;
* the app version, your OS and Python version, and whether the build is frozen;
* the configured provider **name** (`groq` / `openai`) — never the key.

It never contains API keys, credential-vault contents, session ids or tokens,
transcripts, enhanced text, clipboard contents, audio, your account email, or
paths under your user profile (they are rewritten to placeholders before an
event is sent). Turning the switch off stops reporting immediately. A build with
no reporting endpoint compiled in sends nothing even when the box is ticked.

Local verification screenshots are development artefacts and are gitignored;
they are never uploaded anywhere.

## What is stored on disk

Everything mutable lives under one folder (see `docs/ARCHITECTURE.md`):

```
%LOCALAPPDATA%\Voxylis\        (Windows; ~/Library/Application Support/Voxylis on macOS)
├── config\settings.json       non-secret preferences only
├── data\history.sqlite3       transcripts (optional, see below)
├── data\stats.json            word/transcription counters, no text
├── secrets\credentials.vault  API keys, DPAPI-encrypted and user-scoped
├── logs\voxylis.log           sizes, languages, model names, error codes
├── crashes\crash-<pid>.log    local crash report, written whether or not reporting is on
├── temp\                      temporary audio, deleted after every run
└── updates\                   downloaded installers awaiting a verified apply
```

* **Audio** — recorded to a temporary WAV, uploaded, then deleted. Never
  appended to a log or archived.
* **Transcripts** — stored in SQLite only when history is enabled. Retention and
  a maximum entry count are enforced after every insert. You can delete a single
  entry, delete everything, export to JSON/CSV, or turn history off entirely —
  in which case new recordings are not stored at all.
* **API keys** — in the OS credential store (Windows DPAPI at user scope). They
  are never written to `settings.json`, never logged, and never included in a
  diagnostics bundle.
* **Logs** — no transcript text, no keys, no tokens. `docs/ARCHITECTURE.md`
  explains the same property.

Redaction is enforced at construction time in `ui/diagnostics.py`, so "Copy
diagnostics" cannot leak a key or a transcript even if a caller asks for
everything.

## Account and the web dashboard

An account is optional. Local dictation works without one. If you sign in:

* the session token is stored in the same OS credential store, not in a file;
* the dashboard can show history and usage that the desktop app uploaded on
  request from its Account page — nothing is uploaded automatically;
* deleting your account removes the server-side rows and any uploaded history.

### Social sign-in consent (Google / GitHub)

After the provider verifies you, the website shows a consent screen listing
exactly what Voxylis receives — your name, email address and profile photo —
before any Voxylis session exists. **Continue** creates the account/session;
**Cancel** (or closing the dialog) discards the provider token and stores
nothing. The photo is shown in the dialog only and never stored; the server
keeps your name, email and provider id, and refuses sign-in when the provider
email is unverified.

## Removing everything

1. **Settings → Privacy** — turn history off, delete all history, export first
   if you want a copy.
2. **Settings → Privacy → Open data folder** — delete the folder for settings,
   logs, stats and caches.
3. **Settings → AI Providers** — clear a stored key (each key can be deleted
   individually and is removed from the credential store).
4. **Uninstall** — the uninstaller asks separately whether to delete
   `%LOCALAPPDATA%\Voxylis`, and only when you confirm.

## What this project does not claim

Voxylis cannot promise what the upstream provider does with audio you send it.
Groq and OpenAI each have their own retention policies; read theirs if that
matters to you. The desktop app supports whichever of the two you have a key
for; there is no Voxylis-hosted transcription service.
