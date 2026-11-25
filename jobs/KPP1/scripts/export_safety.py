"""Compatibility entry for the historical export recipe; checks live in tools/derive."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.derive.export_safety import (  # noqa: F401,E402 - replay API
    main, require_delivery_mode, require_udim_regions, reserve_run, run_paths,
    validate_atlas, validate_version,
)

if __name__ == "__main__":
    main()
