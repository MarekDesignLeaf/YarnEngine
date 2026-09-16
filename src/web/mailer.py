"""Minimal transactional email client for Resend (https://resend.com), using
only the standard library -- no new pip dependency.

Configured via two environment variables:

  RESEND_API_KEY     Resend API key. If unset, send_email() is a no-op that
                      returns False, so features that send email (password
                      reset) degrade gracefully -- they still respond
                      normally -- instead of crashing when email hasn't been
                      configured yet.
  RESEND_FROM_EMAIL   Sender address, e.g. "YarnEngine <noreply@designleaf.co.uk>".
                      Requires that sending domain to be verified in Resend.
                      Defaults to Resend's shared onboarding sender, which
                      only delivers to the Resend account's own verified
                      address -- fine to smoke-test with, not for real users.
"""
import json
import os
import urllib.error
import urllib.request

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_FROM = "YarnEngine <onboarding@resend.dev>"


def send_email(to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Best-effort send. Returns True only on a confirmed 2xx from Resend;
    returns False (never raises) if email isn't configured or the send
    fails, so callers can treat it as "may not have been delivered" rather
    than needing to handle exceptions."""
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if not api_key or not to:
        return False
    from_addr = os.environ.get("RESEND_FROM_EMAIL", "").strip() or DEFAULT_FROM
    body = {"from": from_addr, "to": [to], "subject": subject, "html": html}
    if text:
        body["text"] = text
    req = urllib.request.Request(
        RESEND_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, ValueError, OSError):
        return False
