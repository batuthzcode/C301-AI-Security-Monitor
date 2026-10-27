## v0.1.2 / 2026-10-26 — Latency isolation experiment
- User reports ~3-second video delay despite working real feed.
- Added `--preview-only` mode to disable YOLO analysis and event recording while leaving live preview functional.
- Added separate, safe go2rtc hardware-transcoding `c301_h264_hw` test plan without changing working `c301`/`c301_h264` definitions.
- Added documentation at `docs/LATENCY_DIAGNOSTICS.md` and regression test for preview-only capture.
- Existing 3-second latency unresolved until hardware testing; does not touch Xiaomi firmware or user go2rtc private config.

# Changelog

## 0.1.0 — 2026-10-26 (prototype)

- Added Windows-first Tkinter GUI with RTSP, webcam and video-file source field.
- Added object class detection via YOLO11n for real input sources (integration not tested).
- Added synthetic demo with an obvious on-image SIMULATION banner.
- Added image-plane 2D object position display (not measured physical radar).
- Added local-only event JPG snapshots and structured JSONL logs.
- Added per-class event debouncing and optional PC spoken notification.
- Added security-minded go2rtc loopback-only sample config.
- Added GitHub-safe ignore rules, documentation, LinkedIn draft and demo screenshot.
- Ran five standard-library unit tests successfully.
- Ran local sample-frame snapshot test successfully.
- Ran offscreen Tkinter demo smoke test successfully under Linux Xvfb.
- Still pending: Windows install test, real Xiaomi C301 access, YOLO runtime benchmark.

### 2026-10-26 — Configuration diagnostics only (Milestone 006)
- Documented go2rtc stream configured but media handshake not yet successful.
- Recorded UDP timeout/RTSP 404 findings and safe next diagnostics.
- No change to application code or camera firmware.

### 2026-10-26 — Debug Fix #001 documentation
- Real C301 go2rtc video playback reported successful, without Administrator privileges.
- Documented user-observed YAML list-item workaround, backup/rollback and outstanding CS2 stability checks.
- Documented unresolved HEVC reference-frame and invalid QP warnings with diagnostics.
- Added `docs/TROUBLESHOOTING_C301.md` and Milestones 007–008 in the development log.
- **Documentation-only update:** no change to firmware or Python source.


### 2026-10-26 — Debug investigation #003 (docs only)
- Documented HEVC missing-reference and invalid-QP errors reproduced with RTSP TCP.
- Clarified camera→go2rtc CS2 versus go2rtc→Python RTSP transport.
- Added rollback-safe `subtype=sd` one-variable test plan; issue remains open.
- No Python code or firmware changes.

### 2026-10-26 — Diagnostic documentation: green RTSP video
- Confirmed camera video looks correct in go2rtc browser but all-green in Python/OpenCV.
- Added optional rollback-safe FFmpeg/H.264 sibling stream test and documentation.
- No change to Python source code or camera firmware.


### 2026-10-26 — H.264 bridging diagnostic, not a confirmed fix
- Logged Python GUI failure when opening `rtsp://127.0.0.1:8554/c301_h264`.
- Added local FFmpeg/go2rtc restream verification and recovery instructions.
- Source code unchanged; Xiaomi configuration remains private and unmodified in the distributed package.

### 2026-10-26 — Debug Fix #005: malformed go2rtc stream definition
- User reported `unsupported scheme` after attempting `c301_h264` FFmpeg stream.
- Explained leading hyphen as YAML list marker, and separated `c301` and `c301_h264` into distinct keys.
- Added safe, nonfunctional placeholder example and recovery steps to `docs/TROUBLESHOOTING_C301.md`.
- Correction awaits live test; Python source and camera firmware unchanged.

### 2026-10-26 — Debug Fix #005 confirmed in go2rtc
- User fixed quoting of YAML stream definitions; both `c301` and `c301_h264` now show live video in the go2rtc browser.
- Previous `unsupported scheme` error resolved in the reported go2rtc setup.
- Python/OpenCV H.264 live-view test remains pending; earlier HEVC green screen is not yet marked fixed.
- Documentation-only change; no code, firmware, or private configuration files included.

### 2026-10-26 — Milestone 016: CS2 recurrence (documentation only)
- Observed recurring buffer-full warnings in Xiaomi C301 `subtype=sd` feed.
- Corrected the status of prior YAML-formatting workaround: it fixes stream
  parsing, but the CS2 instability remains unresolved.
- Documented rollback-safe `subtype=auto` trial, 10-minute active verification,
  and relevant upstream open pull request. Python code unchanged.

### 2026-10-26 — Milestone 017: Repeated C301 CS2 buffer warnings
- Recorded fresh consecutive CS2 pop-buffer-full warnings, under `subtype=sd&audio=0`.
- Confirmed `subtype=auto` was not evidenced by the supplied log sample.
- Documented upstream issue #2057 and open proposed patch #2489 as possible root-cause evidence.
- Left camera firmware and Python source unchanged; no credentials included.

### 2026-10-26 — Milestone 018: local RTSP client disconnect diagnostic
- Documented Windows `WSAECONNABORTED` on loopback RTSP `127.0.0.1:8554` during H.264 restream testing.
- Distinguished the local RTSP session warning from the separate Xiaomi CS2 producer-buffer error.
- Added FFprobe/FFplay isolation steps and benign shutdown-vs-recurrent failure decision tree.
- No camera configuration, Python application source or firmware modified.

### v0.1.1 / 2026-10-26 — Low-latency preview experiment
- Confirmed real camera video appears in Windows AI Security Monitor; user reports delay.
- Split continuous RTSP frame capture from slower YOLO inference in separate threads.
- Keep only newest captured frame and render newest GUI frame per UI poll.
- Added `--imgsz` and `--inference-interval` controls; default inference size 416.
- Added latest-frame unit tests and rollback instructions.
- No Xiaomi firmware or go2rtc private configuration changes.
- End-to-end latency improvement awaits user testing on C301 hardware.
