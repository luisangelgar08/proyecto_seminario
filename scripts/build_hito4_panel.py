from __future__ import annotations

from pathlib import Path
import pandas as pd


INPUT = Path("data/silver/indicators_tidy.parquet")
OUT_GOLD = Path("data/gold")
OUT_GOLD.mkdir(parents=True, exist_ok=True)


def build_panel(df: pd.DataFrame, keep: list[str], outpath: Path) -> None:
    sub = df[df["indicator"].isin(keep)].copy()

    sub["quarter_date"] = sub["date"].dt.to_period("Q").dt.to_timestamp(how="end")

    panel = (
        sub.groupby(["quarter_date", "indicator"], as_index=False)["value"]
        .mean()
        .pivot(index="quarter_date", columns="indicator", values="value")
        .reset_index()
        .rename(columns={"quarter_date": "date"})
        .sort_values("date")
        .reset_index(drop=True)
    )

    panel = panel.dropna().reset_index(drop=True)

    print(f"\n===== {outpath.name} =====")
    print(panel)
    print("Shape:", panel.shape)
    print("Columnas:", panel.columns.tolist())

    panel.to_parquet(outpath, index=False)
    print(f"Guardado -> {outpath}")


def main() -> None:
    df = pd.read_parquet(INPUT).copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).reset_index(drop=True)

    # Panel principal para VAR
    build_panel(
        df,
        keep=["iioc_total", "empleo_construccion"],
        outpath=OUT_GOLD / "hito4_panel_main.parquet"
    )

    # Panel complementario con IPOC y empleo
    build_panel(
        df,
        keep=["ipoc_total", "empleo_construccion"],
        outpath=OUT_GOLD / "hito4_panel_ipoc_empleo.parquet"
    )

    # Serie sola de IPOC para análisis descriptivo / quiebres
    build_panel(
        df,
        keep=["ipoc_total"],
        outpath=OUT_GOLD / "hito4_panel_ipoc.parquet"
    )


if __name__ == "__main__":
    main()