"""Headless self-test loop: boot the app locally and play a session end-to-end.

This is the "open the application and try out the game" loop that runs without
any human input. It starts the real Uvicorn server on a loopback port with a
throwaway database, then drives the full game flow through the same REST +
WebSocket API the PWA uses:

    health -> host new game -> player joins -> character sheet ->
    live dice over WS (seen by a second WS client) -> AI narration ->
    next chapter -> set map -> end session -> save-point email in outbox/

Usage:
    python3 scripts/smoke_loop.py            # one pass, exit 0/1
    python3 scripts/smoke_loop.py --watch 3  # run 3 passes back-to-back

Exit code is 0 only if every assertion passed. Prints PASS/FAIL per step so a
failing step names the broken flow. Safe to run repeatedly: uses its own
temp database (data/smoke-<pid>.db) and outbox, and kills the server on exit.
Never binds anything but 127.0.0.1.
"""

import argparse
import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT / ".venv" / "bin" / "python"
HOST = "127.0.0.1"
PORT = int(os.environ.get("SMOKE_PORT", "8123"))
BASE = f"http://{HOST}:{PORT}"
WS = f"ws://{HOST}:{PORT}"

STEPS: list[tuple[str, str]] = []


def step(name: str, ok: bool, detail: str = "") -> None:
    STEPS.append((name, "PASS" if ok else "FAIL"))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail and not ok else ""))
    if not ok:
        raise AssertionError(f"smoke step failed: {name} {detail}")


async def wait_healthy(proc: subprocess.Popen, httpx) -> None:
    deadline = time.time() + 30
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early with code {proc.returncode}")
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(f"{BASE}/health", timeout=2.0)
                if r.status_code == 200 and r.json().get("status") == "ok":
                    return
        except Exception:
            pass
        await asyncio.sleep(0.25)
    raise RuntimeError("server did not become healthy within 30s")


