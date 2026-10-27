import unittest

from ti_assistant import (
    interpret_utterance,
    is_sleep_command,
    movement_intent,
    normalize,
)


class TiCommandTests(unittest.TestCase):
    def test_turkish_normalization(self):
        self.assertEqual(normalize("Ti, SAĞA dön!"), "ti saga don")

    def test_initial_wake_is_required(self):
        self.assertEqual(
            interpret_utterance("Ti saat kaç", active=False),
            ("ignore", ""),
        )
        self.assertEqual(
            interpret_utterance("Merhaba Ti", active=False),
            ("wake", ""),
        )

    def test_active_session_accepts_ti_command(self):
        self.assertEqual(
            interpret_utterance("Ti sistem durumu ne", active=True),
            ("command", "sistem durumu ne"),
        )

    def test_followup_accepts_command_without_name(self):
        self.assertEqual(
            interpret_utterance("saat kaç", active=True, followup=True),
            ("followup", "saat kac"),
        )

    def test_movement_intents_are_explicit(self):
        self.assertEqual(movement_intent("Ti sola dön"), ("move", "left"))
        self.assertEqual(movement_intent("beni takip et"), ("follow_on", ""))
        self.assertEqual(movement_intent("takibi durdur"), ("follow_off", ""))

    def test_sound_direction_is_not_claimed(self):
        self.assertEqual(
            movement_intent("sesin geldiği yere dön"),
            ("voice_direction", ""),
        )

    def test_sleep_commands(self):
        self.assertTrue(is_sleep_command("iyi geceler"))
        self.assertFalse(is_sleep_command("sistem durumu"))


if __name__ == "__main__":
    unittest.main()
