import unittest
from c301_monitor.video import LatestFrameBuffer


class LatestFrameTests(unittest.TestCase):
    def test_last_update_wins(self):
        buf = LatestFrameBuffer()
        self.assertEqual(buf.snapshot(), (0, None))
        buf.update("old")
        buf.update("recent")
        self.assertEqual(buf.snapshot(), (2, "recent"))

    def test_monotonically_increasing_sequence(self):
        buf = LatestFrameBuffer()
        last = 0
        for i in range(100):
            buf.update(i)
            seq, value = buf.snapshot()
            self.assertEqual(seq, last + 1)
            self.assertEqual(value, i)
            last = seq


if __name__ == "__main__":
    unittest.main()
