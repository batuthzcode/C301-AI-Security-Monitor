import unittest
from c301_monitor.detection import Detection, EventGate


class EventGateTests(unittest.TestCase):
    def setUp(self):
        self.person = Detection("person", 0.94, 20, 30, 50, 110)
        self.cat = Detection("cat", 0.91, 40, 60, 80, 100)
        self.gate = EventGate(gap=6, min_interval=30)

    def test_center(self):
        self.assertEqual(self.person.center, (35, 70))

    def test_first_appearance_only(self):
        self.assertEqual(len(self.gate.observe([self.person], 0)), 1)
        self.assertEqual(len(self.gate.observe([self.person], 1)), 0)
        self.assertEqual(len(self.gate.observe([self.person], 4)), 0)

    def test_reappear_after_gap_and_cooldown(self):
        self.gate.observe([self.person], 0)
        self.assertEqual(self.gate.observe([self.person], 15), [])
        self.assertEqual(len(self.gate.observe([self.person], 48)), 1)

    def test_separate_categories(self):
        self.assertEqual(len(self.gate.observe([self.person, self.cat], 0)), 2)

    def test_duplicate_class_uses_highest_confidence(self):
        lower = Detection("person", 0.31, 5, 7, 21, 50)
        events = self.gate.observe([lower, self.person], 0)
        self.assertEqual(events, [self.person])


if __name__ == "__main__":
    unittest.main()
