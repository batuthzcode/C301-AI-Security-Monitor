# Development log / geliştirme günlüğü

This file records *project development milestones*, not continuous home video.
Sensitive camera video and account details stay outside Git history.

## 2026-10-26 — Milestone 001: architecture and scope

- Owner goal: Xiaomi Smart Camera C301, custom security features while Windows PC is on.
- Camera model identifier: `mxiang.camera.c301` listed as known in go2rtc.
- go2rtc Xiaomi source uses Xiaomi Home login and local camera connection; internet
  is needed to obtain streaming encryption keys.
- Camera-side firmware modification intentionally excluded from initial scope.
- First implementation: tkinter UI, OpenCV video reading, Ultralytics YOLO11n
  detector, local event snapshots/JSONL, visual 2D tracking, PC-only speech,
  synthetic demo.
- Privacy/security: sensitive go2rtc configs, tokens, images, model weights ignored
  by Git; external access disabled in sample config via loopback binds.
- Important limitation: radar is a 2D visualization only; no distance measurement.
- Integration, frame-rate, model download and physical C301 access NOT validated.

### External references
- https://go2rtc.org/internal/xiaomi/
- https://github.com/AlexxIT/go2rtc/issues/1982
- https://go2rtc.org/internal/rtsp/
- https://docs.ultralytics.com/modes/predict/
- https://www.mi.com/tr/product/xiaomi-smart-camera-c301/specs/

## Next session template

Date:
Goal:
Changes made:
Files changed:
Commands/tests executed:
Results (pass/fail):
Screenshots (redacted):
Blockers:
Next step:

## 2026-10-26 — Milestone 002: local prototype checks

- Created initial Python source modules, sample config, security `.gitignore`,
  Windows startup scripts, GitHub workflow, dev journal helper, and documentation.
- Unit test suite `python -m unittest discover -s tests -v`: **5/5 PASS**.
- `python -m compileall -q main.py c301_monitor tests`: **PASS**.
- Synthetic image produced: **960×540, single synthetic object**.
- Local snapshot + JSONL persistence check: **PASS** (temporary local path).
- Tkinter GUI smoke check under **Linux Xvfb**, connected in DEMO mode for ~2s:
  **PASS**, 1 visible synthetic object, 1 logged synthetic event.
- Captured public-safe simulated dashboard image at `assets/demo-dashboard.png`.
- Fixed OpenCV font rendering for Turkish characters and right-panel clipping.
- **Not yet tested:** actual camera, Windows environment, go2rtc credentials,
  real object inference, physical camera speaker, real-time FPS.
