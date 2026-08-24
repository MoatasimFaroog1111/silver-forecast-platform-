from __future__ import annotations

from pathlib import Path
import pandas as pd


class WalkForwardResultCatalog:
    def __init__(self, directory: Path):
        self._summary_path = directory / 'silver_stage10_walk_forward_summary.csv'
        self._detail_path = directory / 'silver_stage10_walk_forward_all_folds.csv'
        self._shortlist_path = directory / 'silver_stage10_ensemble_shortlist.csv'

    def summary(self, horizon: int | None = None) -> list[dict]:
        frame = pd.read_csv(self._summary_path)
        if horizon is not None:
            frame = frame[frame['Horizon_D'] == horizon]
        return frame.replace({float('nan'): None}).to_dict(orient='records')

    def fold_detail(self, horizon: int | None = None, limit: int = 500) -> list[dict]:
        frame = pd.read_csv(self._detail_path)
        if horizon is not None:
            frame = frame[frame['Horizon_D'] == horizon]
        frame = frame.head(limit)
        return frame.replace({float('nan'): None}).to_dict(orient='records')

    def ensemble_shortlist(self, horizon: int | None = None) -> list[dict]:
        frame = pd.read_csv(self._shortlist_path)
        if horizon is not None:
            frame = frame[frame['Horizon_D'] == horizon]
        return frame.replace({float('nan'): None}).to_dict(orient='records')
