"""Synthetic video source for testing without Xiaomi account or live camera."""
import math
import time
import cv2
import numpy as np
from .detection import Detection


def make_demo_frame(t: float, width: int = 960, height: int = 540):
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:] = (27, 22, 17)
    cv2.rectangle(image, (24, 20), (width - 24, height - 20), (58, 60, 58), 2)
    for x in range(100, width, 140):
        cv2.line(image, (x, 20), (x, height - 20), (37, 39, 38), 1)
    for y in range(90, height, 120):
        cv2.line(image, (24, y), (width - 24, y), (37, 39, 38), 1)
    cx = int(width / 2 + math.sin(t * 0.48) * width * 0.28)
    cy = int(height / 2 + math.cos(t * 0.35) * height * 0.19)
    cv2.circle(image, (cx, cy - 36), 21, (170, 180, 212), -1)
    cv2.rectangle(image, (cx - 30, cy - 12), (cx + 30, cy + 100), (165, 140, 110), -1)
    cv2.putText(image, "SIMULASYON / GERCEK KAMERA DEGIL", (44, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 220, 255), 2)
    obj = Detection("person", 0.99, cx - 31, cy - 59, cx + 31, cy + 102)
    return image, [obj]
