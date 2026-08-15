"""TwiML response builders.

Every string a caller could hear on a static Twilio path (fallback,
error) lives here — never generated ad-hoc in a route. Prompts spoken
by the agent during a live call are in `conversation/prompts.yaml`
per invariant §2.2; TwiML is only for the connection edge."""

from __future__ import annotations

from urllib.parse import quote
from xml.etree.ElementTree import Element, SubElement, tostring


def connect_stream_twiml(
    wss_url: str,
    report_id: str,
    caller_hash: str,
    locale: str = "en-IN",
    entrypoint: str = "inbound_hotline",
) -> bytes:
    """<Response><Connect><Stream url="…"><Parameter …/></Stream></Connect></Response>

    `report_id` is minted before the stream opens — it is the idempotency
    key for the whole call (§15.1). A Twilio reconnect never creates a
    duplicate report."""
    root = Element("Response")
    connect = SubElement(root, "Connect")
    stream = SubElement(connect, "Stream", {"url": wss_url})
    for name, value in [
        ("report_id", report_id),
        ("caller_hash", caller_hash),
        ("locale", locale),
        ("entrypoint", entrypoint),
    ]:
        SubElement(stream, "Parameter", {"name": name, "value": value})
    return b'<?xml version="1.0" encoding="UTF-8"?>' + bytes(tostring(root, encoding="utf-8"))


def fallback_twiml(sms_link: str | None = None) -> bytes:
    """Static TwiML served on the Twilio number's Fallback URL. If the
    app is down entirely, the caller still gets a coherent response and
    an alternative channel."""
    root = Element("Response")
    say = SubElement(root, "Say", {"voice": "Polly.Aditi", "language": "en-IN"})
    if sms_link:
        say.text = (
            "Sorry, our voice line is temporarily unavailable. "
            "We're sending you a link to the FloodGuard web form now. "
            "Please try calling again in a few minutes."
        )
        SubElement(root, "Sms", {}).text = f"Report a coastal hazard: {sms_link}"
    else:
        say.text = (
            "Sorry, our voice line is temporarily unavailable. "
            "Please try calling again in a few minutes, "
            "or use the FloodGuard app."
        )
    SubElement(root, "Hangup")
    return b'<?xml version="1.0" encoding="UTF-8"?>' + bytes(tostring(root, encoding="utf-8"))


def gather_redirect_twiml(gather_start_path: str) -> bytes:
    """Response to `/voice/inbound` when RUNNER_MODE is on: skip the
    Media Streams `<Connect>` and jump straight into the Gather flow.
    A `<Redirect>` is used rather than embedding TwiML inline so the
    gather routes remain the single source of prompt sequencing —
    including consent, which must play before ask_intent."""
    root = Element("Response")
    redirect = SubElement(root, "Redirect", {"method": "POST"})
    redirect.text = gather_start_path
    return b'<?xml version="1.0" encoding="UTF-8"?>' + bytes(tostring(root, encoding="utf-8"))


def render_gather_step(
    say_texts: list[str],
    *,
    gather_action: str | None,
    dtmf_map: dict[str, str] | None,
    voice: str = "Polly.Aditi",
    language: str = "en-IN",
    speech_timeout: str = "auto",
) -> bytes:
    """Turn a driver `TurnStepResult` into TwiML.

    - `say_texts` is the ordered list of prompt texts (already rendered
      from the prompt bank). All but the last are plain `<Say>`; the
      last is either wrapped in a `<Gather>` (when `gather_action` is
      set) or followed by a `<Hangup>`.
    - `dtmf_map` sets `numDigits="1"` when non-empty so a single press
      completes the Gather immediately. Speech-only Gathers omit it.
    - No caller-facing text is generated here; texts are pre-rendered
      by the caller of this function via the prompt bank (§2.2)."""
    root = Element("Response")
    if not say_texts:
        SubElement(root, "Hangup")
        return b'<?xml version="1.0" encoding="UTF-8"?>' + bytes(tostring(root, encoding="utf-8"))

    leading = say_texts[:-1]
    trailing = say_texts[-1]

    for text in leading:
        say = SubElement(root, "Say", {"voice": voice, "language": language})
        say.text = text

    if gather_action is None:
        say = SubElement(root, "Say", {"voice": voice, "language": language})
        say.text = trailing
        SubElement(root, "Hangup")
    else:
        gather_attrs: dict[str, str] = {
            "input": "speech dtmf",
            "action": gather_action,
            "method": "POST",
            "language": language,
            "speechTimeout": speech_timeout,
            "actionOnEmptyResult": "true",
        }
        if dtmf_map:
            gather_attrs["numDigits"] = "1"
        gather = SubElement(root, "Gather", gather_attrs)
        say = SubElement(gather, "Say", {"voice": voice, "language": language})
        say.text = trailing
        # Redirect on no-input timeout so we re-enter the state machine
        # with a timeout event rather than dropping the call.
        redirect = SubElement(root, "Redirect", {"method": "POST"})
        redirect.text = gather_action

    return b'<?xml version="1.0" encoding="UTF-8"?>' + bytes(tostring(root, encoding="utf-8"))


def fatal_hangup_twiml(reason_code: str = "internal_error") -> bytes:
    """Used for hard failures (missing env, DB unreachable at boot). A
    call never leaks a raw stacktrace or a Twilio default error to the
    caller — the caller hears a short apology and hangs up."""
    root = Element("Response")
    say = SubElement(root, "Say", {"voice": "Polly.Aditi", "language": "en-IN"})
    say.text = (
        "Sorry, we're unable to take your call right now. Please try again shortly. Stay safe."
    )
    SubElement(root, "Hangup")
    # reason_code is emitted as an XML comment so it shows up in Twilio's
    # inspector without being spoken.
    payload = b'<?xml version="1.0" encoding="UTF-8"?>'
    payload += f"<!-- reason: {quote(reason_code)} -->".encode()
    payload += bytes(tostring(root, encoding="utf-8"))
    return payload
