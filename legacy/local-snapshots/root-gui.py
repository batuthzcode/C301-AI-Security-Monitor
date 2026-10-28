"""Dark local-first Windows dashboard for Xiaomi C301 proof-of-concept."""
import argparse
import queue
import tkinter as tk
from pathlib import Path
from datetime import datetime
from tkinter import messagebox, ttk

import cv2
from PIL import Image, ImageTk

from .detection import Detection
from .records import EventRecorder
from .speech import PCSpeaker
from .worker import CameraWorker

BG = "#101820"
PANEL = "#192532"
FG = "#e8f1fa"
MUTED = "#a5b8cb"
CYAN = "#41d9da"
GREEN = "#6ee7a8"


def friendly_name(label: str) -> str:
    return {
        "person": "Kişi", "cell phone": "Telefon", "laptop": "Dizüstü bilgisayar",
        "backpack": "Sırt çantası", "chair": "Sandalye", "cat": "Kedi",
        "dog": "Köpek", "book": "Kitap", "car": "Araba", "tv": "Televizyon",
    }.get(label, label)


class MonitorApp:
    def __init__(self, root: tk.Tk, options):
        self.root = root
        self.options = options
        self.recorder = EventRecorder(Path(options.data_dir))
        self.messages: queue.Queue = queue.Queue(maxsize=20)
        self.worker: CameraWorker | None = None
        self.speaker = PCSpeaker()
        self.running = False
        self.last_photo = None
        self.last_detections: list[Detection] = []
        self.frame_size = (960, 540)
        self.event_count = 0

        root.title("C301 AI Security Monitor  |  v0.1.3")
        root.configure(bg=BG)
        root.geometry("1240x800")
        root.minsize(990, 680)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        root.after(60, self._poll)
        if options.demo:
            root.after(150, lambda: self.start(demo=True))

    def _build(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        heading = tk.Frame(self.root, bg=BG)
        heading.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 2))
        tk.Label(heading, text="C301  /  AI SECURITY MONITOR", fg=FG, bg=BG,
                 font=("Segoe UI", 20, "bold")).pack(side="left")
        tk.Label(heading, text="LOCAL-FIRST  ·  v0.1.3", fg=CYAN, bg=BG,
                 font=("Consolas", 10, "bold")).pack(side="right")

        controls = tk.Frame(self.root, bg=BG)
        controls.grid(row=1, column=0, sticky="ew", padx=24, pady=(8, 12))
        tk.Label(controls, text="Kaynak", fg=MUTED, bg=BG).pack(side="left", padx=(0, 8))
        self.source_var = tk.StringVar(value=self.options.source)
        self.source = tk.Entry(controls, textvariable=self.source_var, width=37,
                               bg="#273749", fg=FG, insertbackground=FG,
                               relief="flat", font=("Consolas", 10))
        self.source.pack(side="left", padx=(0, 10), ipady=7, fill="x", expand=True)
        self.start_button = tk.Button(controls, text="▶ Başlat", command=self.start,
                                      bg="#096d72", fg="white", relief="flat", padx=14, pady=6)
        self.start_button.pack(side="left", padx=4)
        self.stop_button = tk.Button(controls, text="■ Durdur", command=self.stop,
                                     bg="#304357", fg="white", relief="flat", padx=12, pady=6)
        self.stop_button.pack(side="left", padx=4)
        tk.Button(controls, text="● DEMO", command=lambda: self.start(demo=True),
                  bg="#304357", fg=FG, relief="flat", padx=12, pady=6).pack(side="left", padx=4)
        tk.Button(controls, text="📷 Kaydet", command=self.snapshot,
                  bg="#304357", fg=FG, relief="flat", padx=10, pady=6).pack(side="left", padx=4)

        main = tk.Frame(self.root, bg=BG)
        main.grid(row=2, column=0, sticky="nsew", padx=24)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = tk.Frame(main, bg=PANEL, padx=13, pady=13)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)
        tk.Label(left, text="KAMERA GÖRÜNTÜSÜ", fg=MUTED, bg=PANEL,
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 9))
        self.canvas = tk.Canvas(left, bg="#0c141a", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _e: self._paint_video())
        self.placeholder = self.canvas.create_text(300, 220, text="Kameraya bağlan veya DEMO modunu aç",
                                                   fill=MUTED, font=("Segoe UI", 13))
        self.video_item = self.canvas.create_image(0, 0, anchor="center")
        foot = tk.Frame(left, bg=PANEL)
        foot.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.status_var = tk.StringVar(value="Bağlantı bekleniyor")
        tk.Label(foot, textvariable=self.status_var, fg=GREEN, bg=PANEL,
                 font=("Segoe UI", 10)).pack(side="left")
        self.count_var = tk.StringVar(value="0 nesne")
        tk.Label(foot, textvariable=self.count_var, fg=CYAN, bg=PANEL).pack(side="right")

        right = tk.Frame(main, bg=PANEL, padx=16, pady=16)
        right.grid(row=0, column=1, sticky="nsew")
        tk.Label(right, text="GÖRSEL TAKİP", fg=MUTED, bg=PANEL,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(right, text="Görüntü koordinatlarıdır; mesafe ölçmez.",
                 fg=MUTED, bg=PANEL, font=("Segoe UI", 8), wraplength=270).pack(anchor="w", pady=(3, 8))
        self.radar = tk.Canvas(right, height=250, bg="#111f2d", highlightthickness=0)
        self.radar.pack(fill="x", expand=False)
        self.radar.bind("<Configure>", lambda _e: self._draw_radar())
        self.voice_var = tk.BooleanVar(value=not self.options.mute)
        tk.Checkbutton(right, text="PC'den kişi algılama sesli uyarısı", variable=self.voice_var,
                       fg=FG, bg=PANEL, selectcolor="#304357", activebackground=PANEL,
                       activeforeground=FG).pack(anchor="w", pady=(16, 5))
        self.only_people = tk.BooleanVar(value=self.options.person_only)
        tk.Checkbutton(right, text="Sadece kişileri göster", variable=self.only_people,
                       fg=FG, bg=PANEL, selectcolor="#304357", activebackground=PANEL,
                       activeforeground=FG).pack(anchor="w")
        tk.Label(right, text="Olay kareleri ve kayıtları yalnızca\nbu bilgisayarda saklanır.",
                 bg=PANEL, fg=MUTED, justify="left").pack(anchor="w", pady=(18, 0))

        events = tk.Frame(self.root, bg=PANEL, padx=14, pady=10)
        events.grid(row=3, column=0, sticky="ew", padx=24, pady=(12, 20))
        tk.Label(events, text="OLAY GEÇMİŞİ", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.event_list = tk.Listbox(events, height=5, bg="#111f2d", fg=FG,
                                     selectbackground="#304357", relief="flat",
                                     font=("Consolas", 10))
        self.event_list.pack(fill="x", pady=(7, 0))

    def _emit_gui_error(self, err: str):
        messagebox.showerror("C301 Monitor", err)

    def start(self, demo: bool = False):
        if self.running:
            self.status_var.set("Önce aktif bağlantıyı durdurun")
            return
        source = self.source_var.get().strip()
        if not source and not demo:
            self._emit_gui_error("Kamera kaynağını yazın")
            return
        self.worker = CameraWorker(source, self.messages, self.recorder,
                                   demo=demo, confidence=self.options.confidence,
                                   device=self.options.device,
                                   person_only=False,
                                   inference_size=self.options.imgsz,
                                   inference_interval=self.options.inference_interval,
                                   preview_only=self.options.preview_only,
                                   capture_backend=self.options.capture_backend,
                                   capture_width=self.options.capture_width,
                                   capture_height=self.options.capture_height)
        self.running = True
        self.status_var.set("Bağlanıyor...")
        self.worker.start()

    def stop(self):
        if self.worker:
            self.worker.stop()
            self.status_var.set("Kapanıyor...")

    def snapshot(self):
        if not self.worker or not self.running:
            self._emit_gui_error("Önce bağlantı başlatın")
            return
        try:
            if self.worker.save_manual() is None:
                self.status_var.set("Henüz kaydedilecek görüntü yok")
        except Exception as error:
            self._emit_gui_error(str(error))

    def _poll(self):
        freshest = None
        try:
            while True:
                msg = self.messages.get_nowait()
                kind = msg[0]
                if kind == "frame":
                    # Never render 10 old queued frames sequentially.
                    freshest = msg
                elif kind == "status":
                    self.status_var.set(msg[1])
                elif kind == "error":
                    self.status_var.set("Hata: " + msg[1][:90])
                    self.event_list.insert(0, "HATA: " + msg[1][:110])
                elif kind == "event":
                    event = msg[1]
                    self.event_count += 1
                    local_time = datetime.fromisoformat(event["timestamp_utc"]).astimezone().strftime("%H:%M:%S")
                    self.event_list.insert(0, f"{local_time}  |  {friendly_name(event['label'])}  |  {event['mode']}")
                    if self.event_list.size() > 60:
                        self.event_list.delete(60, tk.END)
                    if event["label"] == "person" and self.voice_var.get() and event["kind"] == "detection":
                        self.speaker.say("Dikkat. Odada bir kişi algılandı.")
                elif kind == "ended":
                    self.running = False
                    self.worker = None
        except queue.Empty:
            pass
        if freshest is not None:
            self.raw_frame = freshest[1]
            self.frame_size = (freshest[1].shape[1], freshest[1].shape[0])
            self.last_detections = [x for x in freshest[2]
                                    if not self.only_people.get() or x.name == "person"]
            self.count_var.set(f"{len(self.last_detections)} nesne")
            self._paint_video()
            self._draw_radar()
        self.root.after(70, self._poll)

    def _paint_video(self):
        if not hasattr(self, "raw_frame"):
            return
        frame = self.raw_frame.copy()
        for d in self.last_detections:
            cv2.rectangle(frame, (d.x1, d.y1), (d.x2, d.y2), (90, 220, 80), 2)
            cv2.putText(frame, f"{friendly_name(d.name).replace('ş', 's').replace('ı', 'i').replace('ü', 'u').replace('ö', 'o').replace('ğ', 'g').replace('ç', 'c')} {d.confidence:.0%}",
                        (max(0, d.x1), max(24, d.y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                        .55, (90, 220, 80), 2)
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        h, w = frame.shape[:2]
        ratio = min(cw / w, ch / h)
        tw, th = max(1, int(w * ratio)), max(1, int(h * ratio))
        frame = cv2.resize(frame, (tw, th))
        pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        self.last_photo = ImageTk.PhotoImage(pil)
        self.canvas.coords(self.video_item, cw // 2, ch // 2)
        self.canvas.itemconfig(self.video_item, image=self.last_photo)
        self.canvas.itemconfigure(self.placeholder, state="hidden")

    def _draw_radar(self):
        c = self.radar
        c.delete("all")
        w, h = max(c.winfo_width(), 10), max(c.winfo_height(), 10)
        mid_x, mid_y = w / 2, h / 2
        r = min(w, h) * .44
        for fraction in [1.0, .72, .44, .18]:
            k = r * fraction
            c.create_oval(mid_x - k, mid_y - k, mid_x + k, mid_y + k, outline="#254d60", width=1)
        c.create_line(mid_x - r, mid_y, mid_x + r, mid_y, fill="#254d60")
        c.create_line(mid_x, mid_y - r, mid_x, mid_y + r, fill="#254d60")
        fw, fh = self.frame_size
        for d in self.last_detections:
            cx, cy = d.center
            x = mid_x + (cx / fw - .5) * 2 * r * .94
            y = mid_y + (cy / fh - .5) * 2 * r * .94
            c.create_oval(x - 5, y - 5, x + 5, y + 5, fill=CYAN, outline="")
            c.create_text(x, y - 15, text=friendly_name(d.name), fill=FG,
                          font=("Segoe UI", 9))

    def close(self):
        if self.worker:
            self.worker.stop()
        self.speaker.close()
        self.root.destroy()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Xiaomi C301 local AI security monitor")
    ap.add_argument("--source", default="rtsp://127.0.0.1:8554/c301",
                    help="OpenCV input, RTSP stream URL, webcam index (0) or video file")
    ap.add_argument("--demo", action="store_true", help="Synthetic demo without camera/model")
    ap.add_argument("--preview-only", action="store_true",
                    help="Only show camera preview; disable YOLO/event detection to isolate stream latency")
    ap.add_argument("--capture-backend", choices=("opencv", "ffmpeg"), default="opencv",
                    help="Choose tested low-buffer FFmpeg pipe or legacy OpenCV reader")
    ap.add_argument("--capture-width", type=int, default=960,
                    help="FFmpeg preview width (default 960)")
    ap.add_argument("--capture-height", type=int, default=540,
                    help="FFmpeg preview height (default 540)")
    ap.add_argument("--device", default="cpu", help="Ultralytics inference device: cpu, 0, cuda:0")
    ap.add_argument("--imgsz", type=int, default=416,
                    help="YOLO analysis image size; smaller is faster (default: 416)")
    ap.add_argument("--inference-interval", type=float, default=.45,
                    help="Minimum seconds between starting YOLO analyses (default: 0.45)")
    ap.add_argument("--confidence", type=float, default=.45)
    ap.add_argument("--person-only", action="store_true")
    ap.add_argument("--mute", action="store_true", help="Start with PC speech disabled")
    ap.add_argument("--data-dir", default="private_data")
    args = ap.parse_args(argv)
    if not (160 <= args.capture_width <= 1920 and 90 <= args.capture_height <= 1080):
        ap.error("Capture width/height out of supported range")
    if args.capture_backend == "ffmpeg" and not args.source.startswith("rtsp://") and not args.demo:
        ap.error("--capture-backend ffmpeg requires a local RTSP source")
    if not (0.05 <= args.confidence <= 1.0):
        ap.error("--confidence must be between 0.05 and 1.0")
    if not (160 <= args.imgsz <= 1280 and args.imgsz % 32 == 0):
        ap.error("--imgsz must be a multiple of 32 between 160 and 1280")
    if not (0.1 <= args.inference_interval <= 10.0):
        ap.error("--inference-interval must be between 0.1 and 10.0 seconds")
    root = tk.Tk()
    MonitorApp(root, args)
    root.mainloop()


if __name__ == "__main__":
    main()
