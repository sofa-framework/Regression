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
    marshals the result back through a temporary JSON file. `run_scene_tasks()`
    schedules a list of scenes over a pool of such children, so that several
    scenes are simulated at the same time.
  * Child side: executed as `python RegressionWorker.py ...`, it sets up the
    SOFA environment, runs a single scene (write or compare) and writes its
    result to the file given by `--result-file`.

Because every scene already runs in its own process, running several of them
concurrently changes nothing to the results: children never share any SOFA
state. The parent only has to schedule them and collect their outcome.

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
import itertools
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def _safe_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


# --------------------------------------------------
# Parent side: spawn one child process for one scene
# --------------------------------------------------
def run_scene_in_subprocess(scene_data, mode, scene_list = None, legacy=False,
                            disable_progress_bar=False, verbose=1,
                            format="JSON", python_exe=None,
                            capture_output=False):
    """Run a single scene (write or compare) in an isolated child process.

    Args:
        scene_data: the RegressionSceneData describing the scene to run.
        mode (str): "write" to generate references, "compare" to check them.
        legacy (bool): use the legacy reference format (compare only).
        disable_progress_bar (bool): forwarded to the child.
        verbose (int): forwarded to the child.
        format (str): reference file format ("JSON" or "CSV").
        python_exe (str): interpreter to use for the child (defaults to the
            current one).
        capture_output (bool): if True, the child output is captured and
            returned in the "stdout"/"stderr" keys of the result instead of
            being interleaved with the output of the other children. Used when
            several scenes run concurrently.

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
        "--regression-type", scene_list.regression_type.name,
        "--meca-in-mapping", "1" if scene_data.meca_in_mapping else "0",
        "--dump-number-step", str(scene_data.dump_number_step),
        "--format", format,
        "--verbose", str(verbose),
        "--result-file", result_path,
    ]
    if legacy:
        cmd.append("--legacy")
    if disable_progress_bar:
        cmd.append("--disable-progress-bar")

    # When a single scene runs at a time, stdout/stderr are inherited so SOFA
    # logs and progress bars behave exactly as before (and the parent's --quiet
    # redirection propagates to the child). When several children run at the
    # same time their output is captured instead, and replayed as one block by
    # the caller, otherwise the logs of all the scenes would be interleaved.
    try:
        completed = subprocess.run(cmd, capture_output=capture_output, text=capture_output)
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
        result = {"ok": False,
                  "error": f"Worker produced no result (exit code {completed.returncode})."}

    if capture_output:
        result["stdout"] = completed.stdout
        result["stderr"] = completed.stderr
    return result


# --------------------------------------------------
# Parent side: schedule several scenes concurrently
# --------------------------------------------------
def resolve_nbr_jobs(nbr_jobs):
    """Turn the user-provided job count into a usable number of workers.

    0 (or a negative value) means "one job per logical core".
    """
    if nbr_jobs is None:
        return 1
    nbr_jobs = int(nbr_jobs)
    if nbr_jobs <= 0:
        return os.cpu_count() or 1
    return nbr_jobs


def _echo_captured_output(header, result, stream_out = sys.stdout, stream_err = sys.stderr  ):
    """Print in one block the output captured from a child process."""
    out = result.get("stdout")
    err = result.get("stderr")

    if not (out or err):
        return

    if out and stream_out is not None:
        print(header, file = stream_out, flush = False)
        print(out, end = '' if out.endswith("\n") else "\n", file = stream_out, flush = True)
    if err and stream_err is not None:
        print(header, file = stream_err, flush = False)
        print(err, end = '' if err.endswith("\n") else "\n", file = stream_err, flush = True)



def run_scene_tasks(tasks, nbr_jobs=1, format="JSON", on_result=None,
                    description=None, disable_progress_bar=False, logs_output=None):
    """Run a list of scenes, up to `nbr_jobs` of them at the same time.

    Args:
        tasks (list): task descriptors. Each one is a dict containing at least
            "scene_data" (RegressionSceneData), "mode" ("write" or "compare"),
            and optionally "legacy" and "verbose". Any other key is ignored
            here and simply handed back to `on_result`, which lets the caller
            attach whatever context it needs to identify the task.
        nbr_jobs (int): maximum number of scenes simulated concurrently.
        format (str): reference file format ("JSON" or "CSV").
        on_result (callable): called as `on_result(task, result)` for every
            finished task, always from the calling thread so that the callback
            does not need any locking.
        description (str): label of the progress bar.
        disable_progress_bar (bool): disable the progress bar of this run.

    Returns:
        int: the number of tasks that were run.
    """

    nbr_jobs = max(1, resolve_nbr_jobs(nbr_jobs))
    # Never spawn more workers than there is work to do.
    nbr_jobs = min(nbr_jobs, len(tasks)) if tasks else 1
    nbTasks = len(tasks)
    executed = itertools.count(1)

    def _run(task):
        return run_scene_in_subprocess(
            task["scene_data"],
            mode=task["mode"],
            legacy=task.get("legacy", False),
            scene_list= task["scene_list"],
            # In parallel the per-step progress bars of the children are
            # captured along with their output: they would only produce noise.
            disable_progress_bar=disable_progress_bar or nbr_jobs > 1,
            verbose=int(task.get("verbose", "1")),
            format=format,
            capture_output=True,
        )


    stream_out = None
    if logs_output is not None:
        stream_out = io.StringIO()

    try :
        if nbr_jobs == 1:
            for task in tasks:
                result = _run(task)

                if stream_out is not None:
                    start_steam_out_size = stream_out.tell()

                verbose = task.get("verbose", 1)
                if verbose == 2:
                    _echo_captured_output( f"--- {task['mode']}: {task['scene_data'].file_scene_path}", result)
                if on_result is not None:
                    ## could use task["id_scene"] instead of next(executed) here, but then the order would be wrong
                    on_result(task, result, log_prefix=f"({next(executed)}/{nbTasks})", err_log_stream = stream_out)

                if stream_out is not None:
                    _echo_captured_output( f"--- {task['mode']}: {task['scene_data'].file_scene_path}", result, stream_err = stream_out, stream_out=None)
                    if(stream_out.tell() != start_steam_out_size):
                        print("", file=stream_out)

        else:
            with ThreadPoolExecutor(max_workers=nbr_jobs) as executor:
                # The threads only wait on their child process: all the result
                # handling happens here, in the calling thread.
                futures = {executor.submit(_run, task): task for task in tasks}
                try:
                    for future in as_completed(futures):
                        task = futures[future]
                        result = future.result()
                        verbose = task.get("verbose", 1)

                        if stream_out is not None:
                            start_steam_out_size = stream_out.tell()

                        if verbose == 2:
                            _echo_captured_output( f"--- {task['mode']}: {task['scene_data'].file_scene_path}", result)
                        if on_result is not None:
                            ## could use task["id_scene"] instead of next(executed) here, but then the order would be wrong
                            on_result(task, result, log_prefix=f"({next(executed)}/{nbTasks})",err_log_stream = stream_out)

                        if stream_out is not None:
                            _echo_captured_output( f"--- {task['mode']}: {task['scene_data'].file_scene_path}", result, stream_err = stream_out, stream_out=None)
                            if(stream_out.tell() != start_steam_out_size):
                                print("", file=stream_out)

                except (KeyboardInterrupt, SystemExit):
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise
    finally:
        if logs_output is not None:
            with open(Path(logs_output) / "run_errors_logs.txt", 'w', encoding="utf-8") as error_logs_file:
                error_logs_file.write(stream_out.getvalue())

    return len(tasks)


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
    parser.add_argument("--regression-type", dest="regression_type", type=str, required=True)
    parser.add_argument("--meca-in-mapping", dest="meca_in_mapping", choices=["0", "1"], required=True)
    parser.add_argument("--dump-number-step", dest="dump_number_step", type=int, required=True)
    parser.add_argument("--format", default="JSON")
    parser.add_argument("--result-file", dest="result_file", required=True)
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--verbose", default=1, type=int)
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

        import Sofa
        import SofaRuntime  # noqa: F401  (registers the py3 scene loader)
        import tools.RegressionSceneData as RegressionSceneData
        import tools.RegressionSceneList as RegressionSceneList
        import numpy as np

        np.set_printoptions(legacy='1.25') # revert printing floating-point type in numpy (concretely remove np.array when displaying a list of np.float)


        scene = RegressionSceneList.RegressionSceneList.RegressionType[args.regression_type].value[1](
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
                "error": None,
                **scene.__dict__
            }
            ## Remove data that break json
            result.__delitem__("meca_objs")
            result.__delitem__("root_node")

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
