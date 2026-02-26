from pathlib import Path
import hashlib
from datetime import datetime
import pandas as pd

RAW_DIR = Path("data/raw")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

# Toma TODOS los excels del raw (sin depender de nombres)
files = sorted([p for p in RAW_DIR.glob("*.xls*")])

if not files:
    raise SystemExit("No hay archivos .xls/.xlsx en data/raw/")

rows = []
for p in files:
    rows.append({
        "file": p.name,
        "path": str(p.as_posix()),
        "sha256": sha256(p),
        "size_bytes": p.stat().st_size,
        "ingested_at": datetime.now().isoformat(timespec="seconds"),
    })
    print(f"[OK] {p.name}")

manifest = pd.DataFrame(rows)
out = REPORTS_DIR / "raw_manifest.csv"
manifest.to_csv(out, index=False)
print("Manifest ->", out)