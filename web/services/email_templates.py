"""
Transactional email templates for Voxylis.

Every template is plain data: ``render(kind, context)`` returns
``(subject, text_body, html_body)``.  The service layer owns delivery, so a
template can be unit-tested and previewed without a network or a provider key.

Rules that apply to every template
----------------------------------
* **No secrets in the body.** Links carry one-time tokens, and the token is the
  only sensitive value present; it is never repeated in the subject line, never
  echoed into the plain-text ``Reason`` lines, and never logged.
* **Branding is inline in HTML.** No external images, no external CSS, no
  tracking pixels: they break in most clients and would leak that a user opened
  an email.  Text and HTML carry the same information.
* **Every message is actionable.** Each one states what happened, what to do,
  and where to get help — the same three-part rule the desktop error dialogs
  follow.
* **Marketing is separated.** Only :data:`MARKETING_KINDS` may carry product
  news, and those require an explicit opt-in plus an unsubscribe link.
"""

from __future__ import annotations

from html import escape
from typing import Dict, Tuple

BRAND = "Voxylis"
SUPPORT_EMAIL = "support@voxylis.com"
WEBSITE = "https://voxylis.com"

#: Transactional messages: delivered regardless of marketing preferences.
TRANSACTIONAL_KINDS = (
    "welcome",
    "verify_email",
    "password_reset",
    "password_changed",
    "security_alert",
    "subscription_changed",
    "usage_warning",
    "usage_limit_reached",
    "account_deleted",
    "contact_notification",
)

#: Product news. Requires marketing consent and always links to unsubscribe.
MARKETING_KINDS = ("product_update",)

ALL_KINDS = TRANSACTIONAL_KINDS + MARKETING_KINDS


def _greeting(context: Dict) -> str:
    name = (context.get("name") or "").strip()
    return f"Hi {name}," if name else "Hi,"


def _layout(heading: str, paragraphs, button: Tuple[str, str] = None, footer_note: str = "") -> str:
    """Wrap body copy in the shared Voxylis HTML frame."""
    parts = [
        '<div style="background:#f5f5f7;padding:24px 12px;'
        'font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1c1c1e">',
        '<div style="max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #e3e3e8;'
        'border-radius:12px;padding:28px">',
        f'<div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#6b6b70;'
        f'font-weight:600;margin-bottom:18px">{escape(BRAND)}</div>',
        f'<h1 style="font-size:19px;line-height:1.35;margin:0 0 16px 0;font-weight:600">{escape(heading)}</h1>',
    ]
    for paragraph in paragraphs:
        parts.append(
            '<p style="font-size:14px;line-height:1.6;margin:0 0 14px 0;color:#3a3a3c">' f"{escape(paragraph)}</p>"
        )
    if button:
        label, url = button
        parts.append(
            f'<p style="margin:22px 0"><a href="{escape(url, quote=True)}" '
            'style="display:inline-block;background:#1c1c1e;color:#ffffff;text-decoration:none;'
            'font-size:14px;font-weight:600;padding:12px 18px;border-radius:8px">'
            f"{escape(label)}</a></p>"
        )
        parts.append(
            '<p style="font-size:12px;line-height:1.6;color:#6b6b70;margin:0 0 14px 0">'
            "If the button does not work, copy this address into your browser:<br>"
            f'<span style="word-break:break-all">{escape(url)}</span></p>'
        )
    if footer_note:
        parts.append(
            '<p style="font-size:12px;line-height:1.6;color:#6b6b70;margin:0 0 14px 0">' f"{escape(footer_note)}</p>"
        )
    parts.append(
        '<hr style="border:none;border-top:1px solid #e3e3e8;margin:22px 0">'
        '<p style="font-size:12px;line-height:1.6;color:#6b6b70;margin:0">'
        f"{escape(BRAND)} &middot; Voice input for your desktop<br>"
        f"Questions? Reply to this email or write to {escape(SUPPORT_EMAIL)}.<br>"
        f'<a href="{WEBSITE}" style="color:#6b6b70">{WEBSITE}</a></p>',
    )
    parts.append("</div></div>")
    return "".join(parts)


