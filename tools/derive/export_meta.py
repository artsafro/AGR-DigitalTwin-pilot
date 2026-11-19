"""new-case: CLI facade for the shared dependency-free export metadata owner (#1361)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.max.agr_tools.export_meta import (
    address_meta_path, export_binding, export_records,
    load_meta, load_package_meta, main, record_export, unique_object, validate_meta, write_meta,
)

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        raise SystemExit(f'refused: {exc}')
