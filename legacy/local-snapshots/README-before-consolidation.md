# C301 AI Security Monitor — Resizable latency preview (Milestone 037)

## What's fixed

The independent `latency_probe_ffmpeg.py` preview originally called `cv2.imshow` without creating a resizable named window. OpenCV's implicit window may use `WINDOW_AUTOSIZE`, so maximizing the Windows window did not scale up the camera image.

The updated script explicitly opens `cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO` and calls `cv2.resizeWindow`. OpenCV HighGUI can then resize the **display** while keeping the stream's 16:9 proportions. It also adds an `F` fullscreen toggle and keeps `Q` / `Esc` to close.

The existing `np.frombuffer(...).copy()` read-only-frame fix is retained. FFmpeg flags and decoded frame size are unchanged: the preview remains a low-buffer diagnostic, not a new AI Security Monitor release.

## How to apply on Windows

1. Close the existing latency preview. Keep go2rtc working.
2. Back up the existing `latency_probe_ffmpeg.py` file in your project folder.
3. Copy this folder's updated `latency_probe_ffmpeg.py` over the file alongside `main.py` in the original project. **Do not replace `main.py` or change `go2rtc.yaml`.**
4. Open PowerShell in your original project folder and run:

```powershell
.\.venv\Scripts\python.exe .\latency_probe_ffmpeg.py --source "rtsp://127.0.0.1:8554/c301_h264_hw"
```

Resize the preview by dragging its border or maximizing the window. Use `F` to switch to fullscreen and back; press `Q` or `Esc` to quit.

The preview input is still decoded at 960×540 before display. Enlarging it scales the **displayed pixels** and does not add additional camera detail or correct an upstream zoom/crop issue. The goal of this patch is window resizing only—not lower measured end-to-end latency.

## Validation and status

- Python source compiled successfully.
- Synthetic FFmpeg frame-to-OpenCV test passed using GUI mocks: resizable window created, writable frame displayed, fullscreen toggle called.
- Original `-fflags nobuffer`, `-flags low_delay`, `-max_delay 0`, TCP source and raw video pipeline preserved.
- **Real Windows resizing and latency still need user confirmation.**

## Security and rollback

- Restore your backed-up `latency_probe_ffmpeg.py` to revert.
- This package contains no `go2rtc.yaml`, tokens, passwords, Xiaomi URLs or device IDs.
- Do not commit your private camera configuration to GitHub.
