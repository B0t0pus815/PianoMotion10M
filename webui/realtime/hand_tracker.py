"""MediaPipe Hands wrapper using legacy solutions.hands API (mediapipe 0.10.14).

Per frame, returns {left, right} → HandPose with 21 landmarks in pixel coords.
Handedness comes from the image-frame perspective; pass mirror=True for a
user-facing webcam so 'left' refers to the user's actual left hand.

Note: MediaPipe is trained on real-photo hands. MANO-rendered hands (e.g. the
biomech v4 reference video) will only be detected sparsely — that's expected,
and the comparator just emits "no hand" results for missing detections.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np

TIP_INDICES = {'thumb': 4, 'index': 8, 'middle': 12, 'ring': 16, 'pinky': 20}
TIP_ORDER = ['thumb', 'index', 'middle', 'ring', 'pinky']
WRIST_IDX = 0


@dataclass
class HandPose:
    landmarks: np.ndarray
    handedness: str
    score: float

    @property
    def fingertips(self) -> np.ndarray:
        return self.landmarks[[TIP_INDICES[f] for f in TIP_ORDER]]

    @property
    def wrist(self) -> np.ndarray:
        return self.landmarks[WRIST_IDX]


class HandTracker:
    def __init__(self,
                 mirror: bool = False,
                 min_detection_confidence: float = 0.3,
                 min_tracking_confidence: float = 0.3):
        self.mirror = mirror
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def process(self, frame_bgr: np.ndarray, timestamp_ms: int = 0) -> dict[str, HandPose]:
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self.hands.process(rgb)

        out: dict[str, HandPose] = {}
        if not result.multi_hand_landmarks:
            return out
        for lms, hd in zip(result.multi_hand_landmarks, result.multi_handedness):
            arr = np.array(
                [[lm.x * w, lm.y * h, lm.z * w] for lm in lms.landmark],
                dtype=np.float32,
            )
            label = hd.classification[0].label.lower()
            if self.mirror:
                label = 'right' if label == 'left' else 'left'
            out[label] = HandPose(
                landmarks=arr,
                handedness=label,
                score=hd.classification[0].score,
            )
        return out

    def close(self):
        self.hands.close()
