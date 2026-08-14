import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from gnome_customizer.backend.app_theme import (
    ApplicationThemeManager,
    NautilusTransparencyManager,
    APPLICATION_PRESETS,
    DEFAULT_APPLICATION_PALETTE,
    application_css,
    managed_bytes,
    managed_nautilus_bytes,
    migrate_managed_application_css,
    unmanaged_bytes,
    unmanaged_nautilus_bytes,
    nautilus_transparency_css,
)
from gnome_customizer.backend.state import StateStore


class ApplicationThemeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.state = StateStore(self.root / "state.json")
        self.manager = ApplicationThemeManager(self.state, self.root / "home")

    def test_managed_block_preserves_existing_css(self):
        original = b"button { color: red; }\n"
        themed = managed_bytes(original, application_css(DEFAULT_APPLICATION_PALETTE))
        self.assertIn(original.strip(), themed)
        self.assertEqual(unmanaged_bytes(themed), original)

    def test_apply_and_restore_created_files(self):
        snapshot = self.manager.apply(DEFAULT_APPLICATION_PALETTE)
        self.assertTrue(all(path.is_file() for path in self.manager.targets))
        self.assertTrue(self.state.data["application_theme"]["palette"])
        self.manager.restore_snapshot(snapshot)
        self.assertTrue(all(not path.exists() for path in self.manager.targets))
        self.manager.apply(DEFAULT_APPLICATION_PALETTE)
        self.assertEqual(self.manager.restore(), 2)
        self.assertTrue(all(not path.exists() for path in self.manager.targets))

    def test_restore_keeps_unrelated_user_css(self):
        target = self.manager.targets[1]
        target.parent.mkdir(parents=True)
        target.write_bytes(b"entry { padding: 4px; }\n")
        self.manager.apply(DEFAULT_APPLICATION_PALETTE)
        self.manager.restore()
        self.assertEqual(target.read_bytes(), b"entry { padding: 4px; }\n")

    def test_factory_reset_removes_preexisting_user_css(self):
        target=self.manager.targets[1];target.parent.mkdir(parents=True);target.write_text("window { color: red; }")
        self.assertEqual(self.manager.reset_factory(),1);self.assertFalse(target.exists())

    def test_complete_presets_generate_distinct_valid_themes(self):
        generated={name:application_css(palette) for name,palette in APPLICATION_PRESETS.items()}
        self.assertEqual(set(generated),{"Light","Dark","High Contrast"});self.assertEqual(len(set(generated.values())),3)
        for css in generated.values():self.assertIn(".nautilus-window",css);self.assertIn("window:not(.gnome-customizer-window):not(.desktopwindow)",css);self.assertNotIn("@define-color",css)

    def test_legacy_managed_css_is_removed_at_startup(self):
        self.manager.apply(DEFAULT_APPLICATION_PALETTE);target=self.manager.targets[1];legacy=target.read_bytes().replace(b"window:not(.gnome-customizer-window):not(.desktopwindow)",b"window")
        target.write_bytes(legacy)
        with patch('gnome_customizer.backend.app_theme.StateStore',return_value=self.state),patch('gnome_customizer.backend.app_theme.ApplicationThemeManager',return_value=self.manager):
            self.assertEqual(migrate_managed_application_css(),2)
        self.assertFalse(target.exists())

    def test_desktop_icons_window_is_never_painted(self):
        css=application_css(APPLICATION_PRESETS["Light"])
        self.assertNotIn("window:not(.gnome-customizer-window) {",css)
        self.assertIn(":not(.desktopwindow)",css)

    def test_unreadable_complete_palette_is_rejected_before_writing(self):
        unsafe={**DEFAULT_APPLICATION_PALETTE,"text_color":"#111111","window_color":"#111111"}
        with self.assertRaisesRegex(Exception,"contrast is unsafe"):self.manager.apply(unsafe)
        self.assertTrue(all(not path.exists() for path in self.manager.targets))

    def test_files_transparency_preserves_existing_css_exactly(self):
        original=b"entry { padding: 4px; }"
        themed=managed_nautilus_bytes(original,.42)
        self.assertEqual(unmanaged_nautilus_bytes(themed),original)

    def test_files_manager_removes_only_its_created_file(self):
        manager=NautilusTransparencyManager(self.state,self.root/"files-home")
        self.assertTrue(manager.sync(True,.65));self.assertTrue(manager.target.is_file())
        self.assertTrue(manager.restore());self.assertFalse(manager.target.exists())

    def test_files_manager_retains_preexisting_empty_file(self):
        manager=NautilusTransparencyManager(self.state,self.root/"files-home")
        manager.target.parent.mkdir(parents=True);manager.target.write_bytes(b"\n")
        manager.sync(True,.5);manager.restore()
        self.assertEqual(manager.target.read_bytes(),b"\n")

    def test_files_transparency_rejects_partial_marker_without_writing(self):
        manager=NautilusTransparencyManager(self.state,self.root/"files-home")
        manager.target.parent.mkdir(parents=True);partial=b"body {}\n/* GNOME Customizer Files transparency: begin */\n"
        manager.target.write_bytes(partial)
        with self.assertRaisesRegex(ValueError,"incomplete"):manager.sync(True,.5)
        self.assertEqual(manager.target.read_bytes(),partial)

    def test_files_manager_refuses_symbolic_link(self):
        manager=NautilusTransparencyManager(self.state,self.root/"files-home")
        source=self.root/"outside.css";source.write_bytes(b"window {}")
        manager.target.parent.mkdir(parents=True);manager.target.symlink_to(source)
        with self.assertRaisesRegex(ValueError,"symbolic-link"):manager.sync(True,.5)
        self.assertEqual(source.read_bytes(),b"window {}")

    def test_files_css_is_nautilus_scoped_and_does_not_fade_contents(self):
        css=nautilus_transparency_css(.35)
        self.assertIn("window.nautilus-window",css);self.assertIn("--view-bg-color",css)
        self.assertIn("alpha(@window_bg_color, 0.35)",css);self.assertNotIn("opacity:",css)
        for line in css.splitlines():
            if "{" in line:self.assertIn("nautilus-window",line)


if __name__ == "__main__":
    unittest.main()
