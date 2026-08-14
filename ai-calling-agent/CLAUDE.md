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
