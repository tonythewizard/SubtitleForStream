from subprocess import TimeoutExpired
from unittest.mock import Mock

from app.vulkan import VulkanWhisper


def test_vulkan_cleanup_kills_server_if_graceful_stop_times_out():
    runtime = VulkanWhisper.__new__(VulkanWhisper)
    runtime.client = Mock()
    runtime.log = Mock()
    runtime.process = Mock()
    runtime.process.poll.return_value = None
    runtime.process.wait.side_effect = [TimeoutExpired("whisper-server", 5), 0]
    runtime.close()
    runtime.process.kill.assert_called_once()
    assert runtime.process.wait.call_count == 2
    runtime.client.close.assert_called_once()
