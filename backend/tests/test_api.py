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

    # Re-submit the same string, accumulating found lemmas. If the string is a
    # homonym it cycles through the other in-set meanings (each accepted once,
    # always a new lemma); once all reachable meanings are found it must report
    # already_found. This exercises both the cycling and already_found paths.
    found = [j["lemma"]]
    for _ in range(6):
        rr = client.post(
            f"/api/puzzle/{pid}/guess",
            json={"form": form, "found_lemmas": found},
        ).json()
        if rr["status"] == "accepted":
            assert rr["lemma"] not in found, "cycling must yield a new lemma"
            found.append(rr["lemma"])
        else:
            assert rr["status"] == "already_found"
            assert rr["lemma"] in found
            break
    else:
        pytest.fail("never converged to already_found after cycling")


def test_puzzle_lemmas_include_constructible_forms(client):
    cur = client.get("/api/puzzle/current").json()
    letters = set(cur["letters"])
    center = cur["center"]
    for l in cur["lemmas"]:
        assert "forms" in l and l["forms"], f"{l['lemma']}: missing forms in API payload"
        for w in l["forms"]:
            # Every advertised form is built from the hive letters (Ё folds to Е)
            # and contains the center.
            folded = w.replace("ё", "е")
            assert set(folded) <= letters, f"{l['lemma']}: form {w} escapes the hive"
            assert center in folded, f"{l['lemma']}: form {w} lacks the center"


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


def test_daily_is_stable_across_generate(client):
    d1 = client.get("/api/puzzle/daily")
    assert d1.status_code == 200, d1.text
    daily_id = d1.json()["id"]
    # Generating a new puzzle must NOT change the daily/default puzzle — that
    # only rebinds the calling browser, never the shared default.
    other = client.post("/api/admin/generate").json()
    assert other["id"] != daily_id
    d2 = client.get("/api/puzzle/daily").json()
    assert d2["id"] == daily_id, "generating must not move the daily puzzle"


def test_admin_can_repin_daily(client):
    p = client.post("/api/admin/generate").json()
    r = client.post(f"/api/admin/daily/{p['id']}")
    assert r.status_code == 200
    assert client.get("/api/puzzle/daily").json()["id"] == p["id"]
    # Unknown puzzle id → 404.
    assert client.post("/api/admin/daily/9999999").status_code == 404


def test_history_records_on_first_correct_guess(client):
    # Generate a fresh puzzle so this test owns a known id.
    p = client.post("/api/admin/generate").json()
    pid = p["id"]

    # Before any correct guess, the puzzle is absent from history.
    hist_ids = {e["id"] for e in client.get("/api/history").json()}
    assert pid not in hist_ids

    # A correct guess enters it into history.
    form = p["lemmas"][0]["lemma"]
    g = client.post(f"/api/puzzle/{pid}/guess", json={"form": form, "found_lemmas": []})
    assert g.json()["status"] == "accepted"

    hist = client.get("/api/history").json()
    entry = next((e for e in hist if e["id"] == pid), None)
    assert entry is not None, "solved puzzle must appear in history"
    assert entry["letters"] == p["letters"]
    assert entry["center"] == p["center"]
    assert entry["total_points"] == p["total_points"]
    assert entry["started_at"]


def test_history_newest_first_and_limit(client):
    # Generate two more puzzles and solve a word in each, newest last.
    ids = []
    for _ in range(2):
        p = client.post("/api/admin/generate").json()
        client.post(
            f"/api/puzzle/{p['id']}/guess",
            json={"form": p["lemmas"][0]["lemma"], "found_lemmas": []},
        )
        ids.append(p["id"])

    hist = client.get("/api/history").json()
    pos = {e["id"]: i for i, e in enumerate(hist)}
    # The later-solved puzzle ranks ahead of the earlier one.
    assert pos[ids[1]] < pos[ids[0]]

    # limit is honored (and clamped to ≥1).
    assert len(client.get("/api/history?limit=1").json()) == 1


def test_history_mark_is_idempotent(client):
    p = client.post("/api/admin/generate").json()
    pid = p["id"]
    form = p["lemmas"][0]["lemma"]
    # Guess the same word twice — the second is already_found, not a new row.
    client.post(f"/api/puzzle/{pid}/guess", json={"form": form, "found_lemmas": []})
    client.post(f"/api/puzzle/{pid}/guess", json={"form": form, "found_lemmas": [form]})
    appearances = [e for e in client.get("/api/history").json() if e["id"] == pid]
    assert len(appearances) == 1
