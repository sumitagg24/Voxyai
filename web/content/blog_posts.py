"""Blog seed data (moved from web/app.py without changes)."""

LEGACY_BLOG_SLUGS = {
    "introducing-voxy-2-0": "introducing-voxylis-3-0",
    "voice-input-vs-typing-numbers": "where-your-data-goes",
}


BLOG_POSTS = [
    {
        "slug": "introducing-voxylis-3-0",
        "title": "Introducing Voxylis 3.0",
        "date": "2026-09-23",
        "category": "Product Update",
        "excerpt": "Voxylis 3.0 is the release that turns a tray utility into a real desktop application: a main window, encrypted API keys and a local SQLite history.",
        "content": (
            "Voxylis 3.0 is the first release we are comfortable calling a desktop product rather than a tray utility.\n\n"
            "## What changed\n\n"
            "### A real application window\n"
            "The recording overlay is no longer the whole interface. Voxylis now has a persistent window with "
            "Home, History, Microphone, AI Providers, Shortcuts, Privacy, Account, Diagnostics and About. "
            "The overlay is what it should be: a small transient pill that appears while you hold your shortcut.\n\n"
            "### API keys left the settings file\n"
            "Keys were previously stored as plaintext JSON. They now live in the operating system credential "
            "store (Windows DPAPI, or your keyring). Existing plaintext keys are migrated automatically and "
            "removed from `settings.json`, which now only records whether a provider is configured.\n\n"
            "### User data moved out of the install directory\n"
            "Settings, history, logs and temporary audio now live under `%LOCALAPPDATA%`\\Voxylis. The install "
            "directory is treated as read-only, so an upgrade can never destroy your configuration.\n\n"
            "### History is a database, not a text file\n"
            "Transcripts are stored in SQLite with per-entry delete, retention, export, and an off switch that "
            "stops recordings being written at all.\n\n"
            "### Shortcuts are recorded, not typed\n"
            "Every shortcut field is a press-to-capture control that rejects reserved Windows combinations and "
            "duplicate assignments.\n\n"
            "## Honest limits\n\n"
            "Voxylis does not train or host a speech model. Transcription is performed by the Groq or OpenAI "
            "key you connect, which is what sets your language coverage and latency. Paid plans are described "
            "on the pricing page but cannot be purchased yet, because no payment provider is connected."
        ),
        "read_time": "4 min read",
    },
    {
        "slug": "bitterest-lesson-voice-ai",
        "title": "The Bitterest Lesson in Voice AI",
        "date": "2026-08-28",
        "category": "Engineering",
        "excerpt": "We deliberately do not train a speech model. Here is why the product is better for it, and where the clever work actually goes.",
        "content": (
            "Rich Sutton's essay *The Bitter Lesson* argues that general methods which leverage computation "
            "beat hand-crafted tricks. For a small team the lesson is blunter: **do not compete with the "
            "foundation models. Build the layer around them.**\n\n"
            "## What we do not do\n\n"
            "Voxylis trains nothing. Speech recognition comes from Whisper through Groq or OpenAI, and text "
            "enhancement comes from the language models those providers expose. Choosing to own a model would "
            "have cost us the time we spent on the parts our users actually touch.\n\n"
            "## Where the work goes instead\n\n"
            "1. **Provider abstraction.** One interface for transcription and one for enhancement, with model "
            "fallback, timeouts and retries in a single place rather than scattered across call sites.\n"
            '2. **Error mapping with a name.** An HTTP 401 becomes *"Groq rejected the API key"* plus an action, '
            "not a stack trace in a dialog.\n"
            "3. **Insertion that admits failure.** Pasting into a window that lost focus used to report success. "
            "It now returns a structured result and tries the next strategy.\n"
            "4. **Readable state.** Silence, network failure, quota exhaustion and a bad key are four different "
            "messages, because they need four different fixes.\n\n"
            "## The takeaway\n\n"
            "The model is not the product. Deterministic plumbing, honest errors and a UI that behaves "
            "predictably are, and that is where a small team can still win."
        ),
        "read_time": "6 min read",
    },
    {
        "slug": "ai-too-good-to-be-true",
        "title": "AI: Too Good to Be True, Too Bad to Type",
        "date": "2026-08-10",
        "category": "Product",
        "excerpt": "AI can draft an email in seconds — but you still have to type the prompt. That gap is the whole reason this app exists.",
        "content": (
            "AI can draft an email in seconds. You still have to *type* the prompt.\n\n"
            "That gap is the reason Voxylis exists. We are not going to invent a multiplier for it: how much "
            "faster speech is than typing depends on how you type, what you are writing and how well your "
            "microphone and provider behave. Anyone quoting a single fixed number for it is guessing.\n\n"
            "## What the app actually does\n\n"
            "1. **Capture.** Hold your shortcut, speak, release. The microphone is opened for exactly that window.\n"
            "2. **Transcribe.** The audio goes to the speech provider whose key you supplied.\n"
            "3. **Optionally rewrite.** Enhancement modes (Formal, Casual, Technical, Concise, Creative, or your "
            "own prompt) ask an LLM to restructure the transcript. This is off by default.\n"
            "4. **Insert.** The text is typed into the window that had focus when you started, preferring the "
            "clipboard, then SendInput, then character-by-character typing.\n\n"
            "## What we measure instead of marketing numbers\n\n"
            "Latency and word counts are shown per session in your own dashboard and history, from your own "
            "machine. We would rather you read your numbers than ours.\n\n"
            "## Try it honestly\n\n"
            "Dictate one real message you would otherwise have typed. If it is not faster or more comfortable, "
            "the app has not earned a place in your workflow — and you will know within a minute."
        ),
        "read_time": "5 min read",
    },
    {
        "slug": "where-your-data-goes",
        "title": "Where your audio and transcripts actually go",
        "date": "2026-07-22",
        "category": "Engineering",
        "excerpt": "A precise walkthrough of every place a recording touches disk or the network, and how to remove all of it.",
        "content": (
            "Privacy statements are usually vague. Here is the exact path a recording takes through Voxylis.\n\n"
            "## On the network\n\n"
            "One HTTP request per utterance, to the provider whose key you configured:\n\n"
            "- **Groq** or **OpenAI** for speech-to-text;\n"
            "- the same provider's LLM, and only if you enabled AI enhancement;\n"
            "- nothing at all if you only use voice commands like *new line* or *clear that*.\n\n"
            "Voxylis itself has no analytics endpoint, no telemetry and no crash-reporting service. There is no "
            "server-side component running on your machine.\n\n"
            "## On disk\n\n"
            "- **Audio** is written to a temporary WAV inside your user-data folder for the duration of the "
            "upload, then deleted. It is never appended to a recording log.\n"
            "- **Transcripts** go into a SQLite database under `%LOCALAPPDATA%`\\Voxylis\\data, capped by a "
            "retention setting and removable per entry.\n"
            "- **API keys** go into the operating system credential store. They are never written to a settings "
            "file, never included in diagnostics, and never logged.\n"
            "- **Logs** record sizes, languages, model names and error codes. Transcript text is not logged; "
            "that is a property of the code, not a promise.\n\n"
            "## How to delete everything\n\n"
            "Settings → Privacy has a single button that wipes the history database, and the data folder is one "
            "click away so you can remove the rest yourself. Uninstalling does not need to leave anything "
            "behind.\n\n"
            "## What we do not claim\n\n"
            "We do not claim the audio never leaves your machine, and we do not claim on-device transcription: "
            "your speech provider receives it, under their retention policy, because that is how the feature works."
        ),
        "read_time": "5 min read",
    },
]
