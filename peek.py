import pandas as pd

panel = pd.read_parquet('data/gold/national_panel.parquet')
metrics = pd.read_parquet('data/gold/metrics_summary.parquet')
print('national_panel sample:')
print(panel.head().to_string(index=False))
print() 
print('metrics_summary sample:')
print(metrics.head().to_string(index=False))
