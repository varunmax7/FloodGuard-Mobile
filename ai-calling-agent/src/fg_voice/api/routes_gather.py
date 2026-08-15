"""Twilio `<Gather>`-based conversation endpoints (P2.6).

The Gather flow is an HTTP-per-turn alternative to the streaming Media
Streams path. Twilio does the STT itself and POSTs the result back
after every caller utterance; each POST is one turn, and we answer
with the TwiML for the next.

Two endpoints:

- `POST /voice/gather/start` — first webhook after `/voice/inbound`
  redirects to us (RUNNER_MODE=true). Creates a fresh CallState and
  returns TwiML that plays the consent notice + opens the first
  Gather on ask_intent.

- `POST /voice/gather/next` — every subsequent turn. Applies the
  caller's SpeechResult or Digits to the current node, advances the
  state machine, returns TwiML for the next prompt(s) + Gather (or
  Hangup on a terminal).

Both validate `X-Twilio-Signature`. Both are idempotent on `CallSid`
via the CallState store — a Twilio retry mid-flow re-enters the same
node."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import Response

from fg_voice.api.routes_voice import _validate
from fg_voice.config import get_settings
from fg_voice.conversation.driver import (
    CallerInput,
    CallStateMissing,
    TurnDriver,
    TurnStepResult,
)
from fg_voice.conversation.graph import build_graph
from fg_voice.conversation.prompt_bank import PromptBank, load_prompt_bank
from fg_voice.conversation.state_store import get_call_state_store
from fg_voice.obs.logging import get_logger
from fg_voice.persistence.session_store import get_session_store
from fg_voice.telephony.twilio_twiml import fatal_hangup_twiml, render_gather_step
from fg_voice.utils.hashing import hash_msisdn

log = get_logger(__name__)
router = APIRouter(prefix="/voice/gather", tags=["voice", "gather"])

# Overridable in tests — same pattern as routes_voice.
_call_state_store_provider = get_call_state_store
_session_store_provider = get_session_store
_prompt_bank_loader = load_prompt_bank
_graph_builder = build_graph


NEXT_ACTION_PATH = "/voice/gather/next"


async def _make_driver() -> TurnDriver:
    return TurnDriver(
        graph=_graph_builder(),
        prompt_bank=_prompt_bank_loader(),
        state_store=await _call_state_store_provider(),
    )


@router.post("/start", response_class=Response)
async def gather_start(
    request: Request,
    x_twilio_signature: Annotated[str | None, Header(alias="X-Twilio-Signature")] = None,
) -> Response:
    """First turn of a Gather-mode call. Creates the CallState + session
    row, then returns TwiML for consent + ask_intent."""
    form = await request.form()
    params: dict[str, str] = {k: str(v) for k, v in form.items()}
    await _validate(request, x_twilio_signature, params)

    settings = get_settings()
    call_sid = params.get("CallSid", "")
    caller = params.get("From", "")
    caller_hash = hash_msisdn(caller, settings.caller_hash_pepper.get_secret_value())

    # Session row for finalisation metadata + CallState mint.
    report_id = str(uuid.uuid4())
    sess = await _session_store_provider()
    await sess.create(
        call_sid=call_sid,
        report_id=report_id,
        caller_hash=caller_hash,
        direction="inbound",
    )

    driver = await _make_driver()
    try:
        state, step = await driver.start_call(call_sid=call_sid, caller_hash=caller_hash)
    except Exception as exc:  # pragma: no cover — belt-and-braces
        log.exception("gather.start.driver_failed", call_sid=call_sid, error=str(exc))
        return Response(
            content=fatal_hangup_twiml("gather_start_error"),
            media_type="application/xml",
        )

    log.info(
        "voice.gather.start",
        call_sid=call_sid,
        report_id=str(state.report_id),
        first_prompt=step.prompts_to_play[-1] if step.prompts_to_play else None,
    )
    return _twiml_response(step, driver.prompt_bank)


@router.post("/next", response_class=Response)
async def gather_next(
    request: Request,
    x_twilio_signature: Annotated[str | None, Header(alias="X-Twilio-Signature")] = None,
) -> Response:
    """Subsequent turns. Reads SpeechResult / Digits from the form
    body, advances the driver, and returns the next TwiML."""
    form = await request.form()
    params: dict[str, str] = {k: str(v) for k, v in form.items()}
    await _validate(request, x_twilio_signature, params)

    call_sid = params.get("CallSid", "")
    speech = params.get("SpeechResult", "").strip()
    digits = params.get("Digits", "").strip()

    if digits:
        # Take the last digit if Twilio sent more than one (numDigits=1
        # in the TwiML makes this the common case anyway).
        caller_input = CallerInput.dtmf(digit=digits[-1])
    elif speech:
        caller_input = CallerInput.speech(transcript=speech)
    else:
        caller_input = CallerInput.timeout()

    driver = await _make_driver()
    try:
        _state, step = await driver.step(call_sid=call_sid, caller_input=caller_input)
    except CallStateMissing:
        log.warning("voice.gather.next.state_missing", call_sid=call_sid)
        return Response(
            content=fatal_hangup_twiml("call_state_expired"),
            media_type="application/xml",
            status_code=status.HTTP_200_OK,
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("gather.next.driver_failed", call_sid=call_sid, error=str(exc))
        return Response(
            content=fatal_hangup_twiml("gather_next_error"),
            media_type="application/xml",
        )

    log.info(
        "voice.gather.next",
        call_sid=call_sid,
        input_kind=caller_input.kind,
        action=step.action,
        prompt_ids=list(step.prompts_to_play),
    )
    return _twiml_response(step, driver.prompt_bank)


def _twiml_response(step: TurnStepResult, prompt_bank: PromptBank) -> Response:
    """Render prompt IDs to their TwiML text via the prompt bank, then
    hand off to `render_gather_step`."""
    say_texts: list[str] = []
    for pid in step.prompts_to_play:
        vars_for_pid = step.prompt_variables.get(pid, {})
        say_texts.append(prompt_bank.render(pid, **vars_for_pid))

    body = render_gather_step(
        say_texts=say_texts,
        gather_action=NEXT_ACTION_PATH if step.action == "gather" else None,
        dtmf_map=step.dtmf_map,
    )
    return Response(content=body, media_type="application/xml")
