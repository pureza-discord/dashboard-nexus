from __future__ import annotations

import logging

import resend

from server.core.settings import get_settings
from server.db.models import VerificationPurpose

logger = logging.getLogger("email_service")
settings = get_settings()

_last_dev_code: dict[str, str] = {}


def get_last_dev_code(email: str) -> str | None:
    """Return the last verification code sent in dev mode (for API exposure)."""
    return _last_dev_code.get(email.strip().lower())


def _subject_for(purpose: VerificationPurpose) -> str:
    if purpose == VerificationPurpose.password_reset:
        return "Nexus Leads - Redefinicao de senha"
    return "Nexus Leads - Codigo de verificacao"


def _log_dev_code(email: str, code: str, purpose: VerificationPurpose) -> None:
    """Always-visible dev console output + store for API retrieval."""
    _last_dev_code[email.strip().lower()] = code
    print(f"\n{'=' * 60}")
    print(f"  [DEV] VERIFICATION CODE")
    print(f"  Email:   {email}")
    print(f"  Code:    {code}")
    print(f"  Purpose: {purpose.value}")
    print(f"{'=' * 60}\n")


def send_verification_email(email: str, code: str, purpose: VerificationPurpose) -> None:
    api_key = settings.resend_api_key
    from_email = settings.resend_from_email or settings.smtp_from_email or "Nexus Leads <onboarding@resend.dev>"
    is_dev = settings.environment != "production"

    # Always log to console in dev
    if is_dev:
        _log_dev_code(email, code, purpose)

    # If no API key, only allow skipping in dev (local-only development)
    if not api_key:
        if is_dev:
            logger.info("No RESEND_API_KEY set — skipping email send (dev mode, code printed to console)")
            return
        raise RuntimeError("RESEND_API_KEY is required in production")

    # Always attempt to send via Resend when API key is present
    resend.api_key = api_key

    action = "confirmar sua conta" if purpose != VerificationPurpose.password_reset else "redefinir sua senha"
    html = (
        "<div style='font-family:Inter,Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;color:#fff;background:#0a0a0a;'>"
        "<h2 style='margin:0 0 8px;'>Nexus Leads Manager</h2>"
        f"<p style='margin:0 0 16px;color:#9ca3af;'>Codigo para {action}:</p>"
        "<div style='background:#111827;border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:18px;text-align:center;'>"
        f"<span style='font-size:30px;font-weight:700;letter-spacing:6px;color:#22c55e'>{code}</span>"
        "</div>"
        f"<p style='margin:16px 0 0;color:#6b7280;font-size:13px'>Expira em {settings.email_code_ttl_minutes} minutos.</p>"
        "</div>"
    )

    try:
        resend.Emails.send(
            {
                "from": from_email,
                "to": [email],
                "subject": _subject_for(purpose),
                "html": html,
            }
        )
        logger.info("Verification email sent to %s via Resend", email)
    except Exception as exc:  # pragma: no cover
        logger.error("Resend API failed for %s: %s", email, exc, exc_info=True)
        if not is_dev:
            raise RuntimeError("Falha ao enviar email via Resend") from exc
