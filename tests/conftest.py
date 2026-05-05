"""
Pytest configuration for integration tests.

Provides a session-scoped fixture that detects the active Python environment.
Works with both virtual environments and system Python without requiring
the project to be installed — the src/ directory is added to PYTHONPATH.
"""

import importlib.util
import os
import re
from pathlib import Path
import pytest

venv_dir = os.environ.get("VIRTUAL_ENV")

def get_required_packages(requirements_path: Path):
    packages = ["pymodrev"]
    pattern = re.compile(r'^([a-zA-Z0-9\-_]+)')
    with open(requirements_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            match = pattern.match(line)
            if match: packages.append(match.group(1))
    return packages

def check_package_resolvable(package_name: str):
    return importlib.util.find_spec(package_name.replace('-', '_')) is not None


@pytest.fixture(scope="session")
def venv_python():
    return str(Path(venv_dir) / "bin" / "python3")

def pytest_sessionstart(session):
    if not venv_dir:
        error_msg = (
            f"\nFATAL: Variable VIRTUAL_ENV not found.\n"
            f"Create and activate a virtual environment before running tests:\n"
            f"  python3 -m venv .venv\n"
            f"  source .venv/bin/activate"
        )
        pytest.exit(reason=error_msg, returncode=1)

    req_file = Path(session.config.rootdir) / "requirements.txt"
    required_packages = get_required_packages(req_file)
    missing = [pkg for pkg in required_packages if not check_package_resolvable(pkg)]

    if missing:
        error_log = (
            f"\n[FATAL] Dependencies missing in environment.\n"
            f"Missing Packages: {', '.join(missing)}\n"
            f"Resolution: Execute 'pip install -r requirements.txt' within the target environment."
        )
        pytest.exit(reason=error_log, returncode=1)
