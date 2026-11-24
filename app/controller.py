"""Own transcription worker lifetimes on the caller's event loop."""
from enum import Enum, auto
from threading import RLock
from time import monotonic


class Phase(Enum):
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    FAILED = auto()


class SessionCaptions:
    def __init__(self, controller, generation):
        self.controller = controller
        self.generation = generation

    def publish(self, *args):
        with self.controller.lock:
            if self.controller.active_generation == self.generation:
                return self.controller.captions.publish(*args)
        return None

    def revise(self, *args):
        with self.controller.lock:
            if self.controller.active_generation == self.generation:
                return self.controller.captions.revise(*args)
        return False


class TranscriptionController:
    def __init__(self, captions):
        self.captions = captions
        self.lock = RLock()
        self.phase = Phase.STOPPED
        self.generation = 0
        self.active_generation = None
        self.workers = ()
        self.capture = None
        self.pending = None
        self.stop_started = None
        self.failed = False

    def start(self, factory):
        if self.phase is Phase.STOPPING:
            self.pending = factory
            return
        if self.phase in (Phase.STARTING, Phase.RUNNING):
            return
        self.phase = Phase.STARTING
        self.failed = False
        with self.lock:
            self.generation += 1
            self.active_generation = self.generation
        try:
            self.workers, self.capture = factory(SessionCaptions(self, self.generation))
            for worker in self.workers:
                worker.start()
        except Exception:
            self.stop()
            self.failed = True
            raise

    def start_capture(self):
        if self.phase in (Phase.STARTING, Phase.RUNNING):
            self.capture.start()
            self.phase = Phase.RUNNING

    def stop(self):
        self.pending = None
        if self.phase not in (Phase.STARTING, Phase.RUNNING):
            return
        self.phase = Phase.STOPPING
        self.stop_started = monotonic()
        with self.lock:
            self.active_generation = None
            self.captions.clear()
        if self.capture is not None:
            self.capture.stop()
        for worker in self.workers:
            worker.stop()

    def poll(self):
        if self.phase in (Phase.STARTING, Phase.RUNNING):
            if any(not worker.is_alive() for worker in self.workers):
                self.stop()
                self.failed = True
            elif self.capture is not None:
                self.capture.poll()
        if self.phase is not Phase.STOPPING:
            return
        if any(worker.is_alive() for worker in self.workers):
            return
        if self.capture is not None and self.capture.is_alive():
            return
        self.workers = ()
        self.capture = None
        self.phase = Phase.FAILED if self.failed else Phase.STOPPED
        pending, self.pending = self.pending, None
        if pending is not None:
            self.start(pending)
