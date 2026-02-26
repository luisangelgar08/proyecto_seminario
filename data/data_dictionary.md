# Diccionario de datos - Hito 2

## Dataset
- Archivo: `data/processed/indicators_tidy.csv`
- Grano: 1 fila = (date, indicator)

## Columnas
- **date** (datetime): fecha del dato.
- **value** (float): valor numérico del indicador.
- **indicator** (string): nombre del indicador.
- **source** (string): fuente oficial.
- **unit** (string): unidad reportada/interpretada.
- **frequency** (string): mensual o trimestral.

## Indicadores incluidos
- FBCF - Otros edificios y estructuras (AN112) [Trimestral]
- GEIH - Ocupados (Construcción) [Mensual]
- IIOC - Total [Trimestral]
- IIOC - 4001 (vías/carreteras/puentes) [Trimestral]
- IIOC - 4002 (férreas/aeropuertos/transporte masivo) [Trimestral]
- IIOC - 4003 (puertos/represas/acueductos/alcantarillado) [Trimestral]
- IIOC - 4004 (minería/tuberías) [Trimestral]
- IIOC - 4008 (otras obras de ingeniería) [Trimestral]

## Fuentes
- DANE - GEIH (ramas CIIU 4)
- DANE - Cuentas Nacionales (FBCF por tipo de activo, Cuadro 5)
- DANE - IIOC (Anexo A3)