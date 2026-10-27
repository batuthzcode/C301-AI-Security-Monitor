"""Independent low-buffer FFmpeg -> Python/OpenCV preview diagnostic.

This leaves go2rtc.yaml, firmware, and the main AI Monitor application unchanged.
It is a visual comparison test, NOT an automated end-to-end latency meter.
"""
import argparse
import shutil
import subprocess
import sys
import time


def ffmpeg_command(executable: str, url: str, width: int, height: int) -> list[str]:
    return [
        executable, "-hide_banner", "-loglevel", "error", "-nostdin",
        "-rtsp_transport", "tcp", "-fflags", "nobuffer",
        "-flags", "low_delay", "-max_delay", "0",
        "-i", url, "-map", "0:v:0", "-an", "-sn", "-dn",
        "-vf", f"scale={width}:{height}:flags=fast_bilinear",
        "-pix_fmt", "bgr24", "-f", "rawvideo", "-fps_mode", "passthrough", "pipe:1",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="C301 isolated FFmpeg-to-Python latency comparison")
    parser.add_argument("--source", default="rtsp://127.0.0.1:8554/c301_h264_hw")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    args = parser.parse_args()
    if args.width <= 0 or args.height <= 0:
        parser.error("Width and height must be positive")
    exe = shutil.which("ffmpeg")
    if not exe:
        print("FFmpeg bulunamadı. Yeni PowerShell açıp 'ffmpeg -version' deneyin.", file=sys.stderr)
        return 1
    import cv2
    import numpy as np
    cmd = ffmpeg_command(exe, args.source, args.width, args.height)
    print("Düşük tamponlu FFmpeg → OpenCV testi başlatılıyor.")
    print("Pencereyi sürükleyerek büyütün; F: tam ekran, Q / ESC: çıkış.")
    print("Bu test YOLO ve Tkinter içermez; gecikmeyi elle karşılaştırın.")
    # FFmpeg diagnostics are short; do not hold stderr open without a consumer.
    # DEVNULL avoids a filled stderr pipe stalling the video process.
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               bufsize=args.width * args.height * 3)
    frame_size = args.width * args.height * 3
    shown = 0
    started = time.monotonic()
    window_name = "C301 latency probe (F: fullscreen / Q: quit)"
    # OpenCV's implicit imshow window is WINDOW_AUTOSIZE (fixed image size).
    # A resizable HighGUI window scales displayed pixels to fill the client area
    # while respecting the 16:9 input aspect ratio. Decoding stays 960x540 by
    # default; maximising the window does NOT add extra FFmpeg processing.
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    cv2.resizeWindow(window_name, 960, 540)
    fullscreen = False
    try:
        while True:
            raw = process.stdout.read(frame_size)
            if len(raw) != frame_size:
                print("Akış sona erdi veya FFmpeg hata verdi. go2rtc akışını kontrol edin.")
                return 2
            frame = np.frombuffer(raw, dtype=np.uint8).reshape(args.height, args.width, 3).copy()
            # The indicator is locally generated; it is NOT the camera's capture time.
            cv2.putText(frame, "FFmpeg pipe / NO YOLO", (12,28),
                        cv2.FONT_HERSHEY_SIMPLEX, .7, (255,255,255), 2)
            cv2.imshow(window_name, frame)
            shown += 1
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):
                return 0
            if key in (ord('f'), ord('F')):
                fullscreen = not fullscreen
                cv2.setWindowProperty(
                    window_name, cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_FULLSCREEN if fullscreen else cv2.WINDOW_NORMAL,
                )
            if shown % 150 == 0:
                elapsed=max(time.monotonic()-started,0.001)
                print(f"Shown frames: {shown}; avg display FPS: {shown/elapsed:.1f} (not end-to-end latency)")
    except KeyboardInterrupt:
        return 0
    finally:
        process.terminate()
        try: process.wait(timeout=2)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=2)
        if process.stdout: process.stdout.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    raise SystemExit(main())
