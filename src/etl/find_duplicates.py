from pathlib import Path
import pandas as pd

DATA = Path("data/processed/indicators_tidy.csv")
df = pd.read_csv(DATA, parse_dates=["date"])

dups = df[df.duplicated(subset=["date", "indicator"], keep=False)].sort_values(["indicator", "date"])

print("Duplicated rows:", len(dups))
print("\nResumen por indicador:")
print(dups.groupby("indicator").size().sort_values(ascending=False))

out = Path("reports/duplicates_rows.csv")
out.parent.mkdir(exist_ok=True)
dups.to_csv(out, index=False)
print("\nGuardado ->", out)

# ¿Son duplicados idénticos en value?
check = dups.groupby(["date", "indicator"])["value"].nunique().reset_index(name="n_unique_values")
print("\nCasos donde el duplicado tiene valores diferentes (n_unique_values>1):")
print(check[check["n_unique_values"] > 1].head(20))