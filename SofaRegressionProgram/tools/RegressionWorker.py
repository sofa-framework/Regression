"""
Per-scene subprocess isolation for the SOFA regression program.

SOFA does not fully reset its global/static state between two load/unload
cycles inside a single process. As a consequence, the simulation result of a
scene depends on which scenes were simulated before it in the same process.
This makes references order-dependent: a scene simulated during the batch
`--write-references` pass can produce a different result than the same scene
simulated during the batch compare pass, causing regressions to fail right
after regenerating the references without anything having changed.

To guarantee reproducibility, every scene is simulated in its own freshly
spawned Python process. Each child starts from a clean SOFA state, so the
write pass and the compare pass always see identical conditions.

This module has two roles:
  * Parent side: `run_scene_in_subprocess()` spawns a child for one scene and
    marshals the result back through a temporary JSON file.
  * Child side: executed as `python RegressionWorker.py ...`, it sets up the
    SOFA environment, runs a single scene (write or compare) and writes its
    result to the file given by `--result-file`.

Only the standard library is imported at module top-level so that importing
this module in the parent does NOT import SOFA (the parent must never load or
simulate a scene, otherwise the isolation would be defeated).
"""

import os
import sys
import json
import argparse
import subprocess
import tempfile


def _safe_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


# --------------------------------------------------
# Parent side: spawn one child process for one scene
# --------------------------------------------------
def run_scene_in_subprocess(scene_data, mode, legacy=False,
                            disable_progress_bar=False, verbose=False,
                            format="JSON", python_exe=None):
    """Run a single scene (write or compare) in an isolated child process.

    Args:
        scene_data: the RegressionSceneData describing the scene to run.
        mode (str): "write" to generate references, "compare" to check them.
        legacy (bool): use the legacy reference format (compare only).
        disable_progress_bar (bool): forwarded to the child.
        verbose (bool): forwarded to the child.
        format (str): reference file format ("JSON" or "CSV").
        python_exe (str): interpreter to use for the child (defaults to the
            current one).

    Returns:
        dict: the result reported by the child. Always contains an "ok" key.
              For compare runs it also contains "result", "regression_failed",
              "nbr_tested_frame", "total_run_time", "error_by_dof" and
              "total_error".
    """
    python_exe = python_exe or sys.executable
    worker_path = os.path.abspath(__file__)

    fd, result_path = tempfile.mkstemp(suffix=".json", prefix="regression_result_")
    os.close(fd)

    cmd = [
        python_exe, worker_path,
        "--mode", mode,
        "--scene", str(scene_data.file_scene_path),
        "--ref", str(scene_data.file_ref_path),
        "--steps", str(scene_data.steps),
        "--epsilon", repr(scene_data.epsilon),
        "--meca-in-mapping", "1" if scene_data.meca_in_mapping else "0",
        "--dump-number-step", str(scene_data.dump_number_step),
        "--format", format,
        "--result-file", result_path,
    ]
    if legacy:
        cmd.append("--legacy")
    if verbose:
        cmd.append("--verbose")
    if disable_progress_bar:
        cmd.append("--disable-progress-bar")

    # stdout/stderr are inherited so SOFA logs and progress bars behave exactly
    # as before (and the parent's --quiet redirection propagates to the child).
    try:
        completed = subprocess.run(cmd)
    except Exception as e:
        _safe_remove(result_path)
        return {"ok": False, "error": f"Failed to launch worker subprocess: {e}"}

    result = None
    try:
        with open(result_path, "r") as f:
            result = json.load(f)
    except Exception:
        result = None
    _safe_remove(result_path)

    if result is None:
        return {"ok": False,
                "error": f"Worker produced no result (exit code {completed.returncode})."}
    return result


# --------------------------------------------------
# Child side: run one scene in a fresh SOFA process
# --------------------------------------------------
def _make_worker_parser():
    parser = argparse.ArgumentParser(description="Regression per-scene worker (internal)")
    parser.add_argument("--mode", choices=["write", "compare"], required=True)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--steps", type=int, required=True)
    parser.add_argument("--epsilon", type=float, required=True)
    parser.add_argument("--meca-in-mapping", dest="meca_in_mapping", choices=["0", "1"], required=True)
    parser.add_argument("--dump-number-step", dest="dump_number_step", type=int, required=True)
    parser.add_argument("--format", default="JSON")
    parser.add_argument("--result-file", dest="result_file", required=True)
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--disable-progress-bar", dest="disable_progress_bar", action="store_true")
    return parser


def _worker_main():
    args = _make_worker_parser().parse_args()

    result = {"ok": False, "error": None}
    try:
        # SOFA and the tools package must be imported inside this fresh process.
        if "SOFA_ROOT" not in os.environ:
            raise RuntimeError("SOFA_ROOT environment variable is not set.")

        sofapython3_path = os.path.join(os.environ["SOFA_ROOT"], "lib", "python3", "site-packages")
        if sofapython3_path not in sys.path:
            sys.path.append(sofapython3_path)

        # Make the "tools" package importable (program root = parent of this dir).
        program_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if program_root not in sys.path:
            sys.path.insert(0, program_root)

        import SofaRuntime  # noqa: F401  (registers the py3 scene loader)
        import tools.RegressionSceneData as RegressionSceneData

        scene = RegressionSceneData.RegressionSceneData(
            file_scene_path=args.scene,
            file_ref_path=args.ref,
            steps=args.steps,
            epsilon=args.epsilon,
            meca_in_mapping=(args.meca_in_mapping == "1"),
            dump_number_step=args.dump_number_step,
            disable_progress_bar=args.disable_progress_bar,
            verbose=args.verbose,
        )

        scene.load_scene(args.format)

        if args.mode == "write":
            scene.write_references(args.format)
            result = {"ok": True, "error": None}
        else:  # compare
            if args.legacy:
                passed = scene.compare_legacy_references()
            else:
                passed = scene.compare_references(args.format)

            result = {
                "ok": True,
                "result": bool(passed),
                "regression_failed": bool(scene.regression_failed),
                "nbr_tested_frame": int(scene.nbr_tested_frame),
                "total_run_time": int(scene.total_run_time),
                "error_by_dof": [float(v) for v in scene.error_by_dof],
                "total_error": [float(v) for v in scene.total_error],
                "error": None,
            }
    except Exception as e:
        import traceback
        result = {"ok": False, "error": str(e), "traceback": traceback.format_exc()}
    finally:
        try:
            with open(args.result_file, "w") as f:
                json.dump(result, f)
        except Exception:
            pass

    # The outcome is communicated through the result file, so always exit 0
    # unless the result could not be written at all.
    sys.exit(0)


if __name__ == "__main__":
    _worker_main()
