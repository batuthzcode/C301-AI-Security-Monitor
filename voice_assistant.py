r"""Voice/weather assistant companion to C301 AI Security Monitor.

Windows text dry run:
  .\.venv\Scripts\python.exe voice_assistant.py --text "Hava nasıl?" --city Ankara --mute
Windows push-to-talk:
  .\.venv\Scripts\python.exe voice_assistant.py --listen --city Ankara
"""
from __future__ import annotations

import argparse
from c301_monitor.assistant_core import answer_question


def main() -> None:
    parser = argparse.ArgumentParser(description="C301 sesli asistan / hava durumu prototipi")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--text", help="Mikrofon olmadan metinle test et")
    mode.add_argument("--listen", action="store_true", help="Windows mikrofonundan bir kez dinle")
    parser.add_argument("--city", default="Ankara", help="Hava durumu şehri (varsayılan: Ankara)")
    parser.add_argument("--seconds", type=float, default=5, help="Dinleme süresi, 2-15 saniye")
    parser.add_argument("--model", default="tiny", choices=("tiny", "base", "small"),
                        help="Türkçe konuşma tanıma modeli (ilk kullanımda indirilir)")
    parser.add_argument("--mute", action="store_true", help="Ses çıkışı yapma, yalnızca yaz")
    args = parser.parse_args()
    if args.listen:
        try:
            from c301_monitor.assistant_audio import transcribe_once
            question = transcribe_once(seconds=args.seconds, model_name=args.model)
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            parser.exit(1, f"Mikrofon veya konuşma tanıma başlatılamadı: {exc}\n")
    else:
        question = args.text
    print("Soru:", question or "(duyulmadı)")
    reply = answer_question(question, city=args.city)
    print("Yanıt:", reply)
    if not args.mute:
        try:
            from c301_monitor.assistant_audio import say
            if not say(reply):
                print("[Uyarı] PC sesli yanıtı kullanılamadı; yanıt yazdırıldı.")
        except ImportError:
            print("[Uyarı] PC sesli yanıt modülü bulunamadı.")


if __name__ == "__main__":
    main()
