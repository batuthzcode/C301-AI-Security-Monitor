# Milestone 036 — FFmpeg → OpenCV read-only frame fix

**Date:** 2026-10-27
**Affected file:** `latency_probe_ffmpeg.py` only
**Status:** Code-level fix verified on a synthetic frame; real camera latency still pending measurement.

## Symptom

On Windows, test aborted when OpenCV tried to draw the overlay:

```
cv2.error: ... in function 'putText'
img marked as output argument, but provided NumPy array marked as readonly
```

## Cause

The diagnostic reads raw bytes from FFmpeg's stdout and uses `np.frombuffer(raw, ...)`.
The input is an immutable Python `bytes` object, so the resulting NumPy array is
read-only. OpenCV `cv2.putText` mutates the frame in place, triggering the error.

## Fix

```python
# Before:
frame = np.frombuffer(raw, dtype=np.uint8).reshape(args.height,args.width,3)

# After:
frame = np.frombuffer(raw, dtype=np.uint8).reshape(args.height, args.width, 3).copy()
```

The `.copy()` creates a writable frame for drawing. This may add a small CPU/memory
copy cost and is **not by itself a latency optimization**. It just lets the
diagnostic run to completion.

## Validation

- Corrected script compiles.
- Synthetic immutable raw RGB frame -> writable NumPy copy -> `cv2.putText` works.
- No changes to go2rtc YAML, account credentials, firmware, or main AI Monitor modules.
- Real Xiaomi C301 latency test still pending.

## How to apply

Save the prior `latency_probe_ffmpeg.py` as a backup and replace only that file
with this corrected version. Re-run the original PowerShell command:

```powershell
.\.venv\Scripts\python.exe .\latency_probe_ffmpeg.py --source "rtsp://127.0.0.1:8554/c301_h264_hw"
```

## Rollback

Restore the previous `latency_probe_ffmpeg.py` file if necessary. Never commit
live `go2rtc.yaml`, Xiaomi tokens or private camera URLs to GitHub.
