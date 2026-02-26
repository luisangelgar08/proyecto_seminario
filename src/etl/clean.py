from pathlib import Path
import pandas as pd
import numpy as np

RAW = Path("data/raw")
OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)

MONTH_MAP = {
    "Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Ago": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dic": 12
}
Q_MAP = {"I": 1, "II": 2, "III": 3, "IV": 4}

def to_tidy(dates, values, indicator, source, unit, frequency):
    df = pd.DataFrame({"date": dates, "value": values})
    df["indicator"] = indicator
    df["source"] = source
    df["unit"] = unit
    df["frequency"] = frequency
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["date"])
    return df

def parse_fbcf_an112_other_buildings(file_path: Path):
    # row 9 = años, row 10 = trimestres, row 12.. = datos, y luego se repite otro bloque (variaciones)
    df = pd.read_excel(file_path, sheet_name="Cuadro 5", header=None)

    # 1) Encuentra la fila "Clasificación Cuentas Nacionales | Concepto | 2005 ..."
    def is_year_header_row(i):
        c0 = str(df.iat[i, 0]).strip()
        c1 = str(df.iat[i, 1]).strip()
        c2 = df.iat[i, 2]
        return (c0 == "Clasificación Cuentas Nacionales") and (c1 == "Concepto") and pd.notna(pd.to_numeric(c2, errors="coerce"))

    year_row_candidates = [i for i in range(min(80, len(df))) if is_year_header_row(i)]
    if not year_row_candidates:
        raise ValueError("No encontré header de años en Cuadro 5. Revisa el archivo.")
    year_row = year_row_candidates[0]
    q_row = year_row + 1

    years = pd.to_numeric(df.iloc[year_row, 2:], errors="coerce").ffill()
    quarters = df.iloc[q_row, 2:].astype(str).str.strip().map(Q_MAP)

    # Determina fin del bloque 
    start = year_row + 2
    end_candidates = df.index[(df.index > start) & (df.iloc[:, 0].astype(str).str.strip() == "Clasificación Cuentas Nacionales")]
    end = int(end_candidates.min()) if len(end_candidates) else len(df)

    block = df.iloc[start:end].copy()

    # Fila AN112
    code_col = block.iloc[:, 0].astype(str).str.strip()
    concept_col = block.iloc[:, 1].astype(str).str.strip()
    mask = (code_col == "AN112") & (concept_col.str.contains("Otros edificios y estructuras", case=False, na=False))
    if not mask.any():
        # Si no matchea el texto completo, al menos por código:
        mask = (code_col == "AN112")
    row = block.loc[mask].iloc[0]

    values = pd.to_numeric(row.iloc[2:], errors="coerce")
    tmp = pd.DataFrame({
        "year": years.values,
        "q": quarters.values,
        "value": values.values,
        "colpos": range(len(values))  # posición de la columna (izq → der)
    }).dropna(subset=["year", "q", "value"])
    tmp = tmp.sort_values("colpos").drop_duplicates(subset=["year", "q"], keep="first")

    
    tmp["period"] = tmp["year"].astype(int).astype(str) + "Q" + tmp["q"].astype(int).astype(str)
    dates = pd.PeriodIndex(tmp["period"], freq="Q").to_timestamp(how="end").normalize()

    return to_tidy(
        dates=dates,
        values=tmp["value"].values,
        indicator="FBCF - Otros edificios y estructuras (AN112)",
        source="DANE - Cuentas Nacionales (Cuadro 5)",
        unit="(según anexo, valores en constantes)",
        frequency="Trimestral"
    )

def parse_geih_ocupados_construccion(file_path: Path):
    # Tu inspector mostró:
    # row 12 = 'Concepto' + año (2015...), row 13 = meses, row 15.. = filas por rama (incluye 'Construcción')
    sh = "ocup ramas mes tnal CIIU 4"
    df = pd.read_excel(file_path, sheet_name=sh, header=None)

    c0 = df.iloc[:, 0].astype(str).str.strip()
    c1_num = pd.to_numeric(df.iloc[:, 1], errors="coerce")

    year_row_candidates = df.index[(c0 == "Concepto") & c1_num.notna()].tolist()
    if not year_row_candidates:
        raise ValueError("No encontré header 'Concepto' + año en GEIH (ocup ramas mes...).")
    year_row = year_row_candidates[0]
    month_row = year_row + 1
    data_start = month_row + 1

    years = pd.to_numeric(df.iloc[year_row, 1:], errors="coerce").ffill()
    months = df.iloc[month_row, 1:].astype(str).str.strip()
    month_num = months.map(MONTH_MAP)

    valid = years.notna() & month_num.notna()
    years_v = years[valid].astype(int).tolist()
    months_v = month_num[valid].astype(int).tolist()

    # Recorta la matriz de datos a columnas válidas
    col_idx = (np.where(valid.values)[0] + 1).tolist()  # +1 porque empezamos en col 1
    data = df.iloc[data_start:, [0] + col_idx].copy()
    data = data[data.iloc[:, 0].notna()]

    concept = data.iloc[:, 0].astype(str).str.strip()
    row = data.loc[concept == "Construcción"]
    if row.empty:
        raise ValueError("No encontré la fila 'Construcción' en la GEIH. Revisa nombres exactos.")
    row = row.iloc[0]

    values = pd.to_numeric(row.iloc[1:].values, errors="coerce")
    dates = [pd.Timestamp(year=y, month=m, day=1) for y, m in zip(years_v, months_v)]

    return to_tidy(
        dates=dates,
        values=values,
        indicator="GEIH - Ocupados (Construcción)",
        source="DANE - GEIH (ramas CIIU4, mensual)",
        unit="Miles de personas (ver anexo)",
        frequency="Mensual"
    )

