from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import ruptures as rpt

from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tsa.api import VAR


INPUT = Path("data/gold/hito4_panel_main.parquet")
VARS = ["iioc_total", "empleo_construccion"]
OUTDIR = Path("reports/hito4_v2")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_panel() -> pd.DataFrame:
    if not INPUT.exists():
        raise FileNotFoundError(f"No existe {INPUT}")
    df = pd.read_parquet(INPUT).copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    missing = [c for c in VARS if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas en panel: {missing}")

    for c in VARS:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=VARS).reset_index(drop=True)
    return df


def stationarity_test(series: pd.Series) -> dict:
    x = series.dropna().astype(float)

    out = {
        "n_obs": len(x),
        "adf_stat": np.nan,
        "adf_pvalue": np.nan,
        "kpss_stat": np.nan,
        "kpss_pvalue": np.nan,
        "stationary_hint": "indefinida",
    }

    if len(x) < 8:
        out["stationary_hint"] = "insuficiente_muestra"
        return out

    try:
        adf_res = adfuller(x, autolag="AIC")
        out["adf_stat"] = adf_res[0]
        out["adf_pvalue"] = adf_res[1]
    except Exception:
        pass

    try:
        kpss_res = kpss(x, regression="c", nlags="auto")
        out["kpss_stat"] = kpss_res[0]
        out["kpss_pvalue"] = kpss_res[1]
    except Exception:
        pass

    adf_p = out["adf_pvalue"]
    kpss_p = out["kpss_pvalue"]

    if pd.notna(adf_p) and pd.notna(kpss_p):
        if adf_p < 0.05 and kpss_p > 0.05:
            out["stationary_hint"] = "estacionaria"
        elif adf_p >= 0.05 and kpss_p <= 0.05:
            out["stationary_hint"] = "no_estacionaria"
        else:
            out["stationary_hint"] = "mixta"

    return out


def build_stationarity_table(df: pd.DataFrame, version: str) -> pd.DataFrame:
    rows = []
    for col in VARS:
        row = stationarity_test(df[col])
        row["variable"] = col
        row["version"] = version
        rows.append(row)
    return pd.DataFrame(rows)[
        ["version", "variable", "n_obs", "adf_stat", "adf_pvalue", "kpss_stat", "kpss_pvalue", "stationary_hint"]
    ]


def detect_breakpoints(series: pd.Series, max_breaks: int = 3) -> list[int]:
    x = series.dropna().astype(float).to_numpy()
    if len(x) < 10:
        return []

    pen = 3 * np.log(len(x))
    algo = rpt.Pelt(model="l2").fit(x)
    bkps = algo.predict(pen=pen)
    bkps = [b for b in bkps if b < len(x)]
    return bkps[:max_breaks]


def build_breaks_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in VARS:
        s = df[["date", col]].dropna().reset_index(drop=True)
        bkps = detect_breakpoints(s[col])

        if not bkps:
            rows.append({
                "variable": col,
                "break_number": 0,
                "break_index": np.nan,
                "break_date": np.nan,
            })
        else:
            for i, b in enumerate(bkps, start=1):
                rows.append({
                    "variable": col,
                    "break_number": i,
                    "break_index": int(b),
                    "break_date": s.loc[b, "date"],
                })

    return pd.DataFrame(rows)


def save_series_plots(df: pd.DataFrame) -> None:
    for col in VARS:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df["date"], df[col])
        ax.set_title(col)
        ax.set_xlabel("Fecha")
        ax.set_ylabel("Valor")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(OUTDIR / f"serie_{col}.png", dpi=150)
        plt.close(fig)


def save_diff_series_plots(df_diff: pd.DataFrame, dates: pd.Series) -> None:
    for col in VARS:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(dates, df_diff[col])
        ax.set_title(f"{col} - primera diferencia")
        ax.set_xlabel("Fecha")
        ax.set_ylabel("Δ valor")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(OUTDIR / f"diff_{col}.png", dpi=150)
        plt.close(fig)


