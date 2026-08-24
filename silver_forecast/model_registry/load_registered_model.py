from __future__ import annotations

from pathlib import Path
import joblib


class RegisteredModelLoader:
    def __init__(self, models_directory: Path):
        self._models_directory = models_directory
        self._cache: dict[str, dict] = {}

    def load(self, artifact_name: str) -> dict:
        if artifact_name not in self._cache:
            path = self._models_directory / artifact_name
            if not path.exists():
                raise FileNotFoundError(f'Forecast model artifact is missing: {path}')
            payload = joblib.load(path)
            if 'model' not in payload or 'prediction_mode' not in payload:
                raise ValueError(f'Invalid model artifact contract: {artifact_name}')
            self._cache[artifact_name] = payload
        return self._cache[artifact_name]

    def health(self, artifact_names: list[str]) -> dict:
        failures = []
        for name in artifact_names:
            try:
                self.load(name)
            except Exception as exc:  # pragma: no cover - reported through health endpoint
                failures.append({'artifact': name, 'error': f'{type(exc).__name__}: {exc}'})
        return {'loadable': not failures, 'failures': failures, 'loaded_count': len(self._cache)}
