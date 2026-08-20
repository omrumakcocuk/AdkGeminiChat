"""Enable browser echo processing in the bundled ADK development UI."""

from __future__ import annotations

from pathlib import Path

import google.adk


MIC_ORIGINAL = "navigator.mediaDevices.getUserMedia({audio:!0})"
MIC_PATCHED = (
    "navigator.mediaDevices.getUserMedia({audio:{"
    "echoCancellation:!0,noiseSuppression:!0,autoGainControl:!0,channelCount:1"
    "}})"
)

LEGACY_PLAYBACK_PATCH = (
    "playIncomingAudio(){this.audioBuffer.length&&"
    "(window.__adkModelAudioUntil=Date.now()+750),"
    "this.audioPlayingService.playAudio(this.audioBuffer),this.audioBuffer=[]}"
)
PLAYBACK_ORIGINAL = (
    "playIncomingAudio(){this.audioPlayingService.playAudio(this.audioBuffer),"
    "this.audioBuffer=[]}"
)

SCHEDULE_ORIGINAL = "n.start(a),this.lastAudioTime=a+i.duration}"
SCHEDULE_PATCHED = (
    "n.start(a),this.lastAudioTime=a+i.duration,"
    "window.__adkModelAudioUntil=Date.now()+"
    "Math.max(0,(this.lastAudioTime-o)*1e3)+200}"
)

SEND_ORIGINAL = (
    "sendBufferedAudio(){let A=this.audioRecordingService.getCombinedAudioBuffer();"
    "if(!A)return;let e="
)
SEND_PATCHED = (
    "sendBufferedAudio(){let A=this.audioRecordingService.getCombinedAudioBuffer();"
    "if(!A)return;if(Date.now()<(window.__adkModelAudioUntil||0)){"
    "this.audioRecordingService.cleanAudioBuffer();return}let e="
)

RUN_CONFIG_ORIGINAL = """        run_config = RunConfig(
            response_modalities=modalities,
            proactivity=("""
RUN_CONFIG_PREVIOUS = """        run_config = RunConfig(
            response_modalities=modalities,
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                    prefix_padding_ms=350,
                    silence_duration_ms=500,
                ),
            ),
            proactivity=("""
RUN_CONFIG_PATCHED = """        run_config = RunConfig(
            response_modalities=modalities,
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                    prefix_padding_ms=150,
                    silence_duration_ms=350,
                ),
            ),
            proactivity=("""


def main() -> int:
    browser_dir = Path(google.adk.__file__).resolve().parent / "cli" / "browser"
    bundles = list(browser_dir.glob("main-*.js"))
    if not bundles:
        raise RuntimeError(f"ADK Web bundle not found in {browser_dir}")

    changed = 0
    for bundle in bundles:
        source = bundle.read_text(encoding="utf-8")
        # Migrate the earlier fixed 750 ms guard to playback-aware timing.
        updated = source.replace(LEGACY_PLAYBACK_PATCH, PLAYBACK_ORIGINAL, 1)
        for original, patched in (
            (MIC_ORIGINAL, MIC_PATCHED),
            (SCHEDULE_ORIGINAL, SCHEDULE_PATCHED),
            (SEND_ORIGINAL, SEND_PATCHED),
        ):
            if patched not in updated and original in updated:
                updated = updated.replace(original, patched, 1)
        if updated != source:
            bundle.write_text(updated, encoding="utf-8")
            changed += 1

    api_server = browser_dir.parent / "api_server.py"
    source = api_server.read_text(encoding="utf-8")
    if RUN_CONFIG_PREVIOUS in source:
        source = source.replace(RUN_CONFIG_PREVIOUS, RUN_CONFIG_PATCHED, 1)
        api_server.write_text(source, encoding="utf-8")
        changed += 1
    if RUN_CONFIG_PATCHED not in source and RUN_CONFIG_ORIGINAL in source:
        api_server.write_text(
            source.replace(RUN_CONFIG_ORIGINAL, RUN_CONFIG_PATCHED, 1),
            encoding="utf-8",
        )
        changed += 1

    if changed:
        print("ADK Web echo and background-speech protection patch applied.")
    else:
        print("ADK Web echo and background-speech protection is already enabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
