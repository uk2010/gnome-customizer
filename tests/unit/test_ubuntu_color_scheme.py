import unittest
from pathlib import Path


class UbuntuColorSchemeTests(unittest.TestCase):
    def test_desktop_appearance_synchronizes_ubuntu_shell_key(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/pages/preferences.py").read_text()
        self.assertIn('"org.gnome.shell.ubuntu","color-scheme"',source)
        self.assertIn('"Ubuntu Color Scheme"',source)

    def test_reset_has_explicit_ubuntu_shell_default(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/backend/settings.py").read_text()
        self.assertIn('("org.gnome.shell.ubuntu","color-scheme"):"default"',source)


if __name__ == "__main__":
    unittest.main()
