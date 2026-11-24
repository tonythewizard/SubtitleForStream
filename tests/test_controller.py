from threading import Event, Thread

from app.controller import Phase, TranscriptionController
from app.state import CaptionState


def test_stop_start_waits_for_inference_and_discards_old_caption():
    entered, release = Event(), Event()
    sources = [{"id": "mic", "name": "Mic"}, {"id": "discord", "name": "Discord"}]
    state = CaptionState({"sources": sources})
    controller = TranscriptionController(state)
    sessions = []

    class Worker(Thread):
        def __init__(self, captions):
            super().__init__(daemon=True)
            self.captions = captions

        def run(self):
            if len(sessions) == 1:
                entered.set()
                release.wait()
            for source in sources:
                self.captions.publish(source, "demo")

        def stop(self):
            pass  # Simulates a native inference call that cannot be interrupted.

    def factory(captions):
        worker = Worker(captions)
        sessions.append(worker)
        return (worker,), None

    controller.start(factory)
    try:
        assert entered.wait(2)
        controller.stop()
        controller.start(factory)
        controller.poll()
        assert controller.phase is Phase.STOPPING
        assert len(sessions) == 1
        assert not state.snapshot()["captions"]
    finally:
        release.set()
        sessions[0].join(2)

    assert not state.snapshot()["captions"]
    controller.poll()
    assert len(sessions) == 2
    sessions[1].join(2)
    assert {item["source"] for item in state.snapshot()["captions"]} == {"mic", "discord"}
    current = state.snapshot()["captions"][0]
    assert not sessions[0].captions.revise(current["source"], current["id"], "old", "normal")
    assert state.snapshot()["captions"][0]["text"] == "demo"
    controller.stop()
    controller.poll()
    assert controller.phase is Phase.STOPPED
