"""
GOLD LAYER: Analytics & Feature Engineering

Creates star-schema for analytics:
- dim_time.parquet
- dim_indicator.parquet
- fact_indicators.parquet
- national_panel.parquet (wide format)
- metrics_summary.parquet (with YoY, rolling, lags, structural breaks)
"""

from pathlib import Path
import pandas as pd
import numpy as np
import logging
from typing import Dict

from .utils import setup_logging


# ============================================================================
# Directory Paths
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SILVER = BASE_DIR / "data" / "silver"
GOLD = BASE_DIR / "data" / "gold"
LOGS = BASE_DIR / "logs"

GOLD.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Key Indicators for Feature Engineering
# ============================================================================

KEY_INDICATORS = ['inv_pib', 'pib_const', 'empleo_const']


def create_dim_time(df: pd.DataFrame) -> pd.DataFrame:
    """Create time dimension."""
    time_df = df[['year', 'quarter']].drop_duplicates().sort_values(['year', 'quarter'])
    time_df['period_id'] = range(1, len(time_df) + 1)
    time_df['period_label'] = time_df.apply(
        lambda x: f"{int(x['year'])}Q{int(x['quarter'])}" if pd.notna(x['quarter']) else str(int(x['year'])),
        axis=1
    )
    return time_df[['period_id', 'year', 'quarter', 'period_label']]


def create_dim_indicator(df: pd.DataFrame) -> pd.DataFrame:
    """Create indicator dimension."""
    ind_df = df[['indicator_id', 'source', 'unit', 'frequency']].drop_duplicates()
    # Add descriptions
    descriptions = {
        'inv_pib': 'Investment in fixed capital formation - construction',
        'empleo_const': 'Employment in construction sector',
        'pib_const': 'GDP contribution from construction',
        'iioc': 'Construction cost index',
        'gasto_const': 'Constant public spending on infrastructure',
        'logistics_lpi': 'Logistics performance index',
        'inv_proyectos': 'Infrastructure investment projects value'
    }
    ind_df['description'] = ind_df['indicator_id'].map(descriptions).fillna('Unknown')
    return ind_df


def create_fact_indicators(df: pd.DataFrame, dim_time: pd.DataFrame) -> pd.DataFrame:
    """Create fact table."""
    fact = df.merge(dim_time, on=['year', 'quarter'], how='left')
    fact = fact[['period_id', 'indicator_id', 'value']]
    return fact


def create_national_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Create wide panel with year/quarter index."""
    panel = df.pivot_table(
        index=['year', 'quarter'],
        columns='indicator_id',
        values='value',
        aggfunc='first'
    ).reset_index()
    panel['period'] = panel.apply(
        lambda x: f"{int(x['year'])}Q{int(x['quarter'])}" if pd.notna(x['quarter']) else str(int(x['year'])),
        axis=1
    )
    return panel


def add_feature_engineering(panel: pd.DataFrame) -> pd.DataFrame:
    """Add YoY growth, rolling means, lags, structural breaks."""
    metrics = panel.copy()
    
    for ind in KEY_INDICATORS:
        if ind in metrics.columns:
            # YoY growth
            metrics[f'{ind}_yoy'] = metrics[ind].pct_change(4 if 'Q' in str(metrics['period'].iloc[0]) else 1) * 100
            
            # Rolling mean (4 quarters or 3 years)
            window = 4 if 'Q' in str(metrics['period'].iloc[0]) else 3
            metrics[f'{ind}_rolling'] = metrics[ind].rolling(window=window, min_periods=1).mean()
            
            # Lags
            for lag in [1, 2, 3]:
                metrics[f'{ind}_lag{lag}'] = metrics[ind].shift(lag)
    
    # Structural breaks: flag if rolling z-score > 2
    for ind in KEY_INDICATORS:
        if ind in metrics.columns:
            rolling_mean = metrics[ind].rolling(window=8, min_periods=4).mean()
            rolling_std = metrics[ind].rolling(window=8, min_periods=4).std()
            z_score = (metrics[ind] - rolling_mean) / rolling_std
            metrics[f'{ind}_break_flag'] = (z_score.abs() > 2).astype(int)
    
    return metrics


def main():
    logger = setup_logging(LOGS / "gold.log", name="gold")
    logger.info("GOLD STAGE: Creating analytics layer")
    
    silver_file = SILVER / "indicators_tidy.parquet"
    if not silver_file.exists():
        logger.error("Silver data not found")
        return
    
    df = pd.read_parquet(silver_file)
    
    # Create dimensions
    dim_time = create_dim_time(df)
    dim_indicator = create_dim_indicator(df)
    
    # Create fact
    fact = create_fact_indicators(df, dim_time)
    
    # Create panel
    panel = create_national_panel(df)
    
    # Feature engineering
    metrics = add_feature_engineering(panel)
    
    # Save all
    dim_time.to_parquet(GOLD / "dim_time.parquet", index=False)
    dim_indicator.to_parquet(GOLD / "dim_indicator.parquet", index=False)
    fact.to_parquet(GOLD / "fact_indicators.parquet", index=False)
    panel.to_parquet(GOLD / "national_panel.parquet", index=False)
    metrics.to_parquet(GOLD / "metrics_summary.parquet", index=False)
    
    logger.info("✅ GOLD layer created")
    logger.info(f"Time periods: {len(dim_time)}")
    logger.info(f"Indicators: {len(dim_indicator)}")
    logger.info(f"Fact rows: {len(fact)}")


if __name__ == "__main__":
    main()