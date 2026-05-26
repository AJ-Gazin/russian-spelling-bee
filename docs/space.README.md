---
title: Russian Spelling Bee
emoji: 🐝
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 7860
pinned: false
short_description: Lemma-scored Russian Spelling Bee (Svelte SPA + FastAPI).
---

# Russian Spelling Bee

A Spelling-Bee-style daily Russian puzzle with **lemma-level scoring**: any
inflected form a player types is mapped to its dictionary headword via
pymorphy3 and credited once.

Source: https://github.com/AJ-Gazin/russian-spelling-bee

## What's running here

- Svelte 5 SPA served at `/`
- FastAPI backend under `/api/*` (see `/docs` for the OpenAPI UI)
- ~42k-lemma pymorphy3-validated dictionary, baked into the image
- Generated puzzles persist to a [Turso](https://turso.tech) libsql DB across
  Space restarts (configured via `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN`
  secrets)