def parse_iioc_anexo_a3(file_path: Path):
    # row 11 = header ('Año','Trimestre','Total IIOC'...), row 12 = nombres 4001..4008, row 13.. datos
    sh = "Anexo A3"
    df = pd.read_excel(file_path, sheet_name=sh, header=None)

    col1 = df.iloc[:, 1].astype(str).str.strip()
    col2 = df.iloc[:, 2].astype(str).str.strip()
    header_candidates = df.index[(col1 == "Año") & (col2 == "Trimestre")].tolist()
    if not header_candidates:
        raise ValueError("No encontré header Año/Trimestre en IIOC Anexo A3.")
    header_row = header_candidates[0]
    label_row = header_row + 1
    data_start = header_row + 2

    # Columnas esperadas
    sub = df.iloc[data_start:, 1:9].copy()
    sub.columns = ["year", "quarter", "iioc_total", "c4001", "c4002", "c4003", "c4004", "c4008"]

    # Año viene “ffill” por bloques
    sub["year"] = pd.to_numeric(sub["year"], errors="coerce").ffill()
    sub["quarter"] = sub["quarter"].astype(str).str.strip().map(Q_MAP)

    # Valores numéricos
    for c in ["iioc_total", "c4001", "c4002", "c4003", "c4004", "c4008"]:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")

    sub = sub.dropna(subset=["year", "quarter"])
    sub["period"] = sub["year"].astype(int).astype(str) + "Q" + sub["quarter"].astype(int).astype(str)
    dates = pd.PeriodIndex(sub["period"], freq="Q").to_timestamp(how="end").normalize()

    out = []
    out.append(to_tidy(dates, sub["iioc_total"].values, "IIOC - Total", "DANE - IIOC (Anexo A3)", "Índice", "Trimestral"))
    out.append(to_tidy(dates, sub["c4001"].values, "IIOC - 4001 (vías/carreteras/puentes)", "DANE - IIOC (Anexo A3)", "Índice", "Trimestral"))
    out.append(to_tidy(dates, sub["c4002"].values, "IIOC - 4002 (férreas/aeropuertos/transporte masivo)", "DANE - IIOC (Anexo A3)", "Índice", "Trimestral"))
    out.append(to_tidy(dates, sub["c4003"].values, "IIOC - 4003 (puertos/represas/acueductos/alcantarillado)", "DANE - IIOC (Anexo A3)", "Índice", "Trimestral"))
    out.append(to_tidy(dates, sub["c4004"].values, "IIOC - 4004 (minería/tuberías)", "DANE - IIOC (Anexo A3)", "Índice", "Trimestral"))
    out.append(to_tidy(dates, sub["c4008"].values, "IIOC - 4008 (otras obras de ingeniería)", "DANE - IIOC (Anexo A3)", "Índice", "Trimestral"))

    return pd.concat(out, ignore_index=True)

def main():
    f_fbcf = RAW / "anex-GastoConstantes-IVtrim2025.xlsx"
    f_geih = RAW / "anexo-mercado-laboral-segun-proyecciones-CNPV2018.xlsx"
    f_iioc = RAW / "anexos_IIOC_IVtrim20.xlsx"

    dfs = []
    dfs.append(parse_fbcf_an112_other_buildings(f_fbcf))
    dfs.append(parse_geih_ocupados_construccion(f_geih))
    dfs.append(parse_iioc_anexo_a3(f_iioc))

    tidy = pd.concat(dfs, ignore_index=True)

    # Limpieza mínima
    tidy["indicator"] = tidy["indicator"].astype(str).str.strip()
    tidy = tidy.dropna(subset=["value"])

    out_csv = OUT / "indicators_tidy.csv"
    out_parq = OUT / "indicators_tidy.parquet"
    tidy.to_csv(out_csv, index=False)
    tidy.to_parquet(out_parq, index=False)

    print("OK ->", out_csv)
    print("OK ->", out_parq)
    print("Indicators:", tidy["indicator"].nunique())
    print("Date range:", tidy["date"].min(), "to", tidy["date"].max())

if __name__ == "__main__":
    main()