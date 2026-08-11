import unittest

import gi
gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gnome_customizer.pages.preferences import _clock_text, _clock_value


class ClockFormatTests(unittest.TestCase):
    def test_twelve_hour_night_light_display_and_input(self):
        self.assertEqual(_clock_text(21.5, True), "9:30 PM")
        self.assertEqual(_clock_value("12:15 AM", True), 0.25)
        self.assertEqual(_clock_value("12:15 PM", True), 12.25)

    def test_twenty_four_hour_night_light_display_and_input(self):
        self.assertEqual(_clock_text(21.5, False), "21:30")
        self.assertEqual(_clock_value("06:45", False), 6.75)

    def test_wrong_format_is_rejected(self):
        with self.assertRaises(ValueError):
            _clock_value("21:30", True)
        with self.assertRaises(ValueError):
            _clock_value("9:30 PM", False)


if __name__ == "__main__":
    unittest.main()
