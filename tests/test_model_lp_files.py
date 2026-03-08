"""
Integration test suite that replicates scripts/run_tests.sh using pytest.

Each test case:
1. Discovers an example directory with model.lp, observation files, and output.txt
2. Runs `main.py` via subprocess (using the venv with all dependencies)
3. Compares the output against output.txt using scripts/compare_outputs.py
"""

import subprocess
import tempfile
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def discover_examples():
    """
    Finds all example directories (examples/*/*/) that contain:
    - model.lp
    - at least one observation .lp file (not model.lp)
    - output.txt
    """
    examples_dir = PROJECT_ROOT / "examples"
    if not examples_dir.exists():
        return []

    valid_dirs = []
    for category_dir in sorted(examples_dir.iterdir()):
        if category_dir.is_dir():
            for example_dir in sorted(category_dir.iterdir()):
                if example_dir.is_dir():
                    model_lp = example_dir / "model.lp"
                    output_txt = example_dir / "output.txt"

                    if model_lp.exists() and output_txt.exists():
                        obs_files = [
                            f for f in example_dir.iterdir()
                            if f.suffix == ".lp" and f.name != "model.lp"
                        ]
                        if obs_files:
                            valid_dirs.append(example_dir)

    return valid_dirs


def pytest_generate_tests(metafunc):
    """Dynamically parametrize tests from example directories."""
    if "example_dir" in metafunc.fixturenames:
        example_dirs = discover_examples()
        ids = [str(d.relative_to(PROJECT_ROOT)) for d in example_dirs]
        metafunc.parametrize("example_dir", example_dirs, ids=ids)


def test_example_output(example_dir: Path, venv_python: str):
    """
    Runs main.py on the example directory and compares output
    against the expected output.txt using compare_outputs.py.
    """
    model_file = str(example_dir / "model.lp")
    output_txt = str(example_dir / "output.txt")

    # Build observation arguments (same logic as run_tests.sh)
    obs_args = []
    for obs_file in sorted(example_dir.iterdir()):
        if obs_file.suffix == ".lp" and obs_file.name != "model.lp":
            base = obs_file.stem           # e.g. "async_1" or "steadystate"
            typology = base.split("_")[0]   # e.g. "async" or "steadystate"
            obs_args.extend([str(obs_file), f"{typology}updater"])

    # Run main.py and capture stdout to a temp file
    cmd = [venv_python, "main.py", "-m", model_file, "-obs"] + obs_args + ["-v", "0"]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )

    # Write stdout to a temp file for compare_outputs.py
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(result.stdout)
        tmp_path = tmp.name

    try:
        # Run compare_outputs.py
        cmp_result = subprocess.run(
            [venv_python, "tests/compare_outputs.py", tmp_path, output_txt],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )

        # compare_outputs.py prints differences to stdout if outputs diverge
        assert cmp_result.stdout.strip() == "", (
            f"Output mismatch for {example_dir.relative_to(PROJECT_ROOT)}:\n"
            f"{cmp_result.stdout}"
        )
    finally:
        os.unlink(tmp_path)
