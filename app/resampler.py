"""Preserve the FIR context and sample phase across PCM callbacks."""
from math import gcd

import numpy as np
from scipy.signal import resample_poly


class StreamingResampler:
    def __init__(self, source_rate, target_rate):
        divisor = gcd(source_rate, target_rate)
        self.up = target_rate // divisor
        self.down = source_rate // divisor
        # scipy's default FIR extends ten times the larger factor on either side.
        self.context = (10 * max(self.up, self.down) + self.up - 1) // self.up
        self.buffer = np.empty(0, dtype=np.float32)
        self.emitted = 0

    def push(self, samples, *, final=False):
        if self.up == self.down:
            return samples
        self.buffer = np.concatenate((self.buffer, samples))
        available = len(self.buffer) if final else max(0, len(self.buffer) - self.context)
        end = (available * self.up + self.down - 1) // self.down
        if end <= self.emitted:
            return np.empty(0, dtype=np.float32)
        block = resample_poly(self.buffer, self.up, self.down)
        result = block[self.emitted:end].copy()
        self.emitted = end
        keep_from = max(0, end * self.down // self.up - self.context)
        discard = keep_from // self.down * self.down
        self.buffer = self.buffer[discard:].copy()
        self.emitted -= discard * self.up // self.down
        return result

    def finish(self):
        return self.push(np.empty(0, dtype=np.float32), final=True)
