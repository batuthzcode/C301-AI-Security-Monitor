# v0.1.1 — Windows setup and latency verification

## Safest update path (keep the installed venv)

1. Close AI Security Monitor. Keep `go2rtc.exe` running.
2. Back up the existing `c301_monitor/worker.py` and `c301_monitor/gui.py`
   as `.bak` files **outside any Git repository**.
3. Unzip the release. Copy these 3 files from its `c301_monitor` folder
   into your **original** project folder's `c301_monitor` directory:
   `worker.py`, `gui.py`, `video.py`.
4. Open PowerShell in the **original** project folder (where `.venv`,
   `main.py` and `requirements.txt` already exist).
5. Run:

   ```powershell
   $env:OPENCV_FFMPEG_CAPTURE_OPTIONS = 'rtsp_transport;tcp'
   .\.venv\Scripts\python.exe main.py --source 'rtsp://127.0.0.1:8554/c301_h264' --imgsz 416 --inference-interval 0.45
   ```

6. Compare motion seen in Xiaomi Home/go2rtc with the Python dashboard.
   Example: wave a hand and notice whether the view catches up quickly.
   Do not expect identical 0ms delay, because H.265 to H.264 conversion adds work.
7. If needed, try `--imgsz 320 --inference-interval 0.7`.
8. To roll back, stop AI Security Monitor and put the original `worker.py`
   and `gui.py` back from the `.bak` copies; remove the new `video.py`.

## Root cause hypothesis and validation

Original code ran `cap.read()` and a blocking `model.predict()` in one loop;
model processing could allow frames to queue. v0.1.1 has a continuously
reading background thread and overwrites older frames. The GUI renders only
the newest available queued frame per poll. A simulated slow-inference unit
check verifies reading continues while inference is blocked.

- No Xiaomi account token, real IP, or private URL is bundled here.
- No modifications to Xiaomi firmware or user's live go2rtc YAML.
- This is experimental until tested end-to-end on the actual C301.
- Do not claim the CS2 producer buffer bug or upstream issue is fixed.