async def run_pass(httpx, websockets) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="smoke-data-"))
    db_path = tmp / "smoke.db"
    env = dict(os.environ)
    env.update(
        HOST=HOST,
        PORT=str(PORT),
        DATABASE_URL=f"sqlite:///{db_path}",
        # no SMTP host -> save-point emails land in <repo>/outbox as .eml files
    )
    server_log = open(tmp / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", HOST, "--port", str(PORT)],
        cwd=ROOT / "backend",
        env=env,
        stdout=server_log,
        stderr=subprocess.STDOUT,
    )
    try:
        await wait_healthy(proc, httpx)
        async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as c:
            r = await c.get("/health")
            step("GET /health returns ok", r.json().get("status") == "ok")

            r = await c.get("/")
            step("GET / serves the built PWA (or api-only notice)", r.status_code == 200)

            r = await c.post("/api/sessions", json={})
            sess = r.json()
            code, sid, token = sess["code"], sess["id"], sess["admin_token"]
            step("POST /api/sessions creates a game with a 6-char code", len(code) == 6, str(sess))

            r = await c.post("/api/players", json={"name": "SmokeTester", "email": "smoke@example.com"})
            pid = r.json()["id"]
            r = await c.post(
                f"/api/players/{pid}/character",
                json={"name": "Smoke the Bold", "sheet": {"class": "Fighter", "level": 1, "hp": 12}},
            )
            step("player + character sheet submit", r.status_code == 200 and r.json()["name"] == "Smoke the Bold")

            r = await c.post("/api/sessions/join", json={"code": code})
            joined = r.json()
            step("join by code returns snapshot", joined["snapshot"]["session"]["code"] == code)
            snap_chars = joined["snapshot"]["characters"]
            step("snapshot includes the submitted character", any(ch["name"] == "Smoke the Bold" for ch in snap_chars))

            r = await c.post(f"/api/sessions/{sid}/state", json={"state": "playing"}, headers={"X-Admin-Token": token})
            step("host starts session (admin token)", r.json()["state"] == "playing")

            r = await c.post("/api/sessions/join", json={"code": "NOPE99"})
            step("joining a bad code is rejected", r.status_code == 404)

            async with websockets.connect(f"{WS}/api/sessions/{sid}/ws") as ws_a, websockets.connect(
                f"{WS}/api/sessions/{sid}/ws"
            ) as ws_b:
                snap_a = json.loads(await ws_a.recv())
                await ws_b.recv()
                step("WS connect returns snapshot", snap_a.get("type") == "snapshot")

                await ws_a.send(json.dumps({"type": "roll", "faces": 20, "roller": "SmokeTester"}))
                ev_a = json.loads(await ws_a.recv())
                ev_b = json.loads(await ws_b.recv())
                ok = (
                    ev_a.get("type") == "dice"
                    and ev_b.get("type") == "dice"
                    and ev_a["payload"]["total"] == ev_b["payload"]["total"]
                    and 1 <= ev_a["payload"]["rolls"][0] <= 20
                )
                step("dice roll broadcast to all WS clients in real time", ok, f"a={ev_a} b={ev_b}")

                await ws_a.send(json.dumps({"type": "ping"}))
                pong = json.loads(await ws_a.recv())
                ok = pong.get("type") == "pong" and pong.get("clients") == 2
                step("WS ping/pong with client count", ok, str(pong))

            r = await c.post(
                f"/api/sessions/{sid}/roll", json={"count": 2, "faces": 6, "modifier": 3, "roller": "REST"}
            )
            roll = r.json()
            ok = (
                len(roll["rolls"]) == 2
                and roll["total"] == sum(roll["rolls"]) + 3
                and roll["dice"] == "2d6+3"
            )
            step("REST dice roll shape (2d6+3 in bounds)", ok, str(roll))

            r = await c.post(
                f"/api/sessions/{sid}/narrate", json={"scene": "The party enters the torch-lit crypt."}
            )
            nar = r.json()
            ok = isinstance(nar.get("text"), str) and len(nar["text"]) > 0
            step("AI narration responds (any provider incl. local fallback)", ok, str(nar))

            r = await c.post(
                f"/api/sessions/{sid}/notes",
                json={"transcript": "We search the room. The rogue checks for traps."},
            )
            step("table-talk notes summarized", r.status_code == 200 and "provider" in r.json())

            r = await c.post(f"/api/sessions/{sid}/chapter", headers={"X-Admin-Token": token})
            ok = r.json()["chapter_index"] == 1 and r.json()["state"] == "loading"
            step("next chapter advances and enters loading state", ok, str(r.json()))

            r = await c.post(
                f"/api/sessions/{sid}/maps",
                json={"label": "Smoke Chamber", "markers": [{"x": 50, "y": 50, "label": "party"}]},
                headers={"X-Admin-Token": token},
            )
            step("host sets the map", r.status_code == 200 and r.json()["label"] == "Smoke Chamber")

            r = await c.post(f"/api/sessions/{sid}/state", json={"state": "ended"}, headers={"X-Admin-Token": token})
            step("end session via admin token", r.json()["state"] == "ended")

            r = await c.post(f"/api/sessions/{sid}/state", json={"state": "playing"})
            step("admin actions rejected without token", r.status_code in (401, 403), str(r.status_code))

        outbox_dir = ROOT / "outbox"
        emls = sorted(outbox_dir.glob("*.eml")) if outbox_dir.exists() else []
        step("save-point email written to outbox/ on session end", len(emls) >= 1, f"outbox has {len(emls)} files")
        if emls:
            body = emls[-1].read_text(encoding="utf-8")
            ok = "Smoke the Bold" in body and "Save point" in body
            step("save-point email contains character + save point", ok, body[:200])
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        server_log.close()
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", type=int, default=1, help="number of consecutive passes to run")
    args = parser.parse_args()

    try:
        import httpx  # noqa: F401
    except ModuleNotFoundError:
        if VENV_PY.exists():
            os.execv(str(VENV_PY), [str(VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]])
        sys.exit("Backend dependencies are missing. Run ./scripts/setup.sh first (creates .venv).")

    import httpx
    import websockets

    failures = 0
    for i in range(1, args.watch + 1):
        print(f"smoke pass {i}/{args.watch}  (server on {BASE})")
        STEPS.clear()
        try:
            asyncio.run(run_pass(httpx, websockets))
            print(f"smoke pass {i}: all {len(STEPS)} steps passed")
        except Exception as exc:
            failures += 1
            print(f"smoke pass {i} FAILED: {exc}")
    if failures:
        print(f"\n{failures}/{args.watch} pass(es) failed")
        return 1
    print(f"\nall {args.watch} pass(es) succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
