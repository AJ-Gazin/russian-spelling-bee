"""Abuse-resistance tests: generate rate limit, puzzle-pool pruning, and the
admin token gate on the daily re-pin.

Unlike test_api.py (one module-scoped client), each test here opens its own
TestClient context so it can set its own env knobs — the lifespan re-runs per
context and re-reads RSB_GENERATE_PER_HOUR / RSB_MAX_PUZZLES / RSB_ADMIN_TOKEN.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from fastapi.testclient import TestClient

_ENV_KEYS = (
    "RSB_DB",
    "RSB_STATE_DB",
    "TURSO_DATABASE_URL",
    "TURSO_AUTH_TOKEN",
    "RSB_ADMIN_TOKEN",
    "RSB_GENERATE_PER_HOUR",
    "RSB_MAX_PUZZLES",
)


@contextmanager
def make_client(tmp_path, **env: str):
    """Fresh app context against a temp state DB, with the given env knobs.
    Restores the caller's environment afterwards (tests must be hermetic)."""
    saved = {k: os.environ.pop(k, None) for k in _ENV_KEYS}
    os.environ["RSB_DB"] = str(tmp_path / "test.db")
    os.environ["RSB_STATE_DB"] = str(tmp_path / "test_state.db")
    os.environ.update(env)
    try:
        from rsb.api import app

        with TestClient(app) as c:
            yield c
    finally:
        for k in _ENV_KEYS:
            os.environ.pop(k, None)
            if saved[k] is not None:
                os.environ[k] = saved[k]


def _typeable_lemma(puzzle: dict) -> str:
    target = next((l for l in puzzle["lemmas"] if l["lemma"] in l["forms"]), None)
    assert target is not None, "puzzle has no self-fitting lemma"
    return target["lemma"]


def test_generate_rate_limit(tmp_path):
    with make_client(tmp_path, RSB_GENERATE_PER_HOUR="2") as client:
        assert client.post("/api/admin/generate").status_code == 200
        assert client.post("/api/admin/generate").status_code == 200
        # Third call in the same window is refused.
        assert client.post("/api/admin/generate").status_code == 429


def test_prune_keeps_daily_history_and_recent(tmp_path):
    with make_client(tmp_path, RSB_MAX_PUZZLES="3", RSB_GENERATE_PER_HOUR="0") as client:
        daily_id = client.get("/api/puzzle/daily").json()["id"]

        # Solve one word in a generated puzzle so it joins history.
        played = client.post("/api/admin/generate").json()
        g = client.post(
            f"/api/puzzle/{played['id']}/guess",
            json={"form": _typeable_lemma(played), "found_lemmas": []},
        )
        assert g.json()["status"] == "accepted"

        # Pile on unplayed puzzles until the oldest of them falls outside the
        # newest-3 window and gets pruned.
        unplayed = [client.post("/api/admin/generate").json()["id"] for _ in range(4)]

        # Protected: the daily pin, the played puzzle, and the newest ones.
        assert client.get(f"/api/puzzle/{daily_id}").status_code == 200
        assert client.get(f"/api/puzzle/{played['id']}").status_code == 200
        assert client.get(f"/api/puzzle/{unplayed[-1]}").status_code == 200
        # Pruned: the oldest unplayed generation is gone.
        assert client.get(f"/api/puzzle/{unplayed[0]}").status_code == 404


def test_daily_repin_requires_token_when_set(tmp_path):
    with make_client(tmp_path, RSB_ADMIN_TOKEN="sekret") as client:
        # Generation stays open — the frontend's "Новая игра" depends on it.
        p = client.post("/api/admin/generate")
        assert p.status_code == 200
        pid = p.json()["id"]

        assert client.post(f"/api/admin/daily/{pid}").status_code == 401
        assert (
            client.post(
                f"/api/admin/daily/{pid}", headers={"X-Admin-Token": "wrong"}
            ).status_code
            == 401
        )
        ok = client.post(f"/api/admin/daily/{pid}", headers={"X-Admin-Token": "sekret"})
        assert ok.status_code == 200
        assert client.get("/api/puzzle/daily").json()["id"] == pid


def test_daily_repin_open_when_token_unset(tmp_path):
    with make_client(tmp_path) as client:
        pid = client.post("/api/admin/generate").json()["id"]
        # No RSB_ADMIN_TOKEN in the environment ⇒ dev convenience: open.
        assert client.post(f"/api/admin/daily/{pid}").status_code == 200
