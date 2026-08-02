"""
AudioListener — Production implementation.

Fixes:
  - Bug: `time` parameter in `_audio_callback` shadowed stdlib `time` module.
    Fixed: renamed parameter to `cb_time`.
  - Bug: `np.frombuffer(indata, ...)` is wrong when sounddevice passes a numpy array.
    Fixed: use `indata.copy()` directly.
  - sounddevice / webrtcvad / rnnoise are optional — fall back gracefully.
"""

import logging
import queue
import threading
import time as _time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    np = None  # type: ignore

try:
    import sounddevice as sd
    _HAS_SD = True
except ImportError:
    _HAS_SD = False
    sd = None  # type: ignore

try:
    import webrtcvad
    _HAS_VAD = True
except ImportError:
    _HAS_VAD = False
    webrtcvad = None  # type: ignore

try:
    import rnnoise
    _HAS_RNNOISE = True
except ImportError:
    _HAS_RNNOISE = False
    rnnoise = None  # type: ignore


class AudioListener:
    """
    Microphone capture with optional VAD and noise filtering.
    Falls back gracefully when sounddevice / webrtcvad / rnnoise are unavailable.
    """

    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        audio_cfg = config.get("audio", {})
        noise_cfg = config.get("noise_filtering", {})

        self.sample_rate: int = int(audio_cfg.get("sample_rate", 16000))
        self.channels: int = int(audio_cfg.get("channels", 1))
        self.chunk_size: int = int(audio_cfg.get("chunk_size", 1024))
        self.format: str = audio_cfg.get("format", "int16")
        self.device_index: Optional[int] = audio_cfg.get("device_index", None)
        self.timeout: float = float(audio_cfg.get("timeout", 5.0))
        self.silence_threshold: float = float(audio_cfg.get("silence_threshold", 0.01))
        self.silence_duration: float = float(audio_cfg.get("silence_duration", 1.0))
        self.continuous_listening: bool = bool(
            config.get("speech_recognition", {}).get("continuous_listening", True)
        )

        self.noise_filtering_enabled: bool = bool(noise_cfg.get("enabled", True))
        self.noise_method: str = noise_cfg.get("method", "webrtc")

        self.audio_queue: queue.Queue = queue.Queue()
        self.is_listening: bool = False
        self.current_stream = None
        self.noise_filter = None

        # VAD — graceful fallback if webrtcvad not installed
        self.vad = None
        if _HAS_VAD:
            try:
                self.vad = webrtcvad.Vad(3)
            except Exception as e:
                self.logger.warning(f"AudioListener: webrtcvad init failed: {e}")

        if self.noise_filtering_enabled and _HAS_RNNOISE and self.noise_method == "rnnoise":
            try:
                self.noise_filter = rnnoise.Denoise()
            except Exception as e:
                self.logger.warning(f"AudioListener: rnnoise init failed: {e}")
                self.noise_filtering_enabled = False

    # ─── Listening ────────────────────────────────────────────────────────────

    def start_listening(self, callback: Optional[Callable] = None):
        if self.is_listening:
            self.logger.warning("AudioListener: already listening")
            return

        if not _HAS_SD:
            self.logger.warning(
                "AudioListener: sounddevice not installed — "
                "cannot capture live audio. Install sounddevice to enable mic input."
            )
            return

        try:
            self.is_listening = True
            self.audio_queue = queue.Queue()
            self.current_stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.format,
                device=self.device_index,
                blocksize=self.chunk_size,
                callback=self._audio_callback,
            )
            self.current_stream.start()
            self.logger.info("AudioListener: started microphone stream")
            if callback:
                threading.Thread(
                    target=self._process_audio,
                    args=(callback,),
                    daemon=True,
                ).start()
        except Exception as e:
            self.is_listening = False
            self.logger.error(f"AudioListener: start_listening failed: {e}")
            raise

    def stop_listening(self):
        if not self.is_listening:
            return
        self.is_listening = False
        if self.current_stream:
            try:
                self.current_stream.stop()
                self.current_stream.close()
            except Exception:
                pass
            self.current_stream = None
        self.logger.info("AudioListener: stopped microphone stream")

    # ─── Audio Callback ───────────────────────────────────────────────────────

    def _audio_callback(self, indata, frames, cb_time, status):
        """
        sounddevice InputStream callback.
        Bug fix: parameter renamed from `time` to `cb_time` to avoid shadowing stdlib time.
        Bug fix: indata is already a numpy array — no need for frombuffer.
        """
        if status:
            self.logger.debug(f"AudioListener: stream status: {status}")
        try:
            # indata shape: (frames, channels) — take first channel, ensure writeable copy
            if _HAS_NUMPY:
                audio_data = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
            else:
                audio_data = list(indata)

            # Apply noise filter
            if self.noise_filtering_enabled and self.noise_filter and _HAS_NUMPY:
                try:
                    audio_data = self.noise_filter.process(audio_data)
                except Exception:
                    pass

            # VAD check
            is_speech = self._is_speech(audio_data)

            if is_speech or self.continuous_listening:
                self.audio_queue.put({
                    "audio": audio_data,
                    "is_speech": is_speech,
                    "timestamp": _time.time(),
                    "frames": frames,
                })
        except Exception as e:
            self.logger.error(f"AudioListener: _audio_callback error: {e}")

    def _is_speech(self, audio_data) -> bool:
        """Return True if audio appears to contain speech."""
        if self.vad and _HAS_VAD and _HAS_NUMPY:
            try:
                # VAD requires 16-bit PCM at specific frame sizes
                import numpy as np
                pcm = audio_data.astype(np.int16).tobytes()
                return self.vad.is_speech(pcm, self.sample_rate)
            except Exception:
                pass
        # Energy-based fallback
        if _HAS_NUMPY:
            import numpy as np
            rms = float(np.sqrt(np.mean(audio_data.astype(float) ** 2)))
        else:
            vals = [float(x) for x in audio_data]
            rms = (sum(x * x for x in vals) / max(1, len(vals))) ** 0.5
        return rms > self.silence_threshold

    # ─── Processing Thread ────────────────────────────────────────────────────

    def _process_audio(self, callback: Callable):
        while self.is_listening:
            try:
                audio_data = self.audio_queue.get(timeout=self.timeout)
                if audio_data["is_speech"]:
                    callback(audio_data["audio"], audio_data["timestamp"])
                self.audio_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"AudioListener: _process_audio error: {e}")

    # ─── Device Management ────────────────────────────────────────────────────

    def get_audio_devices(self) -> List[Dict[str, Any]]:
        if not _HAS_SD:
            return []
        try:
            devices = sd.query_devices()
            return [
                {
                    "index": i,
                    "name": d["name"],
                    "channels": d["max_input_channels"],
                    "sample_rate": d["default_samplerate"],
                }
                for i, d in enumerate(devices)
                if d["max_input_channels"] > 0
            ]
        except Exception as e:
            self.logger.error(f"AudioListener: get_audio_devices error: {e}")
            return []

    def set_device(self, device_index: int):
        was_listening = self.is_listening
        if was_listening:
            self.stop_listening()
        self.device_index = device_index
        self.logger.info(f"AudioListener: set device index to {device_index}")
        if was_listening:
            self.start_listening()

    def cleanup(self):
        self.stop_listening()
        if self.noise_filter:
            try:
                del self.noise_filter
            except Exception:
                pass