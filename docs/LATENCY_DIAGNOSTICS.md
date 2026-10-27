# Xiaomi C301 — three-second end-to-end latency investigation

**Date:** 2026-10-26  
**Status:** User verified video appears in Python AI Security Monitor v0.1.1,
but reported approximately **3 seconds** of motion-to-screen delay. This is a
manual estimate, not a benchmark measurement. The cause is not yet isolated.

## Preserve working configuration

Do not edit `c301` or `c301_h264` for these tests. Save the known-good private
`go2rtc.yaml` in an offline private location. Never upload any true `xiaomi://`
source URL, account token, device ID, or unredacted YAML to GitHub.

## Test 1 — Is YOLO the bottleneck?

Open PowerShell in the previously installed project folder (containing `.venv`).
Copy only `c301_monitor/worker.py` and `c301_monitor/gui.py` from v0.1.2 into
that folder **after backing up** the v0.1.1 counterparts. The `--preview-only`
flag skips YOLO model loading, detections, alarm speech and event recording;
only the camera is displayed.

```powershell
$env:OPENCV_FFMPEG_CAPTURE_OPTIONS = 'rtsp_transport;tcp'
.\.venv\Scripts\python.exe main.py --source 'rtsp://127.0.0.1:8554/c301_h264' --preview-only
```

With the camera on the same scene, quickly wave a hand and compare the delay
against v0.1.1 normal mode. If **both** are ~3s behind, YOLO isn't the main
bottleneck. If preview-only is significantly faster, profile detection, CPU
load, GPU inference, UI rendering and shared capture resources.

Stop this instance **before** running normal mode. To re-enable detection,
launch without `--preview-only`.

## Test 2 — Compare go2rtc original and transcoded feeds

Open the streams **one at a time** and compare visually:

- go2rtc `c301` original Xiaomi stream
- go2rtc `c301_h264` transcoded stream
- Windows Python `--preview-only` consuming `c301_h264`

Avoid watching all 3 feeds simultaneously while judging latency, as the
extra active consumers and encoders can affect performance. Note if delay
appears already in `c301`, only after transcoding, or only in Python.

Optional FFplay comparison (installed as part of Gyan.FFmpeg):

```powershell
ffplay -fflags nobuffer -flags low_delay -framedrop -rtsp_transport tcp -i 'rtsp://127.0.0.1:8554/c301_h264'
```

This does not change go2rtc or the camera. If FFplay and Python both have
about the same lag, optimize the streaming/transcoding side first.

## Test 3 — Optional GPU-transcoding *alternative stream*

On a PC with working supported GPU hardware encoding, go2rtc's FFmpeg
`#hardware` modifier can accelerate H.265→H.264 conversion. Do not replace
the currently working `c301_h264`: add a **third** entry under the existing
`streams:` at the same indentation level. Use correct YAML syntax, quotes,
and the literal `-` list item marker:

```yaml
  c301_h264_hw:
    - "ffmpeg:c301#video=h264#hardware"
```

After saving and restarting go2rtc, confirm the new stream works *before*
asking Python to open `rtsp://127.0.0.1:8554/c301_h264_hw`. Some GPU/driver
combinations do not support this path and may fail to start; in that case,
remove only this additional stream and leave the working ones unchanged.
A GPU-enabled source does not guarantee sub-second latency and may still
experience the upstream Xiaomi CS2 buffer issue.

Go2rtc's documentation says video transcoding can require hardware
acceleration and that it is not enabled by default. Check supported devices
on the go2rtc **Add → Hardware** UI before using this setting.

## Results to record (in DEVLOG)

| Test | Delay (manually estimated) | Stable? | Notes |
|---|---:|---|---|
| go2rtc c301 | TBD | TBD | Original Xiaomi stream |
| go2rtc c301_h264 | TBD | TBD | Software transcoding |
| Python preview-only | TBD | TBD | YOLO off, RTSP TCP |
| Python normal v0.1.1 | ~3s (user report) | Yes (video visible) | YOLO enabled |
| optional GPU stream | TBD | TBD | New isolated stream |

**Existing upstream issue:** `miss: read media: cs2: pop buffer is full` is a
separate camera producer warning. This release does not claim to fix it.

## References

- https://go2rtc.org/internal/ffmpeg/
- https://go2rtc.org/internal/ffmpeg/hardware/
- https://github.com/AlexxIT/go2rtc/issues/2057
