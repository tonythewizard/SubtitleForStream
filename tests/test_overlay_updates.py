from queue import Queue
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json

from app.overlay import OverlayServer
from app.state import CaptionState


def test_long_poll_delivers_changes_and_rejects_foreign_host():
    state = CaptionState({})
    server = OverlayServer(state, 0)
    server.start()
    endpoint = f"http://127.0.0.1:{server.httpd.server_port}/state"
    received = Queue()

    def poll():
        with urlopen(Request(endpoint + "?wait=1", headers={"If-None-Match": version}), timeout=4) as response:
            received.put(json.load(response))

    try:
        with urlopen(endpoint, timeout=2) as response:
            version = response.headers["ETag"]
        assert version
        thread = Thread(target=poll)
        thread.start()
        state.publish({"id": "mic", "name": "Mic"}, "text")
        assert received.get(timeout=4)["captions"][0]["text"] == "text"
        thread.join(2)
        for headers in ({"Host": "foreign.invalid"}, {"Origin": "https://foreign.invalid"}):
            try:
                urlopen(Request(endpoint, headers=headers), timeout=2)
            except HTTPError as error:
                assert error.code == 403
            else:
                raise AssertionError("Foreign request was accepted")
    finally:
        server.stop()


def test_long_poll_removes_expired_caption_without_another_publish():
    state = CaptionState({"duration": .6})
    server = OverlayServer(state, 0)
    server.start()
    endpoint = f"http://127.0.0.1:{server.httpd.server_port}/state"
    try:
        state.publish({"id": "mic", "name": "Mic"}, "sample")
        with urlopen(endpoint, timeout=2) as response:
            assert json.load(response)["captions"]
            version = response.headers["ETag"]
        request = Request(endpoint + "?wait=1", headers={"If-None-Match": version})
        with urlopen(request, timeout=4) as response:
            assert json.load(response)["captions"] == []
            assert response.headers["ETag"] != version
    finally:
        server.stop()


def test_render_ack_records_only_one_sample_per_current_caption():
    state = CaptionState({})
    server = OverlayServer(state, 0)
    server.start()
    base = f"http://127.0.0.1:{server.httpd.server_port}"
    try:
        cid = state.publish({"id": "mic", "name": "Mic"}, "private words")
        for value in ("0" * 32, cid, cid):
            request = Request(base + "/render-ack", data=value.encode("ascii"), method="POST")
            with urlopen(request, timeout=2) as response:
                assert response.status == 204
        with urlopen(base + "/render-metrics", timeout=2) as response:
            samples = json.load(response)
        assert len(samples) == 1
        assert samples[0]["source"] == "mic" and samples[0]["seconds"] >= 0
        assert "private words" not in str(samples)
    finally:
        server.stop()
