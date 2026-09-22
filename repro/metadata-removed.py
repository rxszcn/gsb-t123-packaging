"""同一台机器上，尚未引入的字段被拒、已被移除的字段被放行

跑法：PYTHONPATH=src .venv/bin/python repro/metadata-removed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from packaging.metadata import Metadata, parse_email

HEAD = "Metadata-Version: {v}\nName: foo\nVersion: 1.0\n\nbody\n"
CASES = [("1.0", "Requires-Dist: foo"), ("1.0", "License-File: LICENSE"),
         ("2.1", "Requires: foo"), ("2.1", "Description-Content-Type: text/markdown"),
         ("2.1", "Provides-Dist: bar"), ("2.1", "Requires-External: curl")]

for v, extra in CASES:
    src = HEAD.format(v=v) + extra + "\n"
    raw, unparsed = parse_email(src.encode())
    try:
        md = Metadata.from_raw(raw)
        print(f"v={v} {extra:36s} -> ACCEPTED raw={ {k: val for k, val in raw.items() if k not in ('name', 'version', 'description', 'metadata_version')} } unparsed={list(unparsed)}")
    except Exception as e:
        print(f"v={v} {extra:36s} -> REJECTED {type(e).__name__}: {e}")
