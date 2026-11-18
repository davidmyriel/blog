"""Phone-call voice assistant: Twilio -> Pipecat -> Claude.

Call your Twilio number, ask a question out loud, and Claude answers by voice.

Pipeline:  caller audio -> Deepgram (speech-to-text) -> Claude (LLM)
           -> Cartesia (text-to-speech) -> caller

Run locally:
    ngrok http 7860
    python bot.py -t twilio -x <your-subdomain>.ngrok.app
"""

import os

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.base_transport import BaseTransport
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
from pipecat.workers.runner import WorkerRunner

load_dotenv(override=True)

SYSTEM_PROMPT = """You are a helpful voice assistant answering questions over a phone call.
Your replies are converted to speech, so:
- Answer in one to three short, conversational sentences unless asked for more.
- Never use markdown, bullet points, emojis, code blocks or special characters.
- Spell out numbers, symbols and abbreviations the way a person would say them.
- If you didn't catch the question, ask the caller to repeat it."""

# Only Twilio is enabled; the runner builds the Twilio serializer from the
# call data Twilio sends when the media stream connects.
transport_params = {
    "twilio": lambda: FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
    ),
}


async def run_bot(transport: BaseTransport, handle_sigint: bool):
    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])

    llm = AnthropicLLMService(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        settings=AnthropicLLMService.Settings(
            model=os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5"),
            system_instruction=SYSTEM_PROMPT,
            # Low effort keeps response latency short enough for a phone call.
            effort="low",
            max_tokens=1024,
        ),
    )

    tts = CartesiaTTSService(
        api_key=os.environ["CARTESIA_API_KEY"],
        settings=CartesiaTTSService.Settings(
            # "British Reading Lady" — swap for any voice ID from Cartesia.
            voice=os.getenv("CARTESIA_VOICE_ID", "71a7ad14-091c-4e8e-a314-022ece01c121"),
        ),
    )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline(
        [
            transport.input(),  # audio from the caller
            stt,
            user_aggregator,  # add the caller's words to the conversation
            llm,
            tts,
            transport.output(),  # audio back to the caller
            assistant_aggregator,  # add Claude's reply to the conversation
        ]
    )

    task = PipelineWorker(
        pipeline,
        params=PipelineParams(
            # Twilio media streams are 8 kHz mu-law.
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Caller connected")
        context.add_message(
            {
                "role": "user",
                "content": "The caller just connected. Greet them in one short sentence "
                "and ask what they'd like to know.",
            }
        )
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Caller hung up")
        await task.cancel()

    runner = WorkerRunner(handle_sigint=handle_sigint)
    await runner.add_workers(task)
    await runner.run()


async def bot(runner_args: RunnerArguments):
    """Entry point called by the Pipecat runner for each incoming call."""
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args.handle_sigint)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
