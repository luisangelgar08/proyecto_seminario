from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tsa.api import VAR
import ruptures as rpt


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)

    raise ValueError("Formato no soportado. Usa .parquet o .csv")


def prepare_dataframe(
    df: pd.DataFrame,
    date_col: str,
    vars_: List[str],
) -> pd.DataFrame:
    missing = [c for c in [date_col, *vars_] if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas en el dataset: {missing}")

    work = df[[date_col, *vars_]].copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.dropna(subset=[date_col]).sort_values(date_col).reset_index(drop=True)

    for c in vars_:
        work[c] = pd.to_numeric(work[c], errors="coerce")

    work = work.dropna(subset=vars_).reset_index(drop=True)
    return work


def stationarity_tests(series: pd.Series) -> dict:
    x = series.dropna().astype(float)

    if len(x) < 10:
        return {
            "n_obs": len(x),
            "adf_stat": np.nan,
            "adf_pvalue": np.nan,
            "kpss_stat": np.nan,
            "kpss_pvalue": np.nan,
            "stationary_hint": "insuficiente_muestra",
        }

    try:
        adf_res = adfuller(x, autolag="AIC")
        adf_stat, adf_p = adf_res[0], adf_res[1]
    except Exception:
        adf_stat, adf_p = np.nan, np.nan

    try:
        kpss_res = kpss(x, regression="c", nlags="auto")
        kpss_stat, kpss_p = kpss_res[0], kpss_res[1]
    except Exception:
        kpss_stat, kpss_p = np.nan, np.nan

    # Heurística:
    # ADF p < 0.05 sugiere estacionariedad
    # KPSS p > 0.05 sugiere estacionariedad
    if pd.notna(adf_p) and pd.notna(kpss_p):
        if adf_p < 0.05 and kpss_p > 0.05:
            hint = "estacionaria"
        elif adf_p >= 0.05 and kpss_p <= 0.05:
            hint = "no_estacionaria"
        else:
            hint = "mixta"
    else:
        hint = "indefinida"

    return {
        "n_obs": len(x),
        "adf_stat": adf_stat,
        "adf_pvalue": adf_p,
        "kpss_stat": kpss_stat,
        "kpss_pvalue": kpss_p,
        "stationary_hint": hint,
    }


def build_stationarity_table(df: pd.DataFrame, vars_: List[str], version: str) -> pd.DataFrame:
    rows = []
    for col in vars_:
        out = stationarity_tests(df[col])
        out["variable"] = col
        out["version"] = version
        rows.append(out)
    return pd.DataFrame(rows)[
        ["version", "variable", "n_obs", "adf_stat", "adf_pvalue", "kpss_stat", "kpss_pvalue", "stationary_hint"]
    ]


def detect_breakpoints(series: pd.Series, max_breaks: int = 5, model: str = "l2") -> List[int]:
    x = series.dropna().astype(float).to_numpy()
    if len(x) < 12:
        return []

    # Penalty conservadora para no sobredetectar
    pen = 3 * np.log(len(x))
    algo = rpt.Pelt(model=model).fit(x)
    bkps = algo.predict(pen=pen)

    # ruptures devuelve el índice final como breakpoint, lo removemos
    bkps = [b for b in bkps if b < len(x)]

    # limitar por seguridad
    return bkps[:max_breaks]


def build_breaks_table(df: pd.DataFrame, date_col: str, vars_: List[str], max_breaks: int = 5) -> pd.DataFrame:
    rows = []
    for col in vars_:
        s = df[[date_col, col]].dropna().reset_index(drop=True)
        bkps = detect_breakpoints(s[col], max_breaks=max_breaks)

        if not bkps:
            rows.append({
                "variable": col,
                "break_number": 0,
                "break_index": np.nan,
                "break_date": np.nan,
            })
            continue

        for i, b in enumerate(bkps, start=1):
            rows.append({
                "variable": col,
                "break_number": i,
                "break_index": int(b),
                "break_date": s.loc[b, date_col],
            })

    return pd.DataFrame(rows)


def transform_for_var(df: pd.DataFrame, vars_: List[str], difference: bool = True) -> pd.DataFrame:
    x = df[vars_].copy()
    if difference:
        x = x.diff()
    x = x.dropna().reset_index(drop=True)
    return x


def fit_var_grid(model_df: pd.DataFrame, max_lags: int = 4) -> tuple[pd.DataFrame, dict]:
    rows = []
    fits = {}

    for lag in range(1, max_lags + 1):
        try:
            model = VAR(model_df)
            fit = model.fit(lag)

            try:
                stable = bool(fit.is_stable())
            except Exception:
                stable = np.nan

            rows.append({
                "lag": lag,
                "nobs": fit.nobs,
                "aic": fit.aic,
                "bic": fit.bic,
                "hqic": fit.hqic,
                "fpe": fit.fpe,
                "stable": stable,
                "status": "ok",
                "error": "",
            })
            fits[lag] = fit
        except Exception as e:
            rows.append({
                "lag": lag,
                "nobs": np.nan,
                "aic": np.nan,
                "bic": np.nan,
                "hqic": np.nan,
                "fpe": np.nan,
                "stable": np.nan,
                "status": "fail",
                "error": str(e),
            })

    result_df = pd.DataFrame(rows)
    return result_df, fits


def export_irf(best_fit, outdir: Path, periods: int = 12) -> None:
    irf = best_fit.irf(periods)

    # Gráfico
    fig = irf.plot(orth=False)
    fig.savefig(outdir / "irf_plot.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Tabla
    names = best_fit.names
    rows = []
    for h in range(irf.irfs.shape[0]):
        for i, impulse in enumerate(names):
            for j, response in enumerate(names):
                rows.append({
                    "horizon": h,
                    "impulse": impulse,
                    "response": response,
                    "value": irf.irfs[h, j, i],
                })

    pd.DataFrame(rows).to_csv(outdir / "irf_values.csv", index=False)


def save_series_plots(df: pd.DataFrame, date_col: str, vars_: List[str], outdir: Path) -> None:
    for col in vars_:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df[date_col], df[col])
        ax.set_title(f"Serie - {col}")
        ax.set_xlabel("Fecha")
        ax.set_ylabel(col)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(outdir / f"serie_{col}.png", dpi=150)
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline inicial de Hito 4")
    parser.add_argument("--input", type=str, required=True, help="Ruta del dataset final (.parquet o .csv)")
    parser.add_argument("--date-col", type=str, required=True, help="Nombre de la columna de fecha")
    parser.add_argument("--vars", nargs="+", required=True, help="Variables numéricas para análisis")
    parser.add_argument("--report-dir", type=str, default="reports/hito4", help="Carpeta de salida")
    parser.add_argument("--max-lags", type=int, default=4, help="Máximo de rezagos para grilla VAR")
    parser.add_argument("--max-breaks", type=int, default=5, help="Máximo de quiebres a reportar")
    parser.add_argument("--no-diff", action="store_true", help="No diferenciar antes del VAR")
    args = parser.parse_args()

    input_path = Path(args.input)
    report_dir = Path(args.report_dir)
    ensure_dir(report_dir)

    df_raw = load_dataset(input_path)
    df = prepare_dataframe(df_raw, args.date_col, args.vars)

    # Guardar base usada
    df.to_parquet(report_dir / "analysis_base.parquet", index=False)

    # Gráficas de series
    save_series_plots(df, args.date_col, args.vars, report_dir)

    # Estacionariedad en niveles
    stat_levels = build_stationarity_table(df, args.vars, version="levels")
    stat_levels.to_csv(report_dir / "stationarity_levels.csv", index=False)

    # Estacionariedad en primeras diferencias
    df_diff = df[[args.date_col] + args.vars].copy()
    for col in args.vars:
        df_diff[col] = df_diff[col].diff()
    df_diff = df_diff.dropna().reset_index(drop=True)

    stat_diff = build_stationarity_table(df_diff, args.vars, version="diff_1")
    stat_diff.to_csv(report_dir / "stationarity_diff1.csv", index=False)

    # Quiebres estructurales en niveles
    breaks_df = build_breaks_table(df, args.date_col, args.vars, max_breaks=args.max_breaks)
    breaks_df.to_csv(report_dir / "breakpoints.csv", index=False)

    # VAR / robustez por lag
    model_df = transform_for_var(df, args.vars, difference=not args.no_diff)
    var_grid, fits = fit_var_grid(model_df, max_lags=args.max_lags)
    var_grid.to_csv(report_dir / "var_lag_grid.csv", index=False)

    ok_grid = var_grid[var_grid["status"] == "ok"].copy()
    if ok_grid.empty:
        raise RuntimeError("Ningún modelo VAR pudo ajustarse. Revisa variables, muestra o max_lags.")

    best_lag = int(ok_grid.sort_values("aic").iloc[0]["lag"])
    best_fit = fits[best_lag]

    export_irf(best_fit, report_dir, periods=12)

    summary = {
        "input": str(input_path),
        "date_col": args.date_col,
        "variables": args.vars,
        "n_rows_analysis": int(len(df)),
        "difference_for_var": bool(not args.no_diff),
        "best_lag_by_aic": best_lag,
        "report_dir": str(report_dir),
    }

    with open(report_dir / "hito4_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n✅ Hito 4 inicial ejecutado correctamente")
    print(f"Reportes en: {report_dir}")
    print(f"Mejor lag por AIC: {best_lag}")


if __name__ == "__main__":
    main()