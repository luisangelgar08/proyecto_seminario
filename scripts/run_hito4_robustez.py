from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd
import ruptures as rpt
import matplotlib.pyplot as plt

from statsmodels.tsa.api import VAR


INPUT_MAIN = Path("data/gold/hito4_panel_main.parquet")
INPUT_IPOC = Path("data/gold/hito4_panel_ipoc.parquet")
OUTDIR = Path("reports/hito4_v2")
VARS_MAIN = ["iioc_total", "empleo_construccion"]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_panel(path: Path, vars_: list[str]) -> pd.DataFrame:
    df = pd.read_parquet(path).copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    missing = [c for c in vars_ if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas en {path}: {missing}")

    for c in vars_:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=vars_).reset_index(drop=True)
    return df


def detect_breakpoints(series: pd.Series, max_breaks: int = 3) -> list[int]:
    x = series.dropna().astype(float).to_numpy()
    if len(x) < 10:
        return []

    pen = 3 * np.log(len(x))
    algo = rpt.Pelt(model="l2").fit(x)
    bkps = algo.predict(pen=pen)
    bkps = [b for b in bkps if b < len(x)]
    return bkps[:max_breaks]


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


def export_irf(fit, prefix: str) -> str:
    try:
        irf = fit.irf(8)
        values = irf.irfs

        fig = irf.plot(orth=False)
        fig.savefig(OUTDIR / f"{prefix}_irf_plot.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

        method = "standard_irf"

    except np.linalg.LinAlgError:
        P, eps = _regularized_cholesky(fit.sigma_u)
        irf = fit.irf(8, var_decomp=P)
        values = irf.irfs

        fig = irf.plot(orth=False)
        fig.savefig(OUTDIR / f"{prefix}_irf_plot.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

        method = f"regularized_cholesky_eps_{eps}"

    rows = []
    names = fit.names
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

    pd.DataFrame(rows).to_csv(OUTDIR / f"{prefix}_irf_values.csv", index=False)
    return method


def run_var_spec(df: pd.DataFrame, spec_name: str, difference: bool) -> dict:
    work = df[VARS_MAIN].copy()

    if difference:
        work = work.diff().dropna().reset_index(drop=True)

    if len(work) < 8:
        return {
            "spec": spec_name,
            "difference": difference,
            "nobs": len(work),
            "stable": np.nan,
            "aic": np.nan,
            "bic": np.nan,
            "hqic": np.nan,
            "fpe": np.nan,
            "irf_method": "not_run",
            "status": "fail",
            "error": "muestra insuficiente",
        }

    try:
        model = VAR(work)
        fit = model.fit(1)

        try:
            stable = bool(fit.is_stable())
        except Exception:
            stable = np.nan

        irf_method = export_irf(fit, prefix=spec_name)

        return {
            "spec": spec_name,
            "difference": difference,
            "nobs": fit.nobs,
            "stable": stable,
            "aic": fit.aic,
            "bic": fit.bic,
            "hqic": fit.hqic,
            "fpe": fit.fpe,
            "irf_method": irf_method,
            "status": "ok",
            "error": "",
        }

    except Exception as e:
        return {
            "spec": spec_name,
            "difference": difference,
            "nobs": len(work),
            "stable": np.nan,
            "aic": np.nan,
            "bic": np.nan,
            "hqic": np.nan,
            "fpe": np.nan,
            "irf_method": "fail",
            "status": "fail",
            "error": str(e),
        }


def main() -> None:
    ensure_dir(OUTDIR)

    # Panel principal
    df_main = load_panel(INPUT_MAIN, VARS_MAIN)

    # Sensibilidad 1: VAR(1) en niveles
    res_levels = run_var_spec(df_main, spec_name="var_levels_lag1", difference=False)

    # Sensibilidad 2: VAR(1) en primeras diferencias
    res_diff = run_var_spec(df_main, spec_name="var_diff1_lag1", difference=True)

    robustness = pd.DataFrame([res_levels, res_diff])
    robustness.to_csv(OUTDIR / "robustness_summary.csv", index=False)

    # Correlaciones del panel principal
    corr = df_main[VARS_MAIN].corr()
    corr.to_csv(OUTDIR / "main_correlations.csv")

    # Quiebres IPOC por separado
    df_ipoc = load_panel(INPUT_IPOC, ["ipoc_total"])
    bkps = detect_breakpoints(df_ipoc["ipoc_total"], max_breaks=3)

    rows = []
    if not bkps:
        rows.append({
            "variable": "ipoc_total",
            "break_number": 0,
            "break_index": np.nan,
            "break_date": np.nan,
        })
    else:
        for i, b in enumerate(bkps, start=1):
            rows.append({
                "variable": "ipoc_total",
                "break_number": i,
                "break_index": int(b),
                "break_date": df_ipoc.loc[b, "date"],
            })

    pd.DataFrame(rows).to_csv(OUTDIR / "ipoc_breakpoints.csv", index=False)

    # Resumen final
    summary = {
        "main_panel_rows": int(len(df_main)),
        "main_panel_start": str(df_main["date"].min()),
        "main_panel_end": str(df_main["date"].max()),
        "main_variables": VARS_MAIN,
        "ipoc_rows": int(len(df_ipoc)),
        "ipoc_start": str(df_ipoc["date"].min()),
        "ipoc_end": str(df_ipoc["date"].max()),
    }

    with open(OUTDIR / "robustness_meta.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n✅ Robustez adicional de Hito 4 ejecutada")
    print(f"Reportes en: {OUTDIR}")


if __name__ == "__main__":
    main()