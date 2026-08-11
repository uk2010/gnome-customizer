import tempfile
import unittest
from pathlib import Path

from gnome_customizer.backend.assets import copy_managed_image, remove_managed_images


class ManagedAssetTests(unittest.TestCase):
    def test_staging_replacement_does_not_overwrite_active_asset(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, root)
        source = root / "selected.png"
        managed = root / "managed"
        source.write_bytes(b"first wallpaper")
        active = copy_managed_image(source, managed, "desktop-wallpaper", "image/png")
        original = active.read_bytes()
        source.write_bytes(b"second wallpaper")
        staged = copy_managed_image(source, managed, "desktop-wallpaper", "image/png")
        self.assertNotEqual(active, staged)
        self.assertEqual(active.read_bytes(), original)
        self.assertEqual(staged.read_bytes(), b"second wallpaper")

    def test_cleanup_removes_only_managed_wallpaper_copies(self):
        root=Path(tempfile.mkdtemp());self.addCleanup(__import__("shutil").rmtree,root)
        (root/"desktop-wallpaper-abc.png").write_bytes(b"managed");(root/"keep.png").write_bytes(b"user")
        self.assertEqual(remove_managed_images(root),1);self.assertTrue((root/"keep.png").is_file())


if __name__ == "__main__":
    unittest.main()
