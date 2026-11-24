"""Production server: Twilio webhook + media-stream WebSocket for the bot.

Twilio calls flow through two endpoints:

  POST /   Twilio's "A call comes in" webhook. We check the request really came
           from Twilio, check the caller is allowed, and answer with TwiML that
           tells Twilio to stream the call audio to /ws.
  WS /ws   Twilio streams the call audio here; we hand it to the Pipecat bot.

Environment (see .env.example):
  ALLOWED_CALLERS   Comma-separated phone numbers allowed to use the bot.
                    Empty = anyone can call (not recommended).
  MAX_CALL_MINUTES  Calls are ended after this long. Default 10.
  PUBLIC_HOST       Public hostname, e.g. abc123.ngrok.app. On Railway this is
                    filled in automatically from RAILWAY_PUBLIC_DOMAIN.
  PORT              Port to listen on. Default 7860 (Railway sets this).
"""

import asyncio
import os
import re
import secrets
import time
from xml.sax.saxutils import quoteattr

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import PlainTextResponse, Response
from loguru import logger
from twilio.request_validator import RequestValidator, get_signature_algorithm

from pipecat.runner.utils import parse_telephony_websocket
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from bot import run_bot

load_dotenv(override=True)

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
PUBLIC_HOST = os.getenv("PUBLIC_HOST") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
MAX_CALL_SECONDS = float(os.getenv("MAX_CALL_MINUTES", "10")) * 60
# Set to "false" only for local testing without Twilio.
VALIDATE_TWILIO_SIGNATURE = os.getenv("VALIDATE_TWILIO_SIGNATURE", "true").lower() != "false"

# One-time tokens handed to Twilio in the TwiML, so only calls that passed the
# webhook checks can open a media stream. token -> expiry time.
STREAM_TOKEN_TTL_SECONDS = 60
_stream_tokens: dict[str, float] = {}

validator = RequestValidator(TWILIO_AUTH_TOKEN)
app = FastAPI()


def normalize_number(number: str) -> str:
    """Normalize to E.164 (+15551234567); 10-digit numbers are assumed North American."""
    digits = re.sub(r"\D", "", number)
    if len(digits) == 10:
        digits = "1" + digits
    return "+" + digits if digits else ""


ALLOWED_CALLERS = {
    normalize_number(n) for n in os.getenv("ALLOWED_CALLERS", "").split(",") if n.strip()
}
if ALLOWED_CALLERS:
    logger.info(f"Accepting calls from {len(ALLOWED_CALLERS)} allowed number(s)")
else:
    logger.warning("ALLOWED_CALLERS is empty: anyone who calls the number can use the bot")


def twiml(body: str) -> Response:
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>{body}</Response>'
    return Response(content=xml, media_type="application/xml")


def public_host(request: Request) -> str:
    return PUBLIC_HOST or request.headers.get("x-forwarded-host") or request.headers["host"]


def is_from_twilio(request: Request, params: dict, host: str) -> bool:
    signature = request.headers.get("x-twilio-signature", "")
    algorithm = get_signature_algorithm(
        request.headers.get("x-twilio-webhooks-signature-settings")
    )
    path = request.url.path
    query = f"?{request.url.query}" if request.url.query else ""
    # Twilio signs the exact URL configured in the console; accept it with or
    # without a trailing slash so "https://host" and "https://host/" both work.
    candidates = {f"https://{host}{path}{query}"}
    if path == "/":
        candidates.add(f"https://{host}{query}")
    return any(validator.validate(url, params, signature, algorithm) for url in candidates)


@app.get("/health")
async def health():
    return PlainTextResponse("ok")


@app.post("/")
async def incoming_call(request: Request):
    params = dict(await request.form())
    host = public_host(request)

    if VALIDATE_TWILIO_SIGNATURE and not is_from_twilio(request, params, host):
        logger.warning("Rejected webhook: invalid Twilio signature")
        return Response(status_code=403)

    caller = normalize_number(params.get("From", ""))
    if ALLOWED_CALLERS and caller not in ALLOWED_CALLERS:
        logger.warning(f"Rejected call from {caller or 'unknown number'}: not in ALLOWED_CALLERS")
        return twiml("<Reject/>")

    now = time.monotonic()
    for expired in [t for t, exp in _stream_tokens.items() if exp < now]:
        _stream_tokens.pop(expired, None)
    token = secrets.token_urlsafe(24)
    _stream_tokens[token] = now + STREAM_TOKEN_TTL_SECONDS

    logger.info(f"Accepted call from {caller}")
    stream_url = quoteattr(f"wss://{host}/ws")
    return twiml(
        f"<Connect><Stream url={stream_url}>"
        f'<Parameter name="token" value={quoteattr(token)}/>'
        f"</Stream></Connect>"
    )


@app.websocket("/ws")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    transport_type, call_data = await parse_telephony_websocket(websocket)

    token = call_data.body.get("token", "")
    expiry = _stream_tokens.pop(token, None)
    if transport_type != "twilio" or expiry is None or expiry < time.monotonic():
        logger.warning("Rejected media stream: missing, expired or reused token")
        await websocket.close(code=4003)
        return

    serializer = TwilioFrameSerializer(
        stream_sid=call_data.stream_id,
        call_sid=call_data.call_id,
        account_sid=TWILIO_ACCOUNT_SID,
        auth_token=TWILIO_AUTH_TOKEN,
    )
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
        ),
    )
    await run_bot(transport, handle_sigint=False, max_call_seconds=MAX_CALL_SECONDS)


if __name__ == "__main__":
    if not PUBLIC_HOST:
        logger.warning("PUBLIC_HOST not set; using the Host header of each request")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))
