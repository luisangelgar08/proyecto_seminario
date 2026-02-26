from pathlib import Path
import pandas as pd

DATA = Path("data/processed/indicators_tidy.csv")
REP = Path("reports")
REP.mkdir(exist_ok=True)

df = pd.read_csv(DATA, parse_dates=["date"])

checks = {
    "no_null_date": int(df["date"].isna().sum()),
    "no_null_value": int(df["value"].isna().sum()),
    "duplicate_date_indicator": int(df.duplicated(subset=["date", "indicator"]).sum()),
    "n_indicators": int(df["indicator"].nunique()),
    "min_date": str(df["date"].min()),
    "max_date": str(df["date"].max()),
    "rows": int(len(df)),
}

lines = ["# Quality report (Hito 2)", ""]
for k, v in checks.items():
    lines.append(f"- {k}: {v}")

(REP / "quality_report.md").write_text("\n".join(lines), encoding="utf-8")
print("OK -> reports/quality_report.md")