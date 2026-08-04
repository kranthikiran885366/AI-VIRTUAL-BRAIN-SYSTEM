"""Audio buffer normalization helpers for EarAgent task dispatch."""

from __future__ import annotations

from typing import Any

import numpy as np


def coerce_audio_array(audio: Any, dtype=np.int16) -> np.ndarray:
    """Convert list/bytes/ndarray inputs into a contiguous int16 numpy array."""
    if isinstance(audio, np.ndarray):
        return audio.astype(dtype, copy=False)
    if isinstance(audio, (list, tuple)):
        return np.asarray(audio, dtype=dtype)
    if isinstance(audio, (bytes, bytearray, memoryview)):
        return np.frombuffer(audio, dtype=dtype)
    return np.asarray(audio, dtype=dtype)