def _button_from(context: Dict, key: str, default_label: str) -> Tuple[str, str]:
    url = (context.get(key) or "").strip()
    if not url:
        return None
    return (context.get(f"{key}_label") or default_label, url)


def render(kind: str, context: Dict) -> Tuple[str, str, str]:
    """Render ``kind`` into ``(subject, text, html)``.

    Unknown kinds raise ``KeyError`` rather than silently sending something
    unexpected — a typo in a caller should fail loudly in tests.
    """
    context = dict(context or {})
    builder = _BUILDERS[kind]
    return builder(context)


def _welcome(c: Dict) -> Tuple[str, str, str]:
    greeting = _greeting(c)
    verify = _button_from(c, "verify_url", "Verify email address")
    subject = f"Welcome to {BRAND}"
    lines = [
        greeting,
        "",
        f"Your {BRAND} account is ready.",
    ]
    if verify:
        lines += [
            "",
            "One step left — confirm your email address so we can send you " "password resets and security alerts:",
            verify[1],
            "",
            "The link expires in 24 hours.",
        ]
    lines += [
        "",
        "Voxylis runs on your own keys: download the desktop app and add a Groq "
        "or OpenAI key in Settings. Until you do, there is nothing to configure "
        "on our side.",
        "",
        f"Need help? {SUPPORT_EMAIL}",
        "",
        BRAND,
    ]
    paragraphs = [greeting, f"Your {BRAND} account is ready."]
    if verify:
        paragraphs += [
            "One step left — confirm your email address so we can send you password "
            "resets and security alerts. The link expires in 24 hours.",
            "Voxylis runs on your own keys: download the desktop app and add a Groq or "
            "OpenAI key in Settings. Until you do, there is nothing to configure on our side.",
        ]
    else:
        paragraphs += [
            "Voxylis runs on your own keys: download the desktop app and add a Groq or " "OpenAI key in Settings.",
        ]
    return subject, "\n".join(lines), _layout(f"Welcome to {BRAND}", paragraphs, verify)


def _verify_email(c: Dict) -> Tuple[str, str, str]:
    greeting = _greeting(c)
    button = _button_from(c, "verify_url", "Verify email address")
    expiry = c.get("expires_in") or "24 hours"
    subject = f"Confirm your {BRAND} email address"
    text = "\n".join(
        [
            greeting,
            "",
            f"Confirm this address to finish setting up your {BRAND} account:",
            (button or ("", ""))[1],
            "",
            f"The link expires in {expiry} and can only be used once.",
            "If you did not create a Voxylis account, ignore this email — nothing happens.",
            "",
            BRAND,
        ]
    )
    html = _layout(
        "Confirm your email address",
        [
            greeting,
            f"Confirm this address to finish setting up your {BRAND} account. "
            f"The link expires in {expiry} and can only be used once.",
            "If you did not create a Voxylis account, you can ignore this email — " "no account will be activated.",
        ],
        button,
        "For your security we never ask for your password by email.",
    )
    return subject, text, html


def _password_reset(c: Dict) -> Tuple[str, str, str]:
    greeting = _greeting(c)
    button = _button_from(c, "reset_url", "Choose a new password")
    expiry = c.get("expires_in") or "1 hour"
    subject = f"Reset your {BRAND} password"
    text = "\n".join(
        [
            greeting,
            "",
            f"Someone asked to reset the password for your {BRAND} account.",
            (button or ("", ""))[1],
            "",
            f"The link expires in {expiry} and works only once.",
            "If this was not you, no action is needed: your password has not changed.",
            "",
            f"Still worried? Write to {SUPPORT_EMAIL}.",
            "",
            BRAND,
        ]
    )
    html = _layout(
        "Reset your password",
        [
            greeting,
            f"Someone asked to reset the password for your {BRAND} account. "
            f"The link expires in {expiry} and works only once.",
            "If this was not you, no action is needed — your password has not changed "
            "and no one can use this link without it.",
            "Signing in elsewhere stays active until you use the link above; using it " "signs out other devices.",
        ],
        button,
        "We never include your current password, and we never ask you to send one.",
    )
    return subject, text, html


