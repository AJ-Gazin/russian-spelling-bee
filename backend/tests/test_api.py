"""End-to-end API tests using FastAPI's TestClient.

We point the app at a temporary DB so we don't pollute the dev DB.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rsb_api")
    os.environ["RSB_DB"] = str(tmp / "test.db")
    os.environ["RSB_STATE_DB"] = str(tmp / "test_state.db")
    # Force the local-SQLite state store path even if Turso vars are exported
    # in the developer's shell — tests must be hermetic.
    saved_turso = {
        k: os.environ.pop(k) for k in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN")
        if k in os.environ
    }
    # RSB_LEMMAS unset → falls back to stub.
    # Importing app *after* setting env so lifespan picks it up.
    from rsb.api import app
    with TestClient(app) as c:
        yield c
    os.environ.pop("RSB_DB", None)
    os.environ.pop("RSB_STATE_DB", None)
    os.environ.update(saved_turso)


def test_current_puzzle_autocreated(client):
    r = client.get("/api/puzzle/current")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["letters"]) == 7
    assert data["center"] == data["letters"][0]
    assert data["total_points"] > 0
    assert len(data["lemmas"]) > 0


def test_get_puzzle_by_id(client):
    cur = client.get("/api/puzzle/current").json()
    pid = cur["id"]
    r = client.get(f"/api/puzzle/{pid}")
    assert r.status_code == 200
    assert r.json()["id"] == pid


def test_get_missing_puzzle_404(client):
    r = client.get("/api/puzzle/9999999")
    assert r.status_code == 404


def test_guess_accepted_and_already_found(client):
    cur = client.get("/api/puzzle/current").json()
    pid = cur["id"]
    # Pick the first lemma in the puzzle as a guaranteed-valid guess.
    target = cur["lemmas"][0]
    form = target["lemma"]  # just use the lemma itself — it parses to itself.
    r = client.post(f"/api/puzzle/{pid}/guess", json={"form": form, "found_lemmas": []})
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "accepted"
    assert j["lemma"] == target["lemma"]
    assert j["points"] == target["points"]

    # Now repeat with the lemma already in found_lemmas.
    r2 = client.post(
        f"/api/puzzle/{pid}/guess",
        json={"form": form, "found_lemmas": [target["lemma"]]},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "already_found"
    assert r2.json()["lemma"] == target["lemma"]


def test_guess_not_in_set(client):
    cur = client.get("/api/puzzle/current").json()
    pid = cur["id"]
    # Pick a real Russian word that's almost certainly *not* in this small puzzle.
    r = client.post(f"/api/puzzle/{pid}/guess", json={"form": "автомобилестроение"})
    assert r.status_code == 200
    # Either it lemmatizes and falls outside (not_in_set), or pymorphy3 can't
    # parse it (unparseable). Both are acceptable rejection paths for this test.
    assert r.json()["status"] in {"not_in_set", "unparseable"}


def test_guess_unparseable(client):
    cur = client.get("/api/puzzle/current").json()
    pid = cur["id"]
    r = client.post(f"/api/puzzle/{pid}/guess", json={"form": "—"})
    assert r.status_code == 200
    assert r.json()["status"] in {"unparseable", "not_in_set"}
