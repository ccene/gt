import smtplib
import uuid
from email.message import EmailMessage

from config import settings


def send_save_point(to_email: str, player_name: str, character_name: str, sheet: dict, save_point: dict) -> dict:
    """Send the end-of-session character sheet. Falls back to a local outbox file."""
    subject = f"Your save point — {character_name}"
    lines = [
        f"Hi {player_name},",
        "",
        f"Here is your updated character sheet for {character_name} and where the story stands.",
        "",
        f"Save point: {save_point.get('label', 'session end')} (chapter {save_point.get('chapter_index', 0) + 1})",
        f"Notes: {save_point.get('notes', '')}",
        "",
        "Character sheet:",
    ]
    for key, value in sheet.items():
        lines.append(f"  {key}: {value}")
    body = "\n".join(lines)

    if not settings.smtp_host or not to_email:
        settings.ensure_dirs()
        path = settings.outbox_dir / f"{uuid.uuid4().hex}.eml"
        path.write_text(f"To: {to_email}\nSubject: {subject}\n\n{body}", encoding="utf-8")
        return {"sent": False, "via": "outbox", "path": str(path)}

    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)
    return {"sent": True, "via": "smtp", "to": to_email}


def send_all_save_points(session_id: int) -> list[dict]:
    import db

    session = db.query_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
    if not session:
        return []
    save_point = db.loads(session["save_point"])
    results = []
    rows = db.query(
        "SELECT p.name AS player, p.email, c.name AS character, c.sheet FROM characters c"
        " JOIN players p ON p.id = c.player_id ORDER BY p.id"
    )
    for row in rows:
        result = send_save_point(
            row["email"], row["player"], row["character"], db.loads(row["sheet"]), save_point
        )
        results.append({"player": row["player"], "character": row["character"], **result})
    return results
