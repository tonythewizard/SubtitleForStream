"""Persistent local whisper.cpp backend for Vulkan adapters."""
import atexit
import io
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
from tempfile import TemporaryFile
import time
import wave

import httpx
import numpy as np

from .settings import BUNDLED_MODELS


def vulkan_gpus():
    executable = shutil.which('vulkaninfo')
    if not executable:
        return []
    try:
        result = subprocess.run(
            [executable, '--summary'], capture_output=True, text=True,
            errors='replace', timeout=3,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [(int(index), name.strip()) for index, name in re.findall(
        r'^GPU(\d+):(?:(?!^GPU\d+:)[\s\S])*?deviceName\s*=\s*([^\r\n]+)',
        result.stdout, re.MULTILINE)]


class VulkanWhisper:
    def __init__(self, size, index, stop_event):
        directory = Path(os.environ.get('SUBTITLEFORSTREAM_VULKAN_DIR') or
                         os.environ.get('STREAMCAPTIONS_VULKAN_DIR') or
                         BUNDLED_MODELS.parent / 'whisper-vulkan').resolve()
        executable = directory / 'whisper-server.exe'
        model = next((p for p in (directory / f'ggml-{size}-q5_0.bin',
                                  directory / f'ggml-{size}.bin') if p.is_file()), None)
        if not executable.is_file() or model is None:
            raise RuntimeError(
                f'In {directory} servono whisper-server.exe con Vulkan e ggml-{size}-q5_0.bin '
                f'(oppure ggml-{size}.bin). Vedi README.')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.client = httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False)
        self.log = TemporaryFile()
        self.process = None
        try:
            self.process = subprocess.Popen(
                [str(executable), '-m', str(model), '--host', '127.0.0.1',
                 '--port', str(port), '--no-flash-attn', '-bs', '1', '-bo', '1'],
                cwd=directory, env=dict(os.environ, GGML_VK_VISIBLE_DEVICES=str(index)),
                stdout=self.log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            deadline = time.monotonic()+45
            while self.process.poll() is None and time.monotonic()<deadline:
                if stop_event.wait(.15):
                    raise RuntimeError('Avvio Vulkan annullato.')
                try:
                    self.client.get('/', timeout=.5).raise_for_status()
                except httpx.HTTPError:
                    continue
                output = self._output()
                if re.search(r'using\s+Vulkan\d*\s+backend', output, re.I):
                    atexit.register(self.close)
                    return
                raise RuntimeError('Il server non ha confermato il backend Vulkan.')
            raise RuntimeError('Avvio whisper.cpp fallito. '+self._output()[-600:])
        except BaseException:
            self.close()
            raise

    def _output(self):
        # Reopen the descriptor via a separate read position without moving
        # the shared output offset used by the subprocess.
        size = os.fstat(self.log.fileno()).st_size
        if not size:
            return ''
        import mmap
        with mmap.mmap(self.log.fileno(), size, access=mmap.ACCESS_READ) as data:
            return data[:].decode('utf-8', errors='replace')

    def decode(self, audio, language):
        pcm = (np.clip(audio, -1, 1)*32767).astype('<i2')
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            wav.writeframes(pcm.tobytes())
        response = self.client.post(
            '/inference', data={'language':language or 'auto', 'translate':'false',
                               'response_format':'json' if language else 'verbose_json',
                               'no_language_probabilities':'true',
                               'temperature':'0', 'temperature_inc':'0'},
            files={'file':('clip.wav', buffer.getvalue(), 'audio/wav')}, timeout=10)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body.get('text'), str):
            raise RuntimeError(body.get('error') or 'Risposta Whisper Vulkan incompleta.')
        detected=body.get('language')
        codes={'italian':'it','english':'en','spanish':'es','french':'fr','german':'de'}
        return body['text'].strip(),language or codes.get(str(detected).lower(),detected)

    def close(self):
        atexit.unregister(self.close)
        try:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        finally:
            self.client.close()
            self.log.close()


if __name__ == '__main__':
    import argparse
    from threading import Event

    parser = argparse.ArgumentParser(description='Collauda Whisper Vulkan in locale.')
    parser.add_argument('model')
    parser.add_argument('gpu', type=int)
    args = parser.parse_args()
    devices = vulkan_gpus()
    index = args.gpu
    if index < 0:
        index = next((number for number,name in devices if 'Radeon' in name), -1)
    if index not in dict(devices):
        parser.error(f'Seleziona un indice Vulkan valido. Dispositivi: {devices}')
    backend = VulkanWhisper(args.model, index, Event())
    try:
        audio = (.08*np.sin(2*np.pi*220*np.arange(16000)/16000)).astype(np.float32)
        for attempt in range(2):
            start = time.perf_counter()
            backend.decode(audio, 'it')
            elapsed = time.perf_counter()-start
            print(f'Vulkan {index} ({dict(devices)[index]}) - prova {attempt+1}: {elapsed:.3f} s')
    finally:
        backend.close()
