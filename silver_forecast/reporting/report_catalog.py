from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReportEntry:
    name: str
    title: str
    category: str
    path: Path

    @property
    def content_type(self) -> str:
        suffix = self.path.suffix.lower()
        return {
            '.csv': 'text/csv',
            '.json': 'application/json',
            '.zip': 'application/zip',
        }.get(suffix, 'application/octet-stream')


class ReportCatalog:
    def __init__(self, reports_directory: Path, backtesting_directory: Path):
        self._entries: dict[str, ReportEntry] = {}
        self._load_directory(reports_directory, 'verified-report')
        self._load_directory(backtesting_directory, 'backtesting')

    def _load_directory(self, directory: Path, category: str) -> None:
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            name = path.name
            self._entries[name] = ReportEntry(
                name=name,
                title=name.replace('_', ' ').replace('-', ' ').rsplit('.', 1)[0].title(),
                category=category,
                path=path,
            )

    def list(self) -> list[dict]:
        return [
            {
                'name': entry.name,
                'title': entry.title,
                'category': entry.category,
                'download_url': f'/api/reports/{entry.name}',
            }
            for entry in self._entries.values()
        ]

    def get(self, name: str) -> ReportEntry:
        if name not in self._entries:
            raise KeyError(name)
        return self._entries[name]
