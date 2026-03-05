"""
Generate Cool Analytics Charts

Creates PNG charts in reports/:
- overlay_plot.png: investment vs GDP construction vs employment (normalized)
- correlation_heatmap.png
- lag_correlation_plot.png
- anomalies_plot.png
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from typing import Dict

from src.etl.utils import setup_logging


# ============================================================================
# Directory Paths
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
GOLD = BASE_DIR / "data" / "gold"
REPORTS = BASE_DIR / "reports"
LOGS = BASE_DIR / "logs"


def load_gold_data() -> Dict[str, pd.DataFrame]:
    """Load gold tables."""
    return {
        'panel': pd.read_parquet(GOLD / "national_panel.parquet"),
        'metrics': pd.read_parquet(GOLD / "metrics_summary.parquet"),
        'dim_indicator': pd.read_parquet(GOLD / "dim_indicator.parquet")
    }


def create_overlay_plot(panel: pd.DataFrame) -> None:
    """Overlay plot: investment vs GDP construction vs employment (normalized)."""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Normalize to 100 at first year
    base_year = panel['year'].min()
    for col in ['inv_pib', 'pib_const', 'empleo_const']:
        if col in panel.columns:
            base_val = panel.loc[panel['year'] == base_year, col].values[0]
            if pd.notna(base_val) and base_val != 0:
                panel[f'{col}_norm'] = (panel[col] / base_val) * 100
                ax.plot(panel['year'], panel[f'{col}_norm'], label=col, marker='o')
    
    ax.set_title('Infrastructure Indicators - Normalized Index (Base=100)')
    ax.set_xlabel('Year')
    ax.set_ylabel('Index')
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(REPORTS / "overlay_plot.png", dpi=150)
    plt.close()


def create_correlation_heatmap(panel: pd.DataFrame) -> None:
    """Correlation heatmap."""
    numeric_cols = panel.select_dtypes(include=[np.number]).columns
    corr = panel[numeric_cols].corr()
    
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(corr, annot=True, cmap='coolwarm', ax=ax)
    ax.set_title('Correlation Heatmap - Infrastructure Indicators')
    plt.tight_layout()
    plt.savefig(REPORTS / "correlation_heatmap.png", dpi=150)
    plt.close()


def create_lag_correlation_plot(metrics: pd.DataFrame) -> None:
    """Lag correlation plot."""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # For investment vs GDP/employment lags
    inv_data = metrics[metrics['indicator_id'] == 'inv_pib'].set_index('date')['value']
    gdp_data = metrics[metrics['indicator_id'] == 'pib_const'].set_index('date')['value']
    emp_data = metrics[metrics['indicator_id'] == 'empleo_const'].set_index('date')['value']
    
    lags = range(-4, 5)
    gdp_corr = [inv_data.corr(gdp_data.shift(lag)) for lag in lags]
    emp_corr = [inv_data.corr(emp_data.shift(lag)) for lag in lags]
    
    ax.plot(lags, gdp_corr, label='Investment vs GDP Construction', marker='o')
    ax.plot(lags, emp_corr, label='Investment vs Employment', marker='s')
    
    ax.axhline(0, color='black', linestyle='--')
    ax.set_title('Cross-Correlation: Investment Leading Indicators')
    ax.set_xlabel('Lag (quarters)')
    ax.set_ylabel('Correlation')
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(REPORTS / "lag_correlation_plot.png", dpi=150)
    plt.close()


def create_anomalies_plot(metrics: pd.DataFrame) -> None:
    """Anomalies/outliers plot."""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    for ind in ['inv_pib', 'pib_const', 'empleo_const']:
        ind_data = metrics[metrics['indicator_id'] == ind]
        if not ind_data.empty:
            ax.plot(ind_data['date'], ind_data['value'], label=ind, alpha=0.7)
            # Flag structural breaks
            breaks = ind_data[ind_data.get('structural_break_flag', 0) == 1]
            if not breaks.empty:
                ax.scatter(breaks['date'], breaks['value'], color='red', s=50, label=f'{ind} breaks')
    
    ax.set_title('Infrastructure Indicators with Structural Break Flags')
    ax.set_xlabel('Date')
    ax.set_ylabel('Value')
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(REPORTS / "anomalies_plot.png", dpi=150)
    plt.close()


def main():
    logger = setup_logging(LOGS / "reports.log", name="reports")
    logger.info("Generating analytics charts")
    
    try:
        data = load_gold_data()
        
        create_overlay_plot(data['panel'])
        logger.info("✅ Overlay plot created")
        
        create_correlation_heatmap(data['panel'])
        logger.info("✅ Correlation heatmap created")
        
        create_lag_correlation_plot(data['metrics'])
        logger.info("✅ Lag correlation plot created")
        
        create_anomalies_plot(data['metrics'])
        logger.info("✅ Anomalies plot created")
        
        logger.info("✅ All charts generated in reports/")
    except Exception as e:
        logger.error(f"❌ Report generation failed: {e}", exc_info=True)


if __name__ == "__main__":
    main()