def _password_changed(c: Dict) -> Tuple[str, str, str]:
    greeting = _greeting(c)
    when = c.get("changed_at") or "just now"
    subject = f"Your {BRAND} password was changed"
    text = "\n".join(
        [
            greeting,
            "",
            f"The password for your {BRAND} account was changed ({when}).",
            "All other devices have been signed out.",
            "",
            f"If this was not you, reset your password immediately at {WEBSITE}/auth " f"and contact {SUPPORT_EMAIL}.",
            "",
            BRAND,
        ]
    )
    html = _layout(
        "Your password was changed",
        [
            greeting,
            f"The password for your {BRAND} account was changed ({when}). " "All other devices have been signed out.",
            "If this was not you, reset your password immediately and contact support.",
            "We will never ask you to confirm a password by email.",
        ],
        _button_from(c, "reset_url", "Reset it now"),
        "Security notices are always sent, even if you opted out of product news.",
    )
    return subject, text, html


def _security_alert(c: Dict) -> Tuple[str, str, str]:
    greeting = _greeting(c)
    what = c.get("event") or "A security-relevant change was made to your account."
    when = c.get("changed_at") or "just now"
    subject = f"{BRAND} security notice"
    text = "\n".join(
        [
            greeting,
            "",
            f"{what} ({when}).",
            "",
            "If you did not do this, reset your password and contact " f"{SUPPORT_EMAIL} immediately.",
            "",
            BRAND,
        ]
    )
    html = _layout(
        "Security notice",
        [
            greeting,
            f"{what} ({when}).",
            "If you did not do this, reset your password and tell us straight away. "
            "We can lock the account while we look.",
        ],
        _button_from(c, "activity_url", "Review account activity"),
        "Security notices are always sent, even if you opted out of product news.",
    )
    return subject, text, html


def _subscription_changed(c: Dict) -> Tuple[str, str, str]:
    greeting = _greeting(c)
    plan = c.get("plan") or "Free"
    previous = c.get("previous_plan")
    limit = c.get("limit") or "unchanged"
    subject = f"Your {BRAND} plan is now {plan}"
    detail = f"Previous plan: {previous}. " if previous else ""
    text = "\n".join(
        [
            greeting,
            "",
            f"Your plan is now {plan}. {detail}Monthly transcription allowance: {limit}.",
            "",
            f"See the current state of your plan at {WEBSITE}/dashboard.",
            "",
            BRAND,
        ]
    )
    html = _layout(
        f"Your plan is now {plan}",
        [
            greeting,
            f"Your plan is now {plan}. {detail}Monthly transcription allowance: {limit}.",
            "You can review usage and plan state on your dashboard at any time.",
        ],
        _button_from(c, "dashboard_url", "Open dashboard"),
        c.get("note") or "",
    )
    return subject, text, html


def _usage_warning(c: Dict) -> Tuple[str, str, str]:
    greeting = _greeting(c)
    used = c.get("used", 0)
    limit = c.get("limit", 0)
    percent = c.get("percent", 0)
    subject = f"You have used {percent}% of your {BRAND} monthly allowance"
    text = "\n".join(
        [
            greeting,
            "",
            f"You have used {used} of {limit} transcriptions this month ({percent}%).",
            "When the allowance runs out, transcription stops until the next month "
            "starts. Nothing is charged automatically.",
            "",
            f"Details: {WEBSITE}/dashboard",
            "",
            BRAND,
        ]
    )
    html = _layout(
        f"{percent}% of your monthly allowance is used",
        [
            greeting,
            f"You have used {used} of {limit} transcriptions this month ({percent}%).",
            "When the allowance runs out, transcription stops until the next month "
            "starts. Nothing is charged automatically.",
        ],
        _button_from(c, "dashboard_url", "View usage"),
        "You received this because it affects your account, not because you subscribed to news.",
    )
    return subject, text, html


def _usage_limit_reached(c: Dict) -> Tuple[str, str, str]:
    greeting = _greeting(c)
    limit = c.get("limit", 0)
    subject = f"Your {BRAND} monthly allowance is used up"
    text = "\n".join(
        [
            greeting,
            "",
            f"You have used all {limit} transcriptions included this month.",
            "Transcription is paused until the allowance resets at the start of next "
            "month. Existing history stays available in the desktop app.",
            "",
            f"Your usage: {WEBSITE}/dashboard",
            "",
            BRAND,
        ]
    )
    html = _layout(
        "Monthly allowance reached",
        [
            greeting,
            f"You have used all {limit} transcriptions included this month. "
            "Transcription is paused until the allowance resets at the start of "
            "next month.",
            "Existing history stays available in the desktop app, and nothing has " "been charged.",
        ],
        _button_from(c, "dashboard_url", "View usage"),
        "Paid plans are not purchasable yet, so there is nothing to buy right now.",
    )
    return subject, text, html


def _account_deleted(c: Dict) -> Tuple[str, str, str]:
    greeting = _greeting(c)
    subject = f"Your {BRAND} account was deleted"
    text = "\n".join(
        [
            greeting,
            "",
            f"Your {BRAND} account and the data attached to it have been deleted.",
            "Server-side transcriptions, sessions, sign-in tokens and usage records "
            "were removed. Audio and API keys never left your own machine.",
            "",
            f"If you did not request this, contact {SUPPORT_EMAIL} straight away.",
            "",
            BRAND,
        ]
    )
    html = _layout(
        "Your account was deleted",
        [
            greeting,
            f"Your {BRAND} account and the data attached to it have been deleted. "
            "Server-side transcriptions, sessions, sign-in tokens and usage records "
            "were removed.",
            "Audio files and API keys never lived on our servers, so there is nothing "
            "of yours left to clean up on your machine beyond the local app data "
            "folder.",
            "If you did not request this, contact support immediately.",
        ],
        None,
        "This is the last message we will send to this address.",
    )
    return subject, text, html


def _contact_notification(c: Dict) -> Tuple[str, str, str]:
    sender = (c.get("from_email") or "unknown").strip()
    name = (c.get("name") or "Unknown").strip()
    topic = (c.get("subject") or "(no subject)").strip()
    body = c.get("message") or ""
    subject = f"[contact] {topic}"
    text = "\n".join(
        [
            f"New contact-form message from {name} <{sender}>",
            f"Topic: {topic}",
            "",
            body,
            "",
            "Reply directly to this message to answer the sender.",
        ]
    )
    html = _layout(
        "New contact-form message",
        [f"From: {name} <{sender}>", f"Topic: {topic}", body],
        None,
        "Contact-form submissions are stored in the database as well as emailed.",
    )
    return subject, text, html


def _product_update(c: Dict) -> Tuple[str, str, str]:
    greeting = _greeting(c)
    version = c.get("version") or ""
    headline = c.get("headline") or "What's new in Voxylis"
    summary = c.get("summary") or "A new version of the desktop app is available."
    unsubscribe = _button_from(c, "unsubscribe_url", "Unsubscribe from product news")
    subject = f"{headline}{f' ({version})' if version else ''}"
    text = "\n".join(
        [
            greeting,
            "",
            summary,
            "",
            f"Download: {c.get('download_url') or WEBSITE + '/download'}",
            "",
            f"Unsubscribe from product news: {(unsubscribe or ('', ''))[1]}",
            "Account and security messages are unaffected by this preference.",
            "",
            BRAND,
        ]
    )
    html = _layout(
        headline,
        [
            greeting,
            summary,
            "This is product news. Account and security messages are sent regardless " "of this preference.",
        ],
        _button_from(c, "download_url", "Download the update"),
        f"Unsubscribe any time: {(unsubscribe or ('', ''))[1]}",
    )
    return subject, text, html


_BUILDERS = {
    "welcome": _welcome,
    "verify_email": _verify_email,
    "password_reset": _password_reset,
    "password_changed": _password_changed,
    "security_alert": _security_alert,
    "subscription_changed": _subscription_changed,
    "usage_warning": _usage_warning,
    "usage_limit_reached": _usage_limit_reached,
    "account_deleted": _account_deleted,
    "contact_notification": _contact_notification,
    "product_update": _product_update,
}


def is_marketing(kind: str) -> bool:
    return kind in MARKETING_KINDS


def is_known(kind: str) -> bool:
    return kind in _BUILDERS
