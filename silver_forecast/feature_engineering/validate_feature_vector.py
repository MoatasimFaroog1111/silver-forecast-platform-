from __future__ import annotations

import numpy as np
import pandas as pd


def validate_latest_feature_vector(frame: pd.DataFrame, selected_features: list[str]) -> pd.DataFrame:
    missing_columns = [name for name in selected_features if name not in frame.columns]
    if missing_columns:
        raise ValueError(f'Missing selected features: {missing_columns}')
    latest = frame.iloc[[-1]][selected_features].astype(float)
    missing_values = [name for name in selected_features if latest[name].isna().any()]
    if missing_values:
        raise ValueError(f'Latest observation is not prediction-ready. Missing: {missing_values}')
    values = latest.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError('Latest feature vector contains non-finite values.')
    return latest.astype(np.float64)