def fit_var(df_diff: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows = []
    fits = {}

    # muestra corta: solo lag 1 y 2
    for lag in [1]:
        try:
            model = VAR(df_diff)
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

    return pd.DataFrame(rows), fits


def _regularized_cholesky(sigma: np.ndarray, eps0: float = 1e-8, max_tries: int = 8):
    eps = eps0
    eye = np.eye(sigma.shape[0])

    for _ in range(max_tries):
        try:
            chol = np.linalg.cholesky(sigma + eps * eye)
            return chol, eps
        except np.linalg.LinAlgError:
            eps *= 10

    raise np.linalg.LinAlgError("No se pudo regularizar sigma_u para Cholesky.")


def export_irf(best_fit) -> str:
    names = best_fit.names

    try:
        irf = best_fit.irf(8)
        values = irf.irfs
        fig = irf.plot(orth=False)
        fig.savefig(OUTDIR / "irf_plot.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        method = "standard_irf"

    except np.linalg.LinAlgError:
        P, eps = _regularized_cholesky(best_fit.sigma_u)
        irf = best_fit.irf(8, var_decomp=P)
        values = irf.irfs
        fig = irf.plot(orth=False)
        fig.savefig(OUTDIR / "irf_plot.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        method = f"regularized_cholesky_eps_{eps}"

    rows = []
    for h in range(values.shape[0]):
        for i, impulse in enumerate(names):
            for j, response in enumerate(names):
                rows.append({
                    "horizon": h,
                    "impulse": impulse,
                    "response": response,
                    "value": values[h, j, i],
                    "method": method,
                })

    pd.DataFrame(rows).to_csv(OUTDIR / "irf_values.csv", index=False)
    return method


def main() -> None:
    ensure_dir(OUTDIR)

    df = load_panel()
    df.to_parquet(OUTDIR / "analysis_base.parquet", index=False)

    save_series_plots(df)

    stat_levels = build_stationarity_table(df, "levels")
    stat_levels.to_csv(OUTDIR / "stationarity_levels.csv", index=False)

    df_diff = df[["date"] + VARS].copy()
    for col in VARS:
        df_diff[col] = df_diff[col].diff()

    df_diff = df_diff.dropna().reset_index(drop=True)
    stat_diff = build_stationarity_table(df_diff, "diff_1")
    stat_diff.to_csv(OUTDIR / "stationarity_diff1.csv", index=False)

    save_diff_series_plots(df_diff, df_diff["date"])

    breaks_df = build_breaks_table(df)
    breaks_df.to_csv(OUTDIR / "breakpoints.csv", index=False)

    model_df = df_diff[VARS].copy()
    var_grid, fits = fit_var(model_df)
    var_grid.to_csv(OUTDIR / "var_lag_grid.csv", index=False)

    ok_grid = var_grid[var_grid["status"] == "ok"].copy()
    if ok_grid.empty:
        raise RuntimeError("No se pudo ajustar ningún VAR.")

    stable_grid = ok_grid[ok_grid["stable"] == True].copy()
    candidates = stable_grid if not stable_grid.empty else ok_grid

    best_lag = int(candidates.sort_values(["bic", "aic"]).iloc[0]["lag"])
    best_fit = fits[best_lag]

    irf_method = export_irf(best_fit)

    summary = {
        "input": str(INPUT),
        "variables": VARS,
        "n_rows_analysis": int(len(df)),
        "n_rows_diff": int(len(df_diff)),
        "best_lag": best_lag,
        "irf_method": irf_method,
        "report_dir": str(OUTDIR),
    }

    with open(OUTDIR / "hito4_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n✅ Hito 4 v2 ejecutado correctamente")
    print(f"Reportes en: {OUTDIR}")
    print(f"Mejor lag: {best_lag}")
    print(f"IRF method: {irf_method}")


if __name__ == "__main__":
    main()