# Operating rules for the FloodGuard Voice Agent repository

These are hard invariants. Violating any of them is not a style issue — it's
a life-safety-adjacent bug. See `ai-calling-agent.md` §2 for the full rationale.

## Architecture invariants (never violate)

1. **The LLM never decides the next conversation node.** Routing is the
   deterministic graph in `src/fg_voice/conversation/graph.py`. The LLM is
   a bounded function: utterance in, structured JSON out. It does not
   choose transitions, invent questions, or generate caller-facing prose.

2. **All caller-facing text lives in `src/fg_voice/conversation/prompts.yaml`.**
   Never hardcode a string that a caller could hear. Dynamic values are
   injected via strict template substitution with a variable whitelist.

3. **`conversation/` must not import from `rag/ingest_sop` or any module
   that could produce free-form caller-facing text.** Enforced by
   `import-linter` (see `.importlinter`). CI fails if this contract breaks.

4. **The audio path is fully async.** Any blocking call (denoise, embed,
   FAISS search) goes in the bounded `ThreadPoolExecutor`. One sync call
   in the audio loop stutters every concurrent call on that worker.

5. **Report submission uses the transactional outbox.** The caller never
   hears a failure. If the downstream write fails, the caller still hears
   success and the outbox worker retries.

6. **Raw phone numbers are never persisted.** Use `caller_hash =
   HMAC-SHA256(msisdn, CALLER_HASH_PEPPER)` everywhere. The raw number
   exists only in memory during the call and in Twilio's own logs.

7. **Every external dependency needs a documented degraded mode** before
   it is added. See §2.6 of the spec. No exceptions.

8. **The agent does not give safety advice.** Injury / entrapment /
   immediate danger → fixed `emergency_redirect` prompt directing to
   112, plus `life_safety_flag`. Enforced by keyword+kNN tripwire
   *before* the extraction LLM sees the turn.

## Working rules

- Work **one phase at a time** (see spec §19). Do not start the next
  phase until its exit gate passes.
- Every new node, prompt, or slot needs, in the same commit:
  a unit test, a golden fixture, and a `prompts.yaml` entry.
- Any change touching the audio path must be followed by `make bench`.
  A p95 regression is a blocking failure.
- Do not add a dependency without stating what it replaces and what
  happens when it is unavailable.
- When you find a real call that failed, add it to `data/eval/golden/`
  **before** fixing it.
- Latency SLOs are non-negotiable: p95 end-of-caller-speech → first
  audio byte ≤ 1200 ms; p50 ≤ 700 ms.

## Commands

```
make dev            # local stack (postgres+postgis+pgvector, redis, localstack)
make down           # stop local stack
make test           # unit + property
make lint           # ruff + mypy + import-linter contracts
make golden         # audio → slot regression (P3+)
make noise          # SNR sweep report (P3+)
make bench          # latency budget assertion (P4+)
make sim            # persona simulation (P8+)
make render-bank    # rerender the prerendered TTS audio bank
make deploy ENV=staging
```

## Repository layout

Follow spec §6 exactly. The layout is not incidental — the import-linter
contracts and the deployment topology both assume it.

## Phase Progress

| Phase | Status | Notes |
|-------|--------|-------|
| P0 — Scaffold | ✅ Done | Monorepo, docker-compose, CI |
| P1 — Telephony | ✅ Done | Twilio bidirectional WS, DTMF, call_sessions |
| P2 — Conversation Graph | ✅ Done | Deterministic FSM, keyword extraction, pre-rendered TTS |
| P3 — Audio Pipeline | ✅ Done | STT/TTS, noise sweep, barge-in, DTMF fallback |
| P4 — RAG Layer | ✅ Done | See P4 completion details below |
| P5 — Persistence | ✅ Done | See P5 completion details below |
| P6 — Post-call Enrichment | 🔲 Next | Post-call SMS pin-drop offer is the last remaining P6 item |

### P4 completion details (2026-08-17)

**Delivered:**
- `rag/gazetteer.py` — 3-tier gazetteer (districts + mandals + coastal POIs) with name/phonetic/district/state indices
- `rag/resolve_place.py` — hybrid RRF resolver (exact + substring + phonetic + fuzzy) with geographic prior re-rank
- `rag/snapshot.py` — FAISS snapshot builder + hot reload (numpy-KNN fallback when faiss-cpu absent)
- `rag/phonetic.py` — Double Metaphone + ASCII normalisation
- `rag/keyterms.py` — dynamic keyterm construction from gazetteer + geographic prior
- `rag/taxonomy.py` — hazard classification from `data/taxonomy/hazards.yaml`
- `extraction/hybrid_extractor.py` — LLM extraction replacing keyword rules
- `data/gazetteer/` — districts.json (AP + TG), mandals.json, coastal_pois.json
- `data/eval/geo/fragments.json` — 300-fragment eval set (exact, substring, variant, phonetic, ambiguous, compound, edge, negative)
- `scripts/run_geo_eval.py` — eval runner + exit gate checker
- `tests/unit/test_geo_eval.py` — regression test pinning exit gate
- `tests/unit/test_resolve_place.py` — resolver unit tests
- `tests/unit/test_gazetteer.py`, `test_phonetic.py`, `test_snapshot.py`, `test_taxonomy.py`, `test_keyterms.py`

**Exit gate targets (spec §10.1):**
- Geo resolution ≥ 90% correct at confidence ≥ 0.85 — ✅
- Confidently-wrong rate ≤ 5% — ✅
- `rag.resolve` p95 < 25 ms — ✅
- Hazard classification ≥ 93% — ✅

**Commands:**
- `make geo-eval` — run the full 300-fragment eval + exit gate check
- `make bench` — latency budget assertion
- `make test` — unit + property tests (includes `test_geo_eval.py` regression)

### P5 completion details (2026-08-18)

**Delivered** (server-side landed piecemeal across 2026-08-15/16; final
app-integration + backfill closeout on 2026-08-18):
- `persistence/{db,models,outbox,relay,broker,dispatchers,csv_projector,alerts,dlq_monitor}.py` — Report/Outbox schema, `ReportSink` protocol, `SqlReportSink`, transactional outbox + `OutboxRelay` with `SELECT ... FOR UPDATE SKIP LOCKED`, `InProcessBroker` fan-out, `PubSub`/`Chain`/`CsvProjector`/`Alert` dispatchers, DLQ depth monitor
- Alembic wired (`alembic.ini`, `alembic/env.py`, migrations `2026081501` initial → `…04` QA sampling)
- `api/routes_reports.py` — `GET /reports/stream` (SSE with `:connected`, 15s `:keepalive`, `lagged` sentinel), `GET /reports/{short_ref}`, `GET /reports` (keyset pagination + source/hazard/severity/life_safety/qa_sample/qa_reviewed/from/to filters), `GET /reports/export.csv` (streaming with UTF-8 BOM), `POST /reports/{short_ref}/qa_review`
- `api/routes_dlq.py` — list / detail / retry / purge, admin-guarded
- `api/auth.py::require_admin_api_key` — HMAC-safe `X-Admin-Api-Key` header check, prod boot fails loud without it
- `persistence/csv_projector.py` — single-writer CSV appender with `fcntl.flock` per-node; §12.2 29-column schema; `row_from_report()` shared with `/reports/export.csv` so live projector + batch export can't drift
- `utils/redact.py` + `description_clean` column — write-time PII redaction on Indian phone patterns, emails, and 4-4-4 Aadhaar so every outbound artifact (SSE, CSV, alerts) is PII-safe
- `persistence/db.py::run_migrations_at_boot()` behind `MIGRATE_ON_BOOT` flag (default off; deploy-step init-container is safer for multi-node)
- `mobile/lib/data/api/voice_reports_sse.dart` + `data/models/voice_report.dart` + `features/report/voice_reports_provider.dart` — Flutter SSE listener with 15s polling fallback, admin key via `--dart-define=VOICE_ADMIN_API_KEY=…`, Riverpod `liveVoiceReportsProvider` accumulates the last 100 reports keyed by id
- `scripts/backfill_source.py` — dry-run-by-default one-shot that sets `source='voice'` on empty rows, batches to avoid a giant lock (`--apply` commits, `--value` and `--batch` are overridable)

**Exit gate (spec §P5):**
- Phone call produces a row in `reports` — ✅ `SqlReportSink` writes Report + Outbox in one tx
- Line in the CSV within 10 s — ✅ `CsvProjectorDispatcher` on the relay poll loop (default `RELAY_POLL_INTERVAL_SEC=1.0`)
- Live SSE update in the Flutter app — ✅ `PubSubDispatcher` → broker → `/reports/stream` → `VoiceReportsSseClient`
- Killing the DB mid-submission still results in the caller hearing success and the report landing after recovery — ✅ outbox is idempotent on `report_id` (Twilio retries safe), sink failures swallowed per §2.3
- Two simultaneous calls never corrupt the CSV — ✅ `fcntl.flock` guards the single-writer path

**Commands:**
- `uv run python scripts/backfill_source.py --apply` — normalise legacy rows to `source='voice'`
- `flutter run --dart-define=API_BASE_URL=https://voice.floodguard.in --dart-define=VOICE_ADMIN_API_KEY=…` — mobile app subscribes to the live feed
- `make test` — 653 unit tests green (+4 backfill)

