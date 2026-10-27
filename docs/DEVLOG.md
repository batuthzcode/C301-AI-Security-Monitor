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

## 2026-10-26 — Milestone 003: user's Windows demo verification

- User installed Python dependencies successfully on Windows using the project's `.venv`.
- User launched `python main.py --demo` and supplied a screenshot showing the
  `C301 / AI SECURITY MONITOR` v0.1.0 GUI running on Windows.
- Screenshot evidence is stored at `assets/windows-demo-2026-10-26.png`
  (taskbar cropped). Screen displayed clearly marked **SIMULASYON / GERCEK KAMERA DEGIL**.
- Visible in screenshot: simulated person bounding box, simulated tracking dot,
  event-history row for `Kisi | demo`, and checked PC audible-alert option.
- What this verifies: GUI/demo rendering and that a simulated event appeared on screen.
- What this DOES NOT verify: actual C301 video connection, YOLO inference on live
  frames, persistence of event files, audible speech output, or camera speaker audio.
- Upcoming: use separate go2rtc installation, Xiaomi login, and `c301` RTSP stream.
- Camera firmware remains unmodified; v0.1.0 Python source code unchanged.


## 2026-10-26 — Milestone 004: Xiaomi account authentication

- User opened the local go2rtc `Add > Xiaomi` screen and selected the Europe region.
- The initial Xiaomi authentication attempt produced error `70014` (verification code rejected).
- User subsequently reported successfully logging into the Xiaomi account.
- Next action: choose the authenticated account, select Europe, and click **load devices**.
- Actual device listing, C301 stream setup, and live video are **not yet confirmed**.
- Sensitive details such as account email, password, verification codes, device token, and `xiaomi://` URLs are intentionally excluded from this log.
- **Code unchanged.** No firmware modification or camera-side writes made by our project.

## 2026-10-26 — Milestone 005: C301 discovered in Singapore region

- User selected the Singapore server in the local go2rtc Xiaomi device loader.
- User shared an image of the device listing confirming **Xiaomi Smart Camera C301** appears with a LAN IP and a `xiaomi://...` source URL.
- Region finding: **Singapore** is confirmed as the working *device listing region* for this user's account; Europe did not list the camera.
- Security: real email address, Xiaomi account ID, device MAC, LAN address,
  encryption credentials and the full `xiaomi://` URL are intentionally omitted
  from this GitHub/LinkedIn-safe development journal.
- This confirms **discovery only**. Stream creation, playback, Python live feed,
  YOLO detection and camera-speaker audio are **not yet verified**.
- Next steps: locally add `c301` stream using the full device URL, verify it
  in go2rtc Streams, then run Python with the local RTSP endpoint.
- **Source code unchanged; camera firmware unchanged.**

## 2026-10-26 — Milestone 006: stream registered; upstream video still unavailable

- User opened go2rtc stream info and provided a public screenshot of its JSON status.
- The `c301` stream has a Xiaomi source listed under `producers` with camera model
  `mxiang.camera.c301`; `consumers` was `null` at capture time.
- This confirms **stream configuration only**, not an established live producer or
  successful transfer of camera video frames.
- Earlier reports: Xiaomi stream timeout (`read udp ... i/o timeout`), downstream
  RTSP `DESCRIBE 404 Not Found`, and app could not open video source.
- Previous ICMP check showed four replies and zero lost packets, indicating basic
  LAN reachability, but **not** UDP media handshake success.
- Candidate causes include host UDP firewall rules, CS2 handshake behavior,
  and go2rtc version compatibility. Actual root cause is **unconfirmed**.
- Recommended next diagnostics (no camera firmware or Python code changes):
  verify Windows network is trusted/private, add a narrowly scoped inbound UDP
  allow rule for the go2rtc executable from the camera LAN IP, retry live RTSP,
  then examine redacted go2rtc log errors. Do not globally disable firewall.
- Upstream reports with similar symptoms:
  https://github.com/AlexxIT/go2rtc/issues/2424
  https://github.com/AlexxIT/go2rtc/issues/2048
  https://github.com/AlexxIT/go2rtc/issues/2603
- Security: previous go2rtc account token and a device-details screenshot were
  shared. Rotate/revoke the exposed session where possible; never add credentials,
  full Xiaomi stream URL, account ID, or unredacted images to the repository.
