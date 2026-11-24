from app.audio import LiveClipQueue


def clip(source, index, preview=False):
    return ({"id": source, "_partial": preview}, [index], 0)


def test_busy_source_preserves_other_final_and_rotates_service():
    queue = LiveClipQueue(4)
    for item in (clip("mic", 1), clip("discord", 2), clip("discord", 3),
                 clip("discord", 4), clip("discord", 5)):
        queue.put_clip(item)
    assert [queue.get_nowait()[1][0] for _ in range(4)] == [1, 3, 4, 5]
    assert queue.metrics()["discord"]["dropped_overload_final"] == 1

    for item in (clip("mic", 1), clip("mic", 2), clip("mic", 3), clip("discord", 4)):
        queue.put_clip(item)
    assert [queue.get_nowait()[1][0] for _ in range(4)] == [1, 4, 2, 3]


def test_final_outranks_preview_and_preview_is_replaced():
    queue = LiveClipQueue(3)
    for item in (clip("mic", 1, True), clip("mic", 2, True), clip("discord", 3)):
        queue.put_clip(item)
    assert queue.get_nowait()[1] == [3]
    assert queue.get_nowait()[1] == [2]
    assert queue.metrics()["mic"]["superseded_preview"] == 1
