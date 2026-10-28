# Milestone 037 — Resizable low-latency preview

**Reported:** 27 October 2026
**Component:** `latency_probe_ffmpeg.py`
**Type:** UI / OpenCV HighGUI fix
**Status:** Code test passed; user confirmation pending

## User report

The read-only NumPy frame issue was resolved, and the standalone FFmpeg → OpenCV test could display camera frames. However, when the user made the preview window larger, the video image did not increase in size.

## Root cause

The probe used `cv2.imshow()` without first calling `cv2.namedWindow(..., cv2.WINDOW_NORMAL)`. OpenCV can create a fixed-size `WINDOW_AUTOSIZE` window implicitly.

## Fix

```python
window_name = "C301 latency probe (F: fullscreen / Q: quit)"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
cv2.resizeWindow(window_name, 960, 540)
# Within the existing frame loop:
cv2.imshow(window_name, frame)
```

In addition, the `F` key toggles `cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, ...)`. Existing `Q`, `Esc`, and `.copy()` logic are preserved. The frame decoder output stays 960×540 to avoid increasing the FFmpeg raw-pipe bandwidth merely to enlarge the window.

## Validation

- Python compile check passed.
- Synthetic two-frame GUI-mock test confirmed a resizable window was requested, an OpenCV-writable frame was shown, and `F` toggled fullscreen.
- Live Windows behavior and end-to-end latency pending user verification.

## Rollback

Restore backed-up `latency_probe_ffmpeg.py`. No camera firmware, `go2rtc.yaml`, AI Monitor worker/GUI, tokens, or camera account data changed.

## Reference

- https://docs.opencv.org/4.13.0/d7/dfc/group__highgui.html
