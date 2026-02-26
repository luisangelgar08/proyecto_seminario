from pathlib import Path
import pandas as pd

RAW_DIR = Path("data/raw")

TARGETS = {
    "anex-GastoConstantes-IVtrim2025.xlsx": ["Cuadro 5", "Cuadro 6"],
    "anexo-mercado-laboral-segun-proyecciones-CNPV2018.xlsx": [
        "ocup ramas mes tnal CIIU 4",
        "ocup ramas trim tnal CIIU 4 ",
    ],
    "anexos_IIOC_IVtrim20.xlsx": ["Anexo A1", "Anexo A2", "Anexo A3", "Anexo A4", "Anexo A5"],
}

def show_nonempty_rows(path: Path, sheet: str, max_rows=120, show_top=25):
    df = pd.read_excel(path, sheet_name=sheet, header=None, nrows=max_rows)
    nn = df.notna().sum(axis=1)
    # filas con "algo" de información
    idx = nn[nn >= 3].index.tolist()

    print(f"\n--- {path.name} | {sheet} ---")
    if not idx:
        print("No vi filas con >=3 celdas no-nulas en las primeras", max_rows, "filas.")
        print("Prueba subir max_rows a 300.")
        return

    # imprime las primeras filas relevantes con índice + primeras 12 columnas
    for i in idx[:show_top]:
        row = df.iloc[i, :12].tolist()
        print(f"[row {i:03d}] nonnull={int(nn.iloc[i])} -> {row}")

def main():
    for fn, sheets in TARGETS.items():
        path = RAW_DIR / fn
        if not path.exists():
            print("[FALTA]", path)
            continue
        for sh in sheets:
            try:
                show_nonempty_rows(path, sh)
            except Exception as e:
                print(f"\n--- {path.name} | {sh} --- ERROR:", e)

if __name__ == "__main__":
    main()