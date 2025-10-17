import os
import sys
from pathlib import Path
import subprocess

def print_help(exit_code: int = 0) -> None:
    script = Path(__file__).name
    msg = f"""
Usage:
  python {script} <Regression_test binary> <regression_scenes_dir> <sofa_root> [<reference_plugin_dir>]

Description:
  Prepares the environment variables needed to run the SOFA regression tests and launches the given Regression_test binary.

Positional arguments:
  <Regression_test binary>   Path to the Regression_test executable to run.
  <regression_scenes_dir>    Directory containing the regression scenes.
  <sofa_root>                Path to the SOFA build/install directory.
  [<reference_plugin_dir>]   Optional. Directory of the reference plugin. Defaults to this script's parent directory.

Examples:
  Linux:
    python {script} /home/user/build/bin/Regression_test ~/projects/sofa-src ~/projects/sofa-build ~/projects/regression/references
  Windows:
    python {script} C:\\projects\\sofa-build\\bin\\Release\\Regression_test.exe C:\\projects\\sofa-src C:\\projects\\sofa-build C:\\projects\\sofa-src\\applications\\projects\\Regression\\references
""".strip()
    print(msg)
    sys.exit(exit_code)


# Help flag handling and argument count validation
if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
    print_help(0)

# We expect 4 or 5 arguments total including the script name
if len(sys.argv) not in (4, 5):
    print("Error: invalid number of arguments.\n", file=sys.stderr)
    print_help(1)

# Securely access argv with bounds checks done above
bin_path = Path(sys.argv[1])
scenes_dir = Path(sys.argv[2])
sofa_root = Path(sys.argv[3])
regression_dir = Path(sys.argv[4]) if len(sys.argv) == 5 else Path(__file__).parent.absolute()

# Validate paths before using them
errors = []
if not bin_path.exists():
    errors.append(f"Regression_test binary not found: {bin_path}")
elif bin_path.is_dir():
    errors.append(f"Regression_test binary points to a directory, expected a file: {bin_path}")

if not scenes_dir.exists() or not scenes_dir.is_dir():
    errors.append(f"Invalid regression scenes directory: {scenes_dir}")

if not sofa_root.exists() or not sofa_root.is_dir():
    errors.append(f"Invalid SOFA root directory: {sofa_root}")

if not regression_dir.exists() or not regression_dir.is_dir():
    errors.append(f"Invalid reference plugin directory: {regression_dir}")

if errors:
    print("\n".join(["Argument validation failed:"] + errors), file=sys.stderr)
    sys.exit(1)

# Set required environment variables
os.environ["REGRESSION_SCENES_DIR"] = str(scenes_dir)
os.environ["SOFA_ROOT"] = str(sofa_root)
os.environ["SOFA_PLUGIN_PATH"] = str(sofa_root / "lib")
os.environ["REGRESSION_DIR"] = str(regression_dir)

# Launch the binary without invoking a shell to avoid command injection issues
try:
    result = subprocess.run([str(bin_path)], check=False)
    sys.exit(result.returncode)
except FileNotFoundError:
    print(f"Failed to execute binary (not found): {bin_path}", file=sys.stderr)
    sys.exit(1)
except PermissionError:
    print(f"Failed to execute binary (permission denied): {bin_path}", file=sys.stderr)
    sys.exit(1)
