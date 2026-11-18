# Pipecat + Twilio + Claude phone assistant

Call a phone number, ask a question, and Claude answers you by voice.

```
Caller ──► Twilio ──(media stream WebSocket)──► Pipecat bot
                                                  │
              Deepgram STT ─► Claude (Anthropic) ─► Cartesia TTS
                                                  │
Caller ◄── Twilio ◄───────────────────────────────┘
```

Built on Pipecat's development runner (`pipecat.runner`), which provides the
`POST /` TwiML webhook and the `/ws` media-stream WebSocket for you.

## Prerequisites

- Python 3.11+
- API keys: [Anthropic](https://console.anthropic.com), [Deepgram](https://console.deepgram.com), [Cartesia](https://play.cartesia.ai)
- A [Twilio](https://console.twilio.com) account with a voice-capable phone number
- [ngrok](https://ngrok.com) (or any tunnel) so Twilio can reach your machine

## Setup

```bash
cd pipecat-twilio-claude
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
```

## Run

1. Start a tunnel to port 7860:

   ```bash
   ngrok http 7860
   ```

   Note the hostname it gives you, e.g. `abc123.ngrok.app`.

2. Start the bot, passing that hostname (no `https://`):

   ```bash
   python bot.py -t twilio -x abc123.ngrok.app
   ```

3. In the Twilio Console, open **Phone Numbers → Manage → Active numbers →
   your number → Voice Configuration** and set **A call comes in** to:

   - Webhook: `https://abc123.ngrok.app/`
   - Method: `HTTP POST`

   Save.

4. Call your Twilio number. Claude greets you; ask it anything.

## Customize

- **Personality / instructions:** edit `SYSTEM_PROMPT` in `bot.py`.
- **Model:** set `ANTHROPIC_MODEL` in `.env` (default `claude-opus-5-5`).
  `claude-haiku-5-5` responds faster and costs less.
- **Voice:** set `CARTESIA_VOICE_ID` to any voice from the Cartesia library.
- **Tools:** Pipecat supports function calling, so you can give Claude tools
  (weather, a database lookup, etc.) — see the Pipecat docs on function calling.

## Deploying

The ngrok setup is for development. For production, run `bot.py` on a host
with a public HTTPS URL (or Pipecat Cloud) and point the Twilio webhook there.
