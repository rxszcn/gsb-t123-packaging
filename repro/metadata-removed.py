"""字段有效期：还没引入的会被拒，早就移除掉的照收

跑法：PYTHONPATH=src .venv/bin/python repro/metadata-removed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from packaging.metadata import Metadata, parse_email

HEAD = "Metadata-Version: {v}\nName: foo\nVersion: 1.0\n"
CASES = [("1.0", "Requires-Dist: foo"), ("1.0", "License-File: LICENSE"),
         ("2.1", "Requires: foo"), ("2.1", "Description-Content-Type: text/markdown"),
         ("2.1", "Provides-Dist: bar"), ("2.1", "Requires-External: curl")]

for v, extra in CASES:
    src = HEAD.format(v=v) + extra + "\n\nbody\n"
    raw, unparsed = parse_email(src.encode())
    try:
        md = Metadata.from_raw(raw)
    except Exception as e:
        print(f"v={v} {extra:40s} -> REJECTED {type(e).__name__}: {e}")
        continue
    field = extra.split(":")[0].lower().replace("-", "_")
    print(f"v={v} {extra:40s} -> ACCEPTED unparsed={list(unparsed)} md.{field}={getattr(md, field, '<无此属性>')!r}")
