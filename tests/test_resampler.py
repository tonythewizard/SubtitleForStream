import numpy as np
from scipy.signal import resample_poly

from app.resampler import StreamingResampler


def test_resampler_matches_whole_signal_at_irregular_boundaries():
    for rate in (44100, 48000, 16000):
        source = np.random.default_rng(17).normal(size=11321).astype(np.float32)
        converter = StreamingResampler(rate, 16000)
        chunks = [converter.push(chunk) for chunk in np.array_split(source, 97)]
        actual = np.concatenate([*chunks, converter.finish()])
        np.testing.assert_allclose(actual, resample_poly(source, 16000, rate), atol=2e-6)
