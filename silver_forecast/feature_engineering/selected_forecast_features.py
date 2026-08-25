from __future__ import annotations

import json
from pathlib import Path


def load_selected_forecast_features(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    features = list(payload['features'])
    if payload.get('feature_count') != len(features):
        raise ValueError('Selected feature manifest count does not match feature list.')
    if any(name.startswith('Target_') for name in features):
        raise ValueError('Target leakage detected in selected feature manifest.')
    return features
