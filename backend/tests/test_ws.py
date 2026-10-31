import pytest


def _token(client, session, player_id=None):
    payload = {"code": session["code"]}
    if player_id is not None:
        payload["player_id"] = player_id
    return client.post("/api/sessions/join", json=payload).json()["player_token"]


def test_ws_snapshot_and_broadcast(client, session):
    sid = session["id"]
    token = _token(client, session)
    with client.websocket_connect(f"/api/sessions/{sid}/ws?token={token}") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "snapshot"
        assert snap["session"]["id"] == sid
        # second client joins; both receive a dice event
        with client.websocket_connect(f"/api/sessions/{sid}/ws?token={_token(client, session)}") as ws2:
            snap2 = ws2.receive_json()
            assert snap2["type"] == "snapshot"
            ws2.send_json({"type": "roll", "count": 1, "faces": 20, "roller": "IGNORED-CLIENT-NAME"})
            ev = ws.receive_json()
            assert ev["type"] == "dice"
            assert ev["payload"]["roller"] == "guest"  # attributed from the token, not the payload
            ev2 = ws2.receive_json()
            assert ev2["type"] == "dice"
            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong" and pong["clients"] == 2


def test_ws_chat_attributed_to_token_player(client, session):
    p = client.post("/api/players", json={"name": "Aria"}).json()
    token = _token(client, session, player_id=p["id"])
    with client.websocket_connect(f"/api/sessions/{session['id']}/ws?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"type": "chat", "from": "SPOOF", "text": "hello"})
        ev = ws.receive_json()
        assert ev["type"] == "chat" and ev["payload"]["from"] == "Aria" and ev["payload"]["text"] == "hello"


def test_ws_roll_validation(client, session):
    token = _token(client, session)
    with client.websocket_connect(f"/api/sessions/{session['id']}/ws?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"type": "roll", "faces": 7})
        msg = ws.receive_json()
        assert msg["type"] == "error"


def test_ws_unknown_session(client):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/sessions/9999/ws") as ws:
            ws.receive_json()


def test_ws_rejects_missing_or_bad_token(client, session):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/sessions/{session['id']}/ws"):
            pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/sessions/{session['id']}/ws?token=bogus"):
            pass
