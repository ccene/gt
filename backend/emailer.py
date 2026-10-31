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
    msg["From"] = settings.smtp_from or settings.smtp_user or "dnd-table@localhost"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    else:
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
    # Only this session's members get save points — never other sessions'
    # characters that happen to live in the same database. Sessions with no
    # recorded members fall back to all characters (legacy/demo data).
    rows = db.query(
        "SELECT p.name AS player, p.email, c.name AS character, c.sheet FROM characters c"
        " JOIN players p ON p.id = c.player_id"
        " WHERE NOT EXISTS (SELECT 1 FROM session_players sp"
        "   WHERE sp.session_id = ? AND sp.player_id IS NOT NULL)"
        "    OR c.player_id IN (SELECT sp.player_id FROM session_players sp"
        "   WHERE sp.session_id = ? AND sp.player_id IS NOT NULL)"
        " ORDER BY p.id",
        (session_id, session_id),
    )
    for row in rows:
        result = send_save_point(
            row["email"], row["player"], row["character"], db.loads(row["sheet"]), save_point
        )
        results.append({"player": row["player"], "character": row["character"], **result})
    return results
