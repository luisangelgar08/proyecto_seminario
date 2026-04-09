# Data Quality Report

**Generated**: 2026-03-05T20:54:11.571895

**Dataset**: data\silver\indicators_tidy.parquet
**Rows**: 688 | **Columns**: 6 | **Indicators**: 8

## Check Results

### schema_validation ✅ PASS
```
OK
```

### missingness ✅ PASS
```
{'date': {'null_count': 0, 'null_pct': 0.0, 'exceeded_threshold': np.False_}, 'value': {'null_count': 0, 'null_pct': 0.0, 'exceeded_threshold': np.False_}, 'indicator': {'null_count': 0, 'null_pct': 0.0, 'exceeded_threshold': np.False_}, 'source': {'null_count': 0, 'null_pct': 0.0, 'exceeded_threshold': np.False_}, 'unit': {'null_count': 0, 'null_pct': 0.0, 'exceeded_threshold': np.False_}, 'frequency': {'null_count': 0, 'null_pct': 0.0, 'exceeded_threshold': np.False_}}
```

### uniqueness_date_indicator ✅ PASS
```
{'key_columns': ['date', 'indicator'], 'total_rows': 688, 'unique_rows': 688, 'n_duplicates': 0, 'failed': False}
```

### time_consistency ✅ PASS
```
{'min_date': '1999-03-31 00:00:00', 'max_date': '2023-12-31 00:00:00', 'n_rows': 688, 'null_dates': 0, 'min_gap_days': 0, 'max_gap_days': 92, 'negative_gaps': 0, 'failed': False}
```

### value_ranges ✅ PASS
```
{'column': 'value', 'non_numeric': 0, 'min': 1.9996357124675184, 'max': 21319.543752303427, 'violations': [], 'failed': False}
```

### outliers ✅ PASS
```
{'column': 'value', 'method': 'IQR', 'q1': 38.28790116514462, 'q3': 174.14718719736106, 'iqr': 135.85928603221646, 'lower_bound': -165.5010278831801, 'upper_bound': 377.93611624568575, 'n_outliers': 160, 'pct_outliers': 23.25581395348837}
```


## Summary

- Checks passed: **6/6**
- Overall status: **✅ All checks passed**