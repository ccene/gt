"""WebAuthn passkey auth for the host/admin.

Flow: register options -> browser ceremony -> verify & store credential ->
authentication options -> browser ceremony -> verify -> issue admin session token.
Challenges are single-use and short-lived. Credentials stored in SQLite.
"""

import base64
import secrets
import time

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialType,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

import db

CHALLENGE_TTL_S = 300



def _to_jsonable(obj):
    """Recursively convert webauthn structs (dataclasses, enums, bytes) to JSON-safe dicts."""
    import dataclasses
    import enum

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, bytes):
        return _b64u(obj)
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj

def _b64u(b: bytes) -> str:
    return bytes_to_base64url(b)


def _unb64u(s: str) -> bytes:
    return base64url_to_bytes(s)


def _rp_id(origin: str) -> str:
    from urllib.parse import urlparse

    return urlparse(origin).hostname or "localhost"


def _store_challenge(kind: str, challenge: str, ttl: int = CHALLENGE_TTL_S) -> None:
    db.execute(
        "INSERT INTO webauthn_challenges (kind, challenge, expires_at) VALUES (?, ?, ?)",
        (kind, challenge, int(time.time()) + ttl),
    )


def _pop_challenge(kind: str, challenge: str) -> bool:
    row = db.query_one(
        "SELECT expires_at FROM webauthn_challenges WHERE kind = ? AND challenge = ?",
        (kind, challenge),
    )
    if row:
        db.execute("DELETE FROM webauthn_challenges WHERE challenge = ?", (challenge,))
    return row is not None and row["expires_at"] > time.time()


def registration_options(origin: str, user_name: str = "host") -> dict:
    rp_id = _rp_id(origin)
    existing = db.query("SELECT credential_id FROM webauthn_credentials")
    exclude = [
        PublicKeyCredentialDescriptor(type=PublicKeyCredentialType.PUBLIC_KEY, id=_unb64u(r["credential_id"]))
        for r in existing
    ]
    challenge = secrets.token_bytes(32)
    opts = generate_registration_options(
        rp_id=rp_id,
        rp_name="D&D Table Companion",
        user_name=user_name,
        user_id=secrets.token_bytes(16),
        user_display_name=user_name,
        challenge=challenge,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=exclude or None,
    )
    _store_challenge("register", _b64u(challenge))
    return _to_jsonable(opts)


def verify_registration(origin: str, credential: dict) -> dict:
    rp_id = _rp_id(origin)
    challenge_b64 = credential.get("response", {}).get("clientDataJSON", "")
    # extract challenge from clientDataJSON
    import json

    client_data = json.loads(_unb64u(challenge_b64))
    challenge = client_data.get("challenge", "")
    if not _pop_challenge("register", challenge):
        raise ValueError("challenge expired or unknown")
    verified = verify_registration_response(
        credential=credential,
        expected_challenge=_unb64u(challenge),
        expected_rp_id=rp_id,
        expected_origin=origin,
        require_user_verification=False,
    )
    cred_id = _b64u(verified.credential_id)
    db.execute(
        "INSERT OR REPLACE INTO webauthn_credentials (credential_id, public_key, sign_count, created_at)"
        " VALUES (?, ?, ?, datetime('now'))",
        (cred_id, _b64u(verified.credential_public_key), verified.sign_count),
    )
    return {"ok": True, "credential_id": cred_id}


def authentication_options(origin: str) -> dict:
    rp_id = _rp_id(origin)
    creds = db.query("SELECT credential_id FROM webauthn_credentials")
    allow = [
        PublicKeyCredentialDescriptor(type=PublicKeyCredentialType.PUBLIC_KEY, id=_unb64u(r["credential_id"]))
        for r in creds
    ]
    challenge = secrets.token_bytes(32)
    opts = generate_authentication_options(
        rp_id=rp_id,
        challenge=challenge,
        allow_credentials=allow or None,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    _store_challenge("auth", _b64u(challenge))
    return _to_jsonable(opts)


def verify_authentication(origin: str, credential: dict) -> str:
    """Verify ceremony; returns a new admin session token."""
    import json

    rp_id = _rp_id(origin)
    client_data = json.loads(_unb64u(credential.get("response", {}).get("clientDataJSON", "")))
    challenge = client_data.get("challenge", "")
    if not _pop_challenge("auth", challenge):
        raise ValueError("challenge expired or unknown")
    cred_id = credential.get("id", "")
    row = db.query_one("SELECT public_key, sign_count FROM webauthn_credentials WHERE credential_id = ?", (cred_id,))
    if not row:
        raise ValueError("unknown credential")
    verified = verify_authentication_response(
        credential=credential,
        expected_challenge=_unb64u(challenge),
        expected_rp_id=rp_id,
        expected_origin=origin,
        credential_public_key=_unb64u(row["public_key"]),
        credential_current_sign_count=row["sign_count"],
        require_user_verification=False,
    )
    db.execute(
        "UPDATE webauthn_credentials SET sign_count = ? WHERE credential_id = ?",
        (verified.new_sign_count, cred_id),
    )
    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO admin_sessions (token, credential_id, created_at, expires_at) VALUES (?, ?, datetime('now'), ?)",
        (token, cred_id, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 12 * 3600))),
    )
    return token


def is_valid_admin_session(token: str | None) -> bool:
    if not token:
        return False
    row = db.query_one(
        "SELECT expires_at FROM admin_sessions WHERE token = ? AND expires_at > datetime('now')",
        (token,),
    )
    return row is not None


def _b64unused() -> str:
    return base64.b64encode(b"").decode()
