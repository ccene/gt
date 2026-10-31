import base64
import json

import db
import passkeys

ORIGIN = "http://localhost:8000"


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _make_client_data(challenge_b64: str) -> str:
    return _b64u(json.dumps({"type": "webauthn.create", "challenge": challenge_b64, "origin": ORIGIN}).encode())


def _fake_credential(challenge_b64: str) -> dict:
    return {
        "id": _b64u(b"cred-id-1"),
        "rawId": _b64u(b"cred-id-1"),
        "type": "public-key",
        "response": {
            "clientDataJSON": _make_client_data(challenge_b64),
            "attestationObject": _b64u(b"fake-attestation"),
        },
    }


def _extract_challenge(options: dict) -> str:
    return options["challenge"]


def test_registration_options_shape(client):
    resp = client.post("/api/auth/passkey/register/options", headers={"origin": ORIGIN})
    assert resp.status_code == 200
    body = resp.json()
    assert body["rp"]["id"] == "localhost"
    assert body["challenge"]
    assert body["user"]["name"] == "host"


def test_verify_registration_rejects_bad_challenge(client):
    cred = _fake_credential(_b64u(b"unknown-challenge"))
    resp = client.post(
        "/api/auth/passkey/register/verify",
        json={"credential": cred},
        headers={"origin": ORIGIN},
    )
    assert resp.status_code == 400


def test_verify_registration_mocked_success(client, monkeypatch):
    # generate real options so a challenge exists
    opts = passkeys.registration_options(ORIGIN)
    challenge = _extract_challenge(opts)

    class FakeVerified:
        credential_id = b"cred-id-1"
        credential_public_key = b"pubkey-bytes"
        sign_count = 0

    monkeypatch.setattr(
        passkeys, "verify_registration_response", lambda **kw: FakeVerified()
    )
    resp = client.post(
        "/api/auth/passkey/register/verify",
        json={"credential": _fake_credential(challenge)},
        headers={"origin": ORIGIN},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    rows = db.query("SELECT credential_id FROM webauthn_credentials")
    assert len(rows) == 1
    # challenge is single-use
    resp2 = client.post(
        "/api/auth/passkey/register/verify",
        json={"credential": _fake_credential(challenge)},
        headers={"origin": ORIGIN},
    )
    assert resp2.status_code == 400


def test_authentication_flow_mocked(client, monkeypatch):
    # seed a credential directly
    db.execute(
        "INSERT INTO webauthn_credentials (credential_id, public_key, sign_count) VALUES (?, ?, 0)",
        (_b64u(b"cred-id-1"), _b64u(b"pubkey-bytes")),
    )
    opts = passkeys.authentication_options(ORIGIN)
    challenge = opts["challenge"]

    class FakeVerified:
        new_sign_count = 1

    monkeypatch.setattr(passkeys, "verify_authentication_response", lambda **kw: FakeVerified())
    auth_cred = {
        "id": _b64u(b"cred-id-1"),
        "rawId": _b64u(b"cred-id-1"),
        "type": "public-key",
        "response": {
            "clientDataJSON": _b64u(
                json.dumps({"type": "webauthn.get", "challenge": challenge, "origin": ORIGIN}).encode()
            ),
            "authenticatorData": _b64u(b"auth-data"),
            "signature": _b64u(b"sig"),
            "userHandle": _b64u(b"user"),
        },
    }
    resp = client.post(
        "/api/auth/passkey/login/verify",
        json={"credential": auth_cred},
        headers={"origin": ORIGIN},
    )
    assert resp.status_code == 200
    token = resp.json()["admin_session_token"]
    assert passkeys.is_valid_admin_session(token)
    assert not passkeys.is_valid_admin_session("bogus")


def test_admin_action_with_passkey_session(client, session):
    """A passkey admin session token authorizes host actions."""
    import passkeys as pk

    db.execute(
        "INSERT INTO admin_sessions (token, credential_id, expires_at)"
        " VALUES ('pk-token', 'c', datetime('now', '+12 hours'))"
    )
    assert pk.is_valid_admin_session("pk-token")
    resp = client.post(
        f"/api/sessions/{session['id']}/state",
        json={"state": "playing"},
        headers={"X-Admin-Token": "pk-token"},
    )
    assert resp.status_code == 200
    # wrong token still rejected
    assert (
        client.post(
            f"/api/sessions/{session['id']}/state",
            json={"state": "playing"},
            headers={"X-Admin-Token": "nope"},
        ).status_code
        == 403
    )


def test_challenge_expiry(monkeypatch):
    db.execute(
        "INSERT INTO webauthn_challenges (kind, challenge, expires_at) VALUES ('auth', 'expired', 1)"
    )
    assert passkeys._pop_challenge("auth", "expired") is False
