"""Terminal-first Gemini Live client with an optional ADK development UI."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from difflib import SequenceMatcher
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
APP_DIR = PROJECT_DIR / "app"
INPUT_SAMPLE_RATE = 16_000
OUTPUT_SAMPLE_RATE = 24_000
ECHO_TAIL_SECONDS = 0.2


def _device(value: str | None) -> int | str | None:
    if value is None:
        return None
    return int(value) if value.isdigit() else value


def _merge_transcript(current: str, update: str) -> str:
    current = current.strip()
    update = update.strip()
    if not update:
        return current
    if not current or current in update:
        return update
    if update in current:
        return current
    compact_current = "".join(current.split())
    compact_update = "".join(update.split())
    if compact_current and compact_current in compact_update:
        return update
    if compact_update and compact_update in compact_current:
        return current
    length_ratio = min(len(current), len(update)) / max(len(current), len(update))
    if length_ratio >= 0.6 and SequenceMatcher(None, current, update).ratio() >= 0.75:
        return update

    common_prefix = 0
    for old_char, new_char in zip(current, update):
        if old_char != new_char:
            break
        common_prefix += 1
    prefix_threshold = min(
        20,
        max(4, len(current) // 2),
        max(4, len(update) // 2),
    )
    if common_prefix >= prefix_threshold:
        return update

    max_overlap = min(len(current), len(update))
    for overlap in range(max_overlap, 0, -1):
        if current.endswith(update[:overlap]):
            return current + update[overlap:]

    separator = "" if update[:1] in ".,!?;:" else " "
    return current + separator + update


async def _run_terminal(input_device: int | str | None, output_device: int | str | None) -> int:
    try:
        import certifi
        from dotenv import load_dotenv
        from google.adk.agents import LiveRequestQueue
        from google.adk.agents.run_config import RunConfig
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
    except ImportError as error:
        print(
            f"Eksik bağımlılık ({error.name}). Çalıştırın: "
            "python -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    try:
        import sounddevice as sd
    except Exception as error:
        print(f"Ses sistemi başlatılamadı: {error}", file=sys.stderr)
        return 1

    load_dotenv(APP_DIR / ".env", override=True)
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())

    if not os.getenv("GOOGLE_API_KEY"):
        print("app/.env içinde GOOGLE_API_KEY eksik.", file=sys.stderr)
        return 1

    # The agent reads its model from the environment during import.
    from app.google_search_agent.agent import root_agent

    logging.getLogger("google_adk").setLevel(logging.WARNING)
    logging.getLogger("google.adk").setLevel(logging.WARNING)

    app_name = "google_search_agent"
    user_id = "terminal-user"
    session_id = str(uuid.uuid4())
    sessions = InMemorySessionService()
    await sessions.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )
    runner = Runner(
        app_name=app_name,
        agent=root_agent,
        session_service=sessions,
    )
    live_queue = LiveRequestQueue()
    microphone_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=64)
    speaker_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    playback_active = threading.Event()
    speech_finished_at: float | None = None
    playback_started_at: float | None = None
    pending_response_latency: float | None = None
    loop = asyncio.get_running_loop()

    def microphone_callback(indata, frames, timing, status) -> None:
        del frames, timing
        if status:
            loop.call_soon_threadsafe(print, f"\n[Mikrofon uyarısı: {status}]")
        if playback_active.is_set():
            return
        audio = bytes(indata)

        def enqueue() -> None:
            if not microphone_queue.full():
                microphone_queue.put_nowait(audio)

        loop.call_soon_threadsafe(enqueue)

    async def send_microphone() -> None:
        while True:
            audio = await microphone_queue.get()
            live_queue.send_realtime(
                types.Blob(
                    mime_type=f"audio/pcm;rate={INPUT_SAMPLE_RATE}",
                    data=audio,
                )
            )

    async def play_speaker(output_stream) -> None:
        nonlocal speech_finished_at, playback_started_at, pending_response_latency
        while True:
            audio = await speaker_queue.get()
            if audio is None:
                return
            if not playback_active.is_set():
                playback_started_at = time.perf_counter()
            playback_active.set()
            await asyncio.to_thread(output_stream.write, audio)

            while True:
                try:
                    audio = await asyncio.wait_for(
                        speaker_queue.get(), timeout=ECHO_TAIL_SECONDS
                    )
                except TimeoutError:
                    playback_active.clear()
                    if speech_finished_at is not None and playback_started_at is not None:
                        pending_response_latency = (
                            playback_started_at - speech_finished_at + 0.30
                        )
                        report_pending_latency()
                    speech_finished_at = None
                    playback_started_at = None
                    break
                if audio is None:
                    playback_active.clear()
                    return
                await asyncio.to_thread(output_stream.write, audio)

    run_config = RunConfig(
        response_modalities=[types.Modality.AUDIO],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                prefix_padding_ms=100,
                silence_duration_ms=300,
            )
        ),
    )

    input_text = ""
    output_text = ""
    turn_rendered_rows = 0
    turn_display_open = False
    microphone_task: asyncio.Task[None] | None = None
    speaker_task: asyncio.Task[None] | None = None
    live_task: asyncio.Task[None] | None = None

    def rendered_rows(text: str) -> int:
        columns = max(20, shutil.get_terminal_size(fallback=(80, 24)).columns)
        return sum(max(1, (len(line) - 1) // columns + 1) for line in text.split("\n"))

    def clear_turn_display() -> None:
        if turn_rendered_rows <= 0:
            return
        print("\r", end="")
        for _ in range(turn_rendered_rows - 1):
            print("\033[1A", end="")
        for row in range(turn_rendered_rows):
            print("\033[2K", end="")
            if row < turn_rendered_rows - 1:
                print("\033[1B", end="")
        for _ in range(turn_rendered_rows - 1):
            print("\033[1A", end="")
        print("\r", end="")

    def show_turn_transcripts() -> None:
        nonlocal turn_rendered_rows, turn_display_open
        lines = []
        if input_text.strip():
            lines.append(f"Sen: {input_text.strip()}")
        if output_text.strip():
            lines.append(f"Gemini: {output_text.strip()}")
        if not lines:
            return
        if turn_display_open:
            clear_turn_display()
        rendered_text = "\n".join(lines)
        print(rendered_text, end="", flush=True)
        turn_rendered_rows = rendered_rows(rendered_text)
        turn_display_open = True

    def finish_turn_display() -> None:
        nonlocal turn_rendered_rows, turn_display_open
        if turn_display_open:
            print()
            turn_rendered_rows = 0
            turn_display_open = False

    def report_pending_latency() -> None:
        nonlocal pending_response_latency
        if pending_response_latency is None or turn_display_open:
            return
        print(
            "⏱️ "
            f"Geri dönüş: {max(0.0, pending_response_latency):.2f} sn"
        )
        pending_response_latency = None

    async def consume_live_events() -> None:
        nonlocal input_text, output_text
        nonlocal speech_finished_at, playback_started_at
        async for event in runner.run_live(
            user_id=user_id,
            session_id=session_id,
            live_request_queue=live_queue,
            run_config=run_config,
        ):
            if event.input_transcription:
                transcript = event.input_transcription
                if transcript.text and playback_started_at is None:
                    speech_finished_at = time.perf_counter()
                input_text = _merge_transcript(input_text, transcript.text or "")
                show_turn_transcripts()

            if event.output_transcription:
                transcript = event.output_transcription
                output_text = _merge_transcript(output_text, transcript.text or "")
                show_turn_transcripts()

            for part in event.content.parts if event.content else []:
                if (
                    part.inline_data
                    and part.inline_data.data
                    and (part.inline_data.mime_type or "").startswith("audio/")
                ):
                    await speaker_queue.put(part.inline_data.data)

            if event.turn_complete:
                finish_turn_display()
                report_pending_latency()
                input_text = ""
                output_text = ""

    try:
        print("Gemini Live bağlantısı kuruluyor...")
        live_task = asyncio.create_task(consume_live_events())
        # run_live establishes its WebSocket lazily. Do not capture speech until
        # the connection has had time to finish its setup handshake.
        await asyncio.sleep(1.0)
        if live_task.done():
            await live_task

        with sd.RawInputStream(
            samplerate=INPUT_SAMPLE_RATE,
            blocksize=1_600,
            device=input_device,
            channels=1,
            dtype="int16",
            callback=microphone_callback,
        ), sd.RawOutputStream(
            samplerate=OUTPUT_SAMPLE_RATE,
            blocksize=0,
            device=output_device,
            channels=1,
            dtype="int16",
        ) as output_stream:
            microphone_task = asyncio.create_task(send_microphone())
            speaker_task = asyncio.create_task(play_speaker(output_stream))
            print("Gemini Live hazır. Konuşabilirsiniz. Çıkmak için Ctrl+C.\n")
            await live_task

    except asyncio.CancelledError:
        raise
    except Exception as error:
        print(f"\nSesli oturum hatası: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    finally:
        live_queue.close()
        if microphone_task:
            microphone_task.cancel()
        if speaker_task:
            await speaker_queue.put(None)
        if live_task:
            live_task.cancel()
        await asyncio.gather(
            *(task for task in (microphone_task, speaker_task, live_task) if task),
            return_exceptions=True,
        )
        await runner.close()

    return 0


def _option_value(arguments: list[str], option: str, default: str) -> str:
    for index, argument in enumerate(arguments):
        if argument == option and index + 1 < len(arguments):
            return arguments[index + 1]
        if argument.startswith(f"{option}="):
            return argument.split("=", 1)[1]
    return default


def _open_browser_when_ready(host: str, port: int) -> None:
    connect_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((connect_host, port), timeout=0.25):
                webbrowser.open(f"http://{connect_host}:{port}")
                return
        except OSError:
            time.sleep(0.2)


def _run_web(arguments: list[str]) -> int:
    try:
        import certifi
    except ImportError:
        print("Bağımlılıklar eksik. requirements.txt dosyasını kurun.", file=sys.stderr)
        return 1

    if "--reload" not in arguments and "--no-reload" not in arguments:
        arguments = ["--no-reload", *arguments]
    host = _option_value(arguments, "--host", "127.0.0.1")
    port = int(_option_value(arguments, "--port", "8000"))
    threading.Thread(
        target=_open_browser_when_ready,
        args=(host, port),
        daemon=True,
    ).start()
    env = os.environ.copy()
    env.setdefault("SSL_CERT_FILE", certifi.where())
    return subprocess.call(
        [sys.executable, "-m", "google.adk.cli", "web", *arguments],
        cwd=APP_DIR,
        env=env,
    )


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--web":
        return _run_web(sys.argv[2:])

    parser = argparse.ArgumentParser(
        description="Gemini Live ile terminalden sesli konuşun."
    )
    parser.add_argument("--list-devices", action="store_true", help="Ses aygıtlarını listele")
    parser.add_argument("--input-device", help="Mikrofon aygıt numarası veya adı")
    parser.add_argument("--output-device", help="Hoparlör aygıt numarası veya adı")
    args = parser.parse_args()

    if args.list_devices:
        try:
            import sounddevice as sd

            print(sd.query_devices())
            return 0
        except Exception as error:
            print(f"Ses aygıtları okunamadı: {error}", file=sys.stderr)
            return 1

    try:
        return asyncio.run(
            _run_terminal(_device(args.input_device), _device(args.output_device))
        )
    except KeyboardInterrupt:
        print("\nOturum kapatıldı.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
