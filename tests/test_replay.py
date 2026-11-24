from io import BytesIO
from threading import Event
from time import monotonic, sleep
from urllib.request import urlopen
from unittest.mock import patch
import json
import wave

import numpy as np

from app.audio import LiveClipQueue, SourceCapture
from app.engine import ASRWorker
from app.overlay import OverlayServer
from app.state import CaptionState


def wav_frames(frequency):
    rate = 48000
    t = np.arange(rate) / rate
    pcm = np.concatenate((np.sin(t * frequency * 2 * np.pi) * 8000, np.zeros(rate // 2)))
    wav = BytesIO()
    with wave.open(wav, "wb") as output:
        output.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        output.writeframes(pcm.astype("<i2").tobytes())
    wav.seek(0)
    with wave.open(wav) as source:
        while frame := source.readframes(960):
            yield (np.frombuffer(frame, "<i2").astype(np.float32) / 32768).tobytes()


class Config(dict):
    def snapshot(self):
        return self.copy()


def test_two_wav_sources_reach_overlay_with_separate_metrics():
    sources = [{"id": sid, "name": sid, "enabled": True} for sid in ("mic", "discord")]
    settings = Config(sources=sources, asr_model="tiny", asr_device="cpu", censor=False)
    state = CaptionState(settings)
    clips = LiveClipQueue(8)
    stop = Event()
    server = OverlayServer(state, 0)
    capture = []
    for source, frequency in zip(sources, (310, 460)):
        worker = SourceCapture(source, clips, stop, lambda message: None)
        worker.run = lambda w=worker: w._buffer_loop(1)
        for frame in wav_frames(frequency):
            worker._emit(frame)
        capture.append(worker)
    decoder = ASRWorker(settings, clips, state, lambda message: None)
    server.start()
    try:
        for worker in capture:
            worker.start()
        deadline = monotonic() + 3
        while sum(bool(v.get("queued")) for v in clips.metrics().values()) != 2 and monotonic() < deadline:
            sleep(.01)
        with patch.object(decoder, "_create_model", return_value=object()), patch.object(
            decoder, "_decode", return_value=("sample words", "en")
        ):
            decoder.start()
            deadline = monotonic() + 3
            while monotonic() < deadline:
                with urlopen(f"http://127.0.0.1:{server.httpd.server_port}/state", timeout=1) as response:
                    captions = json.load(response)["captions"]
                if {item["source"] for item in captions} == {"mic", "discord"} and all(
                    values.get("published_final") for values in clips.metrics().values()
                ):
                    break
                sleep(.01)
            else:
                raise AssertionError(clips.metrics())
            for source in sources:
                sid = source["id"]
                assert clips.metrics()[sid]["published_final"] == 1
                assert len(clips.timings()[sid, "final", "callback_to_publish"]) == 1
    finally:
        stop.set()
        decoder.stop()
        if decoder.ident is not None:
            decoder.join(2)
        for worker in capture:
            worker.join(2)
        server.stop()
