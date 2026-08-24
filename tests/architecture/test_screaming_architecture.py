from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[2]


def test_forbidden_generic_buckets_do_not_exist():
    forbidden = {'components', 'assets', 'services', 'utils', 'helpers'}
    found = {path.name for path in ROOT.rglob('*') if path.is_dir() and path.name in forbidden}
    assert not found, f'Generic architecture buckets found: {sorted(found)}'


def test_forecasting_domain_does_not_depend_on_outer_frameworks():
    forbidden_roots = {'fastapi', 'sqlalchemy', 'joblib', 'catboost', 'xgboost', 'lightgbm'}
    violations = []
    for path in (ROOT / 'silver_forecast' / 'forecasting').glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split('.')[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split('.')[0]]
            else:
                continue
            for name in names:
                if name in forbidden_roots:
                    violations.append(f'{path.name}: {name}')
    assert not violations, violations
