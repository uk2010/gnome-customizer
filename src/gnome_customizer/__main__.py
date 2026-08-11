import sys


def main() -> int:
    from .backend.app_theme import migrate_managed_application_css
    migrate_managed_application_css()
    from .application import CustomizerApplication
    return CustomizerApplication().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
