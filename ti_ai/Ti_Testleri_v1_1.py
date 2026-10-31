"""Ti v1.1 preview tests; no camera, mic, motor or Spotify connection."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch
import ti_services
from ti_lowlatency import WIDTH, HEIGHT, command, LatestFFmpegCapture


class TestPreview(unittest.TestCase):
    def test_ffmpeg_options(self):
        cmd=command('ffmpeg','rtsp://127.0.0.1:8554/c301')
        self.assertIn('nobuffer',cmd)
        self.assertIn('low_delay',cmd)
        self.assertIn('force_original_aspect_ratio=decrease',cmd[cmd.index('-vf')+1])
        self.assertIn('pad=',cmd[cmd.index('-vf')+1])
        self.assertNotIn('crop=',cmd[cmd.index('-vf')+1])
        self.assertEqual(cmd[-1],'pipe:1')

    def test_untrusted_url_rejected(self):
        with self.assertRaises(ValueError):command('ffmpeg','rtsp://192.168.1.2/c301')

    def test_default_source(self):
        self.assertEqual(ti_services.STREAM_URL, 'rtsp://127.0.0.1:8554/c301')
        self.assertEqual(ti_services.DEFAULTS['digital_zoom'],1.0)

    def test_existing_legacy_source_upgraded_but_explicit_new_override_respected(self):
        with tempfile.TemporaryDirectory() as d:
            prev_dir,prev_path=ti_services.DATA,ti_services.SETTINGS_PATH
            try:
                ti_services.DATA=Path(d)
                ti_services.SETTINGS_PATH=Path(d)/'settings.json'
                ti_services.SETTINGS_PATH.write_text(json.dumps({'video_source':'rtsp://127.0.0.1:8554/c301_h264_hw', 'digital_zoom':2.0}),encoding='utf8')
                s=ti_services.settings_load()
                self.assertEqual(s['video_source'],ti_services.STREAM_URL)
                self.assertEqual(s['digital_zoom'],1.0)
                s['video_source']='rtsp://127.0.0.1:8554/c301_h264_hw'
                ti_services.settings_save(s)
                self.assertEqual(ti_services.settings_load()['video_source'], 'rtsp://127.0.0.1:8554/c301_h264_hw')
            finally:
                ti_services.DATA,ti_services.SETTINGS_PATH=prev_dir,prev_path

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg not installed')
    def test_capture_reader_keeps_latest_not_queue_of_frames(self):
        # A test pattern generated locally by FFmpeg, not camera/network.
        # Input deliberately runs faster than Python consumer so older frames drop.
        def synthetic_cmd(ffmpeg, _url):
            return [ffmpeg, '-hide_banner','-loglevel','error','-f','lavfi',
                    '-i',f'testsrc2=size={WIDTH}x{HEIGHT}:rate=30:duration=1.0',
                    '-pix_fmt','bgr24','-f','rawvideo','pipe:1']
        with patch('ti_lowlatency.command', synthetic_cmd):
            cap=LatestFFmpegCapture('rtsp://127.0.0.1:8554/c301')
            try:
                deadline=time.monotonic()+5
                num=0
                while time.monotonic()<deadline:
                    ok,frame=cap.read()
                    if frame is not None:
                        num+=1
                        self.assertEqual(frame.shape,(HEIGHT,WIDTH,3))
                        if cap._sequence >= 3:break
                    if not ok and cap._sequence==0:self.fail('FFmpeg did not decode any frames')
                self.assertGreaterEqual(num,1)
                # Drain frames in reader without requiring caller read per-frame.
                time.sleep(.7)
                seq_before=cap._sequence
                self.assertGreaterEqual(seq_before,3)
                ok,frame=cap.read()
                self.assertTrue(ok)
                self.assertIsNotNone(frame)
                self.assertEqual(cap._returned,seq_before)
            finally:
                cap.release()

if __name__=='__main__':unittest.main(verbosity=2)
