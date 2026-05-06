"""Tiny audio-cue helper for game state transitions.

Generates two short WAV files on first run (so we don't ship binaries
with the repo) and plays them through Qt's ``QSoundEffect`` when the
tracker enters / leaves a match.

Sounds:
* ``match_start`` \u2014 ascending two-note chime (A4 \u2192 E5).
* ``match_end``   \u2014 descending two-note chime (E5 \u2192 A4).

Sound playback can be disabled at runtime via :meth:`set_enabled`.
"""

from __future__ import annotations

import math
import os
import struct
import wave
from typing import Optional

from PySide6.QtCore import QObject, QStandardPaths, QUrl
from PySide6.QtMultimedia import QSoundEffect


_SAMPLE_RATE = 22_050
_AMPLITUDE = 0.32  # peak amplitude (0..1) before scaling to int16


def _write_chime(path: str, frequencies: tuple[float, ...], note_ms: int = 180) -> None:
    """Write a multi-note sine-wave chime to ``path`` as 16-bit mono WAV."""

    samples_per_note = int(_SAMPLE_RATE * note_ms / 1000)
    total = samples_per_note * len(frequencies)
    fade = max(1, int(samples_per_note * 0.08))

    frames = bytearray()
    peak = int(32_767 * _AMPLITUDE)
    for note_idx, freq in enumerate(frequencies):
        for i in range(samples_per_note):
            t = i / _SAMPLE_RATE
            base = math.sin(2 * math.pi * freq * t)
            # Soft attack / release so notes don't click.
            envelope = 1.0
            if i < fade:
                envelope = i / fade
            if i > samples_per_note - fade:
                envelope = max(0.0, (samples_per_note - i) / fade)
            sample = int(peak * envelope * base)
            frames.extend(struct.pack("<h", sample))
        del note_idx

    with wave.open(path, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(_SAMPLE_RATE)
        fh.writeframes(bytes(frames))


class SoundNotifier(QObject):
    """Plays short audio cues on match-start / match-end transitions."""

    _CHIMES = {
        "match_start": (440.0, 659.25),  # A4 \u2192 E5
        "match_end": (659.25, 440.0),    # E5 \u2192 A4
    }

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._enabled = True
        self._effects: dict[str, QSoundEffect] = {}
        self._last_state: Optional[str] = None
        self._ensure_files()

    # ------------------------------------------------------------ public
    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def is_enabled(self) -> bool:
        return self._enabled

    def play(self, name: str) -> None:
        if not self._enabled:
            return
        effect = self._effects.get(name)
        if effect is None:
            return
        # Restart playback even if the previous sound is still ringing
        # so consecutive matches don't get lost.
        if effect.isPlaying():
            effect.stop()
        effect.play()

    def update_state(self, state: str) -> None:
        """Play match-start / match-end based on a state transition."""

        new_state = (state or "").upper()
        previous = self._last_state
        self._last_state = new_state
        if previous is None or previous == new_state:
            return
        if new_state == "INGAME" and previous != "INGAME":
            self.play("match_start")
        elif previous == "INGAME" and new_state != "INGAME":
            self.play("match_end")

    # ------------------------------------------------------------ helpers
    def _ensure_files(self) -> None:
        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        if not base:
            base = os.path.join(os.path.expanduser("~"), ".vry")
        sound_dir = os.path.join(base, "sounds")
        os.makedirs(sound_dir, exist_ok=True)

        for name, freqs in self._CHIMES.items():
            path = os.path.join(sound_dir, f"{name}.wav")
            if not os.path.exists(path):
                try:
                    _write_chime(path, freqs)
                except OSError:
                    continue
            effect = QSoundEffect(self)
            effect.setSource(QUrl.fromLocalFile(path))
            effect.setVolume(0.55)
            self._effects[name] = effect
