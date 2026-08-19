import sys


def main() -> int:
    # Keep the session startup repair GUI-free. GNOME Shell reads its
    # extension list before normal applications are launched.
    if "--ensure-extensions" in sys.argv[1:]:
        from .backend.settings import SettingsBackend
        SettingsBackend().ensure_bundled_extensions()
        return 0

    from .backend.app_theme import migrate_managed_application_css
    migrate_managed_application_css()
    from .application import CustomizerApplication
    return CustomizerApplication().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
