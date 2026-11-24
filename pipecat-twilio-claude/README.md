# Pipecat + Twilio + Claude phone assistant

Call a phone number, ask a question, and Claude answers you by voice.

```
Caller ──► Twilio ──(media stream WebSocket)──► Pipecat bot
                                                  │
              Deepgram STT ─► Claude (Anthropic) ─► Cartesia TTS
                                                  │
Caller ◄── Twilio ◄───────────────────────────────┘
```


## Deploy on Railway (always on)

1. At [railway.app](https://railway.app): **New Project → Deploy from GitHub repo** and pick this repo.
2. Open the service's **Settings**:
   - **Root Directory:** `pipecat-twilio-claude`
   - **Networking → Generate Domain.** Copy the address it shows.
3. In **Variables**, add:

   | Variable | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | from console.anthropic.com |
   | `DEEPGRAM_API_KEY` | from console.deepgram.com |
   | `CARTESIA_API_KEY` | from play.cartesia.ai |
   | `TWILIO_ACCOUNT_SID` | Twilio Console → Account Info |
   | `TWILIO_AUTH_TOKEN` | Twilio Console → Account Info |
   | `ALLOWED_CALLERS` | **your own** phone number (the one you call from), e.g. `+16045551234`. Comma-separate several. |

4. In Twilio: **Phone Numbers → your number → Configuration details → Voice**.
   Set **A call comes in** to *Webhook*, `https://<your-railway-domain>/`, *HTTP POST*. Save.
5. Call your Twilio number.

Calls from numbers not in `ALLOWED_CALLERS` are rejected, and calls end after
`MAX_CALL_MINUTES` (default 10). Railway's Deploy Logs show each call.

## What's in here

- `bot.py`: the voice pipeline (Deepgram → Claude → Cartesia).
- `server.py`: the web server Twilio talks to. It checks that requests are
  really from Twilio, rejects callers not on the allowlist, and enforces the
  call time limit.
- `Dockerfile`, `railway.json`: Railway build and deploy settings.

## Run locally (optional)

```bash
cd pipecat-twilio-claude
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in keys, ALLOWED_CALLERS and PUBLIC_HOST
ngrok http 7860               # in another terminal; put its hostname in PUBLIC_HOST
python server.py
```

Then point the Twilio webhook at `https://<ngrok-host>/` as in step 4.

## Customize

- **Personality / instructions:** edit `SYSTEM_PROMPT` in `bot.py`.
- **Model:** set `ANTHROPIC_MODEL` in `.env` (default `claude-opus-5-5`).
  `claude-haiku-5-5` responds faster and costs less.
- **Voice:** set `CARTESIA_VOICE_ID` to any voice from the Cartesia library.
- **Tools:** Pipecat supports function calling, so you can give Claude tools
  (weather, a database lookup, etc.) — see the Pipecat docs on function calling.