- **Python source code unchanged. Original C301 firmware unchanged.**

## 2026-10-26 — Milestone 007: first real C301 video and permission tests

- User reported **real live C301 video visible via go2rtc**.
- Running go2rtc as Administrator was subsequently tested and found **unnecessary**.
- Public -> Private network profile did not independently clear a prior UDP handshake timeout; a narrow go2rtc UDP firewall exception and retries were also tried. Root cause not isolated.
- Python source and original camera firmware were not changed.

## 2026-10-26 — Milestone 008: DEBUG FIX #001 (observed) / HEVC diagnostics (open)

- Before: `cs2: pop buffer is full` in the go2rtc logs every ~11–12 seconds during streaming.
- User restored a working `go2rtc.yaml` backup and configured `c301` as a list item using a leading `-` (no quotes); `subtype=auto` and `audio=0` were also reported.
- User reported **no further CS2 warning at the initial observation**. Causality and sustained stability have not yet been verified; document as a workaround, not a proven upstream fix.
- Afterwards FFmpeg/OpenCV HEVC decoder warnings were observed: `Could not find ref with POC 8`, `cu_qp_delta -59 ... outside the valid range`.
- The HEVC issue remains **OPEN**, potentially involving damaged or missing compressed video data.
- Configuration and stream URL remain entirely local and private; the publication-safe structure is documented in `docs/TROUBLESHOOTING_C301.md`.
- No Python code change and no camera-firmware change.


## 2026-10-26 — Milestone 009: HEVC warnings persist with RTSP TCP

- Python/OpenCV RTSP consumer was invoked with `OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp`.
- User reported `Could not find ref with POC 32` and `cu_qp_delta 29 ... outside ... [-26,25]`.
- Source of malformed/missing HEVC frames not yet isolated; TCP only affects the client-to-go2rtc leg, not the separate Xiaomi CS2 feed.
- Documented one-variable diagnostic plan and optional rollback-safe `subtype=sd` stream test.
- Python code and camera firmware unchanged. See `docs/TROUBLESHOOTING_C301.md`.


### 2026-10-26 — Milestone 012: Green OpenCV image, browser stream healthy

- go2rtc browser playback confirmed normal by the user; Windows Python RTSP stream
  displays entirely green frames.
- HEVC decoding errors persisted after RTSP-over-TCP selection.
- Next reversible diagnostic: separate H.264 transcoded stream `c301_h264`.
- Underlying source `c301`, firmware and Python application code unchanged.
- See `docs/TROUBLESHOOTING_C301.md` Debug Investigation #004.


## 2026-10-26 — Milestone 013 / Debug Investigation #004

- New user screenshot shows the RTSP input `c301_h264` in the Windows GUI, status `Bağlantı kapalı` and `HATA: Görüntü kaynağı açılamadı`.
- The original `c301` feed remains confirmed working in the go2rtc browser; only the Python application and new H.264 variant remain unverified.
- Root cause of the failed H.264 stream is unknown; next checks are whether go2rtc registers and opens `c301_h264`, and whether it can launch a local FFmpeg binary.
- Existing firmware and Python code preserved, no credential URLs documented.

## 2026-10-26 — Milestone 014: H.264 stream YAML parsing error
- Browser preview showed `mse: streams: streams: unsupported scheme` and included concatenated Xiaomi + FFmpeg entries in the supposed URL.
- Diagnosis: malformed YAML separation of `c301` and `c301_h264`; a hyphen list item must be separated from the URL by a space.
- Proposed safe structure shown in `TROUBLESHOOTING_C301.md`; not yet confirmed by user test.
- Keep camera firmware, source code, Xiaomi credentials and tokens untouched.

## 2026-10-26 — Milestone 015: quoted YAML streams — go2rtc browser success

- User reported that inserting the missing quotation marks in the private go2rtc YAML resolved the configuration parser error.
- Both separate sources, `c301` and `c301_h264`, are now displaying real video in go2rtc.
- This verifies the stream definitions and browser playback, **not yet the Python dashboard**.
- Next step: Windows application use `rtsp://127.0.0.1:8554/c301_h264`; verify no green frames and ongoing stream stability.
- No camera firmware, application source, account token, device ID or private camera URL changed or published.

## 2026-10-26 — Milestone 016: Xiaomi C301 CS2 warning recurred

