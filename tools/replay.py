"""Replay two mono PCM WAVs through capture, local ASR and the overlay API."""
import argparse
import json
from threading import Event
from time import monotonic
from urllib.request import urlopen
import wave

import numpy as np

from app.audio import LiveClipQueue, SourceCapture
from app.engine import ASRWorker
from app.overlay import OverlayServer
from app.state import CaptionState


class ReplaySettings(dict):
    def snapshot(self):
        return self.copy()


class WavCapture(SourceCapture):
    def __init__(self, source, clips, stop, rate):
        super().__init__(source, clips, stop, print)
        self.rate = rate

    def run(self):
        self._buffer_loop(1, capture_rate=self.rate)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", nargs=2)
    parser.add_argument("--model", default="medium")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    sources = [dict(id=f"wav{index}", name=f"WAV {index}", enabled=True) for index in (1, 2)]
    config = ReplaySettings(sources=sources, asr_model=args.model, asr_device=args.device,
                            censor=False)
    state = CaptionState(config)
    clips = LiveClipQueue(4)
    stop, ready = Event(), Event()
    decoder = ASRWorker(config, clips, state, print,
                        on_state=lambda _, stage: ready.set() if stage == "ready" else None)
    server = OverlayServer(state, 0)
    captures = []
    seen = set()
    server.start()
    decoder.start()
    try:
        if not ready.wait(60):
            raise RuntimeError("ASR backend did not become ready")
        streams = []
        for filename, source in zip(args.wav, sources):
            with wave.open(filename) as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                    raise ValueError("Replay requires mono 16-bit PCM WAV")
                rate = wav.getframerate()
                audio = np.frombuffer(wav.readframes(wav.getnframes()), "<i2").astype(np.float32) / 32768
            streams.append((np.pad(audio, (0, rate // 2)), rate // 50))
            captures.append(WavCapture(source, clips, stop, rate))
            captures[-1].start()
        endpoint = f"http://127.0.0.1:{server.httpd.server_port}/state"
        with urlopen(endpoint, timeout=2) as response:
            assert json.load(response)["captions"] == []
        feed_start = monotonic()
        for index in range(max((len(audio) + block - 1) // block for audio, block in streams)):
            stop.wait(max(0, feed_start + index * .02 - monotonic()))
            for capture, (audio, block) in zip(captures, streams):
                frame = audio[index * block:(index + 1) * block]
                if len(frame):
                    capture._emit(frame.tobytes())
        deadline = monotonic() + 8
        while monotonic() < deadline:
            with urlopen(endpoint, timeout=2) as response:
                seen.update(item["source"] for item in json.load(response)["captions"])
            if len(seen) == 2 and all(clips.metrics().get(source["id"], {}).get("published_final")
                                      for source in sources):
                break
            stop.wait(.05)
        print(json.dumps(dict(model=args.model, requested_backend=args.device,
                              effective_backend=decoder.active_device, overlay_sources=sorted(seen),
                              counters=clips.metrics(),
                              seconds={"/".join(key):np.percentile(values,[50,95,99]).round(4).tolist()
                                       for key, values in clips.timings().items()}), indent=2))
        if seen != {source["id"] for source in sources} or not all(
            clips.metrics().get(source["id"], {}).get("published_final") for source in sources
        ):
            raise RuntimeError("Replay did not publish final captions for both sources")
    finally:
        stop.set()
        decoder.stop()
        for capture in captures:
            capture.join()
        decoder.join()
        server.stop()


if __name__ == "__main__":
    main()
