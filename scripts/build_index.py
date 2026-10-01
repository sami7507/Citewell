"""(Re)build the sample-document search index. Run from the project root."""
import _bootstrap  # noqa: F401

from citewell import config
from citewell.pipeline import build_index

if __name__ == "__main__":
    config.configure_logging()
    config.ensure_dirs()
    build_index()
