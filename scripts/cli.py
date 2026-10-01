"""Run `citewell.cli` from the project root without installing the package."""
import _bootstrap  # noqa: F401  (adds backend/ to sys.path)

from citewell.cli import main

if __name__ == "__main__":
    main()
