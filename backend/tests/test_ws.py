import pytest


def test_ws_snapshot_and_broadcast(client, session):
    sid = session["id"]
    with client.websocket_connect(f"/api/sessions/{sid}/ws") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "snapshot"
        assert snap["session"]["id"] == sid
        # second client joins; both receive a dice event
        with client.websocket_connect(f"/api/sessions/{sid}/ws") as ws2:
            snap2 = ws2.receive_json()
            assert snap2["type"] == "snapshot"
            ws2.send_json({"type": "roll", "count": 1, "faces": 20, "roller": "Aria"})
            ev = ws.receive_json()
            assert ev["type"] == "dice"
            assert ev["payload"]["roller"] == "Aria"
            ev2 = ws2.receive_json()
            assert ev2["type"] == "dice"
            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong" and pong["clients"] == 2


def test_ws_roll_validation(client, session):
    with client.websocket_connect(f"/api/sessions/{session['id']}/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "roll", "faces": 7})
        msg = ws.receive_json()
        assert msg["type"] == "error"


def test_ws_unknown_session(client):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/sessions/9999/ws") as ws:
            ws.receive_json()
