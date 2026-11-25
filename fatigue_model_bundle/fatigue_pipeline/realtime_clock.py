"""Resample observations onto the model's clock, independent of CPU throughput.

Use a short zero-order hold between observations. Camera outages become missing
data, so a long gap cannot manufacture a valid feature window.
"""
from dataclasses import replace
import math


class RealtimeClock:
    def __init__(self, fps, max_hold_seconds=2.0):
        self.fps = fps
        self.max_hold_seconds = max_hold_seconds
        self.origin = None
        self.next_index = 0
        self.previous = None
        self.previous_at = None

    def sample(self, observation, now):
        if self.origin is None:
            self.origin = now
        end_index = math.floor((now - self.origin) * self.fps + 1e-6)
        rows = []
        while self.next_index <= end_index:
            timestamp = self.origin + self.next_index / self.fps
            current = abs(timestamp - now) < 1e-6 or self.previous is None
            source = observation if current else self.previous
            row = replace(source, frame_idx=self.next_index,
                          timestamp_s=self.next_index / self.fps)
            if not current and timestamp - self.previous_at > self.max_hold_seconds:
                row = replace(row, face_detected=False, p_eye_left_closed=None,
                              p_eye_right_closed=None, p_mouth_open=None, keypoints=None)
            rows.append(row)
            self.next_index += 1
        self.previous, self.previous_at = observation, now
        return rows