- While both go2rtc streams `c301` and `c301_h264` had been reported to display
  video, two subsequent CS2 `pop buffer is full` warnings reappeared, roughly
  15 seconds apart, with the private Xiaomi source configured as `subtype=sd&audio=0`.
- Reclassified the earlier YAML list/quoting change as a configuration parser
  correction only: it is **not** confirmed to fix the underlying CS2 issue.
- Proposed one-variable `subtype=sd` → `subtype=auto` trial and 10-minute
  active-view/log stability measurement; this trial is **not yet performed**.
- Linked specific model issue #2057 and unmerged PR #2489 for future research.
- No Xiaomi credentials, private connection URL, IP or device ID in GitHub files.
- No Python source or camera firmware changed.

## 2026-10-26 — Milestone 017: CS2 buffer warning repeated (user observed)

- User supplied go2rtc log entries at 17:57–17:59 showing repeated `miss: read media: cs2: pop buffer is full` warnings while using Xiaomi C301 (`mxiang.camera.c301`).
- The active source URL in **all supplied lines** ends in `subtype=sd&audio=0`, so there is no evidence in these logs that the proposed `subtype=auto` experiment was active. The logs could predate a later configuration change.
- The warning repeated at intervals of approximately 15 seconds in several consecutive entries. This confirms a continuing problem with the Xiaomi go2rtc source; the H.264 child stream does not itself correct it.
- go2rtc issue [#2057](https://github.com/AlexxIT/go2rtc/issues/2057) reproduces the same warning on the **exact C301 model**.
- Unmerged upstream PR [#2489](https://github.com/AlexxIT/go2rtc/pull/2489) proposes continuously reading Xiaomi CS2 command/control packets to prevent a full command-channel pop buffer. The PR was **open on 2026-10-26**, so it must not be described as included in a released build without verification.
- No camera firmware or Python source code was changed in this documentation checkpoint.
- Next: inspect actual go2rtc `streams.c301` after a complete restart, then compare with fresh log lines while one stream is actively viewed. Keep existing working config/backup; do not publicly disclose credentials, full `xiaomi://` URL, LAN IP, or device ID.

## 2026-10-26 — Milestone 018: localhost RTSP client abort during H.264 trial

- User supplied go2rtc warning at **18:01:16.837** from `internal/rtsp/rtsp.go:262`: `read tcp 127.0.0.1:8554->127.0.0.1:<ephemeral-port>: wsarecv: An established connection was aborted by the software in your host machine.`
- This is the Windows `WSAECONNABORTED` (Winsock 10053) connection-aborted condition, **not** the Xiaomi `cs2: pop buffer is full` source warning. Both endpoints are on loopback, so the RTSP server and its client are on the same Windows PC.
- Possible explanations include a normal client/player closing, a Python process terminating, FFmpeg transcoder restarting, or a local network/protocol abort. **One warning is insufficient to determine which.**
- go2rtc upstream issue [#1372](https://github.com/AlexxIT/go2rtc/issues/1372) contains this exact Windows message in an FFmpeg RTSP-restream workflow. This is analogous behavior, not proof of the user's cause.
- Keep working `go2rtc.yaml` and camera firmware untouched. Distinguish a single warning at viewer shutdown from persistent warnings while video plays. Then independently probe `c301_h264` via FFprobe/FFplay, comparing the Windows Python dashboard and go2rtc browser.
- No private source URLs, tokens, device ID or IP addresses included in these documents. No changes to Python source code or firmware.
- **Status:** diagnosis open; not yet a confirmed fix.

## 2026-10-26 — Milestone 019: Live RTSP confirmed; delay investigation

- User confirmed both go2rtc streams and successful live video in Windows AI Security Monitor.
- Reported delay in the Python dashboard despite working video.
- Root cause candidate from code review: `VideoCapture.read` and CPU-bound YOLO inference used the same thread, permitting stale RTSP frames to accumulate. Tkinter also painted each queued frame.
- Implemented a **test build** with a separate continuously draining capture thread, a one-frame overwrite buffer, independent prediction loop, and newest-only GUI rendering.
- Camera and `go2rtc.yaml` remain untouched.
- Tests are software-only; real camera latency benefit remains unverified.
- Existing v0.1.0 backup remains the rollback point.
- Regression test verified that capture keeps reading while simulated YOLO inference sleeps; **8 tests passed**.
