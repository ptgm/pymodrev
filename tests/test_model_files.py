"""
Integration test suite that replicates scripts/run_tests.sh using pytest.

Each test case:
1. Discovers an example directory with model.*, observation files, and output.txt
2. Runs `main.py` via subprocess (using the venv with all dependencies)
3. Compares the output against output.txt using scripts/compare_outputs.py
"""

import subprocess
import tempfile
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SUPPORTED_EXTENSIONS = {".lp", ".bnet", ".ginml", ".zginml"}

def discover_examples():
    """
    Finds all example directories (examples/*/*/) that contain:
    - model.* (where * is a supported extension)
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
                    output_txt = example_dir / "output.txt"
                    if not output_txt.exists():
                        continue

                    model_files = []
                    for ext in SUPPORTED_EXTENSIONS:
                        candidate = example_dir / f"model{ext}"
                        if candidate.exists():
                            model_files.append(candidate)

                    if model_files:
                        obs_files = [
                            f for f in example_dir.iterdir()
                            if f.suffix == ".lp" and f.name != "model.lp"
                        ]
                        if obs_files:
                            for mf in model_files:
                                valid_dirs.append((example_dir, mf))

    return valid_dirs

def pytest_generate_tests(metafunc):
    """Dynamically parametrize tests from example directories."""
    if "example_data" in metafunc.fixturenames:
        examples = discover_examples()
        ids = [f"{d[0].relative_to(PROJECT_ROOT)}/{d[1].name}" for d in examples]
        metafunc.parametrize("example_data", examples, ids=ids)

def test_example_output(example_data, venv_python: str):
    """
    Runs main.py on the example directory and compares output
    against the expected output.txt using compare_outputs.py.
    """
    example_dir, model_file_path = example_data
    model_file = str(model_file_path)
    output_txt = str(example_dir / "output.txt")

    # Build observation arguments (same logic as run_tests.sh)
    obs_args = []
    for obs_file in sorted(example_dir.iterdir()):
        if obs_file.suffix == ".lp" and obs_file.name != "model.lp":
            base = obs_file.stem           # e.g. "async_1" or "steadystate"
            typology = base.split("_")[0]   # e.g. "async" or "steadystate"
            obs_args.extend([str(obs_file), f"{typology}updater"])

    # Run main.py and capture stdout to a temp file
    cmd = [venv_python, "main.py", "-m", model_file, "-obs"] + obs_args + ["-v", "0"] + ["-t", "r"] + ["--sub-opt"]
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
            f"{cmp_result.stdout}\n"
            f"---\n"
            f"Command run: {' '.join(cmd)}\n"
            f"Process stderr: {result.stderr}\n"
        )
    finally:
        os.unlink(tmp_path)
