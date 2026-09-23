import os
import io
import argparse
import sys
import numpy as np
from pathlib import Path

import time

if "SOFA_ROOT" not in os.environ:
    print('SOFA_ROOT environment variable has not been detected, quitting.')
    exit(1)
else:
    sofapython3_path = os.environ["SOFA_ROOT"] + "/lib/python3/site-packages"
    sys.path.append(sofapython3_path)

import Sofa
import SofaRuntime # importing SofaRuntime will add the py3 loader to the scene loaders
import tools.RegressionSceneList as RegressionSceneList
import tools.RegressionWorker as RegressionWorker
from tools.RegressionHelper import writeMessage, writeWarning

regression_file_extension = ".regression-tests"

class RegressionProgram:
    def __init__(self, input_folders, filter = None, reg_type = 'ALL',  disable_progress_bar = False, verbose = 1, nbr_jobs = 1, logs_output = None):
        """Initialize the RegressionProgram

        Args:
            input_folders (list(str)): Paths to folders containing regression test files.
            filter (str): Regex pattern to filter scene files (e.g., '^demo.*.scn$'). If None, no filter is applied. Defaults to None.
            disable_progress_bar (bool, optional): If True, disable progress bars. Defaults to False.
            verbose (int, optional): If 0 returns only errors and success, 1 display warnings, 2 display everything. Defaults to 1.
            nbr_jobs (int, optional): Number of scenes to write/compare at the same time. 0 means one per logical core. Defaults to 1.
        """
        self.scene_sets = []  # List <RegressionSceneList>
        self.disable_progress_bar = disable_progress_bar
        self.verbose = verbose
        self.legacy_mode = False
        self.nbr_jobs = RegressionWorker.resolve_nbr_jobs(nbr_jobs)
        self.logs_output = logs_output
        self.reg_type = reg_type

        err_logs_stream = None
        if self.logs_output is not None :
            err_logs_stream = io.StringIO()
        try:

            for directory in input_folders :
                for root, dirs, files in os.walk(directory):
                    for file in files:
                        file_path = os.path.join(root, file)

                        #Warning lazy or in the end, if not lazy then this breaks
                        if file.endswith(regression_file_extension) and (reg_type == 'ALL' or RegressionSceneList.RegressionSceneList.RegressionType[reg_type].value[0] in file) :
                            scene_list = RegressionSceneList.RegressionSceneList(file_path, filter, self.disable_progress_bar, verbose, self.nbr_jobs)

                            if err_logs_stream is not None:
                                start_steam_out_size = err_logs_stream.tell()

                            scene_list.process_file(err_log_stream = err_logs_stream)

                            if err_logs_stream is not None and start_steam_out_size != err_logs_stream.tell():
                                print("", file=err_logs_stream)

                            self.scene_sets.append(scene_list)
                        elif file.endswith(regression_file_extension):
                            writeWarning(f"Regression file {file_path} skipped because of selected regression type {reg_type}", self.verbose)

        finally:
            if self.logs_output is not None :
                with open(Path(self.logs_output) / "parse_errors.txt", 'w', encoding="utf-8") as summary_file:
                    summary_file.write(err_logs_stream.getvalue())


    def nbr_error_in_sets(self):
        nbr_errors = 0
        for scene_list in self.scene_sets:
            nbr_errors = nbr_errors + scene_list.get_nbr_errors()
        return nbr_errors

    def nbr_crash_in_sets(self):
        nbr_errors = 0
        for scene_list in self.scene_sets:
            nbr_errors = nbr_errors + scene_list.get_nbr_crash()
        return nbr_errors

    def nbr_parsing_error_in_sets(self):
        nbr_errors = 0
        for scene_list in self.scene_sets:
            nbr_errors = nbr_errors + scene_list.get_nbr_parsing_errors()
        return nbr_errors

    def log_errors_in_sets(self):
        for scene_list in self.scene_sets:
            scene_list.log_scenes_errors()

    def run_all_sets(self, mode, description):
        """Run every scene of every set in `mode` ("write" or "compare").

        When several jobs are allowed, the scenes of all the sets are scheduled
        in a single pool: a set holding fewer scenes than the number of jobs
        would otherwise leave most of the workers idle.
        """
        tasks = []
        for scene_list in self.scene_sets:
            scene_list.legacy_mode = self.legacy_mode
            tasks.extend(scene_list.build_tasks(mode))

        return RegressionWorker.run_scene_tasks(
            tasks,
            nbr_jobs=self.nbr_jobs,
            on_result=lambda task, result, **kwargs: task["scene_list"].apply_result(task, result, **kwargs),
            description=description,
            disable_progress_bar=self.disable_progress_bar,
            logs_output=self.logs_output)

    def write_sets_references(self, id_set=0):
        scene_list = self.scene_sets[id_set]
        nbr_scenes = scene_list.write_all_references()
        return nbr_scenes

    def write_all_sets_references(self):
        return self.run_all_sets("write", "Write All sets")

    def compare_sets_references(self, id_set=0):
        scene_list = self.scene_sets[id_set]
        scene_list.legacy_mode = self.legacy_mode
        nbr_scenes = scene_list.compare_all_references()
        return nbr_scenes

    def compare_all_sets_references(self):
        return self.run_all_sets("compare", "Compare All sets")

    def replay_references(self, id_scene, id_set=0):
        if(self.scene_sets[id_set].regression_type is not None and self.scene_sets[id_set].regression_type.value[1].is_replay_available()):
            scene_list = self.scene_sets[id_set]
            scene_list.replay_references(id_scene)
        else:
            raise ValueError(f"Replay is not available for regression type {self.scene_sets[id_set].regression_type}")

    def write_summary(self, buffer,nbr_scenes, duration_seconds):
        writeMessage ("test_suite=" + str(len(self.scene_sets)), buffer)
        writeMessage ("test_total=" + str(nbr_scenes), buffer)
        writeMessage ("parsing_error=" + str(self.nbr_parsing_error_in_sets()), buffer)
        writeMessage ("failures=" + str(self.nbr_error_in_sets()), buffer)
        writeMessage ("crashes=" + str(self.nbr_crash_in_sets()), buffer)
        writeMessage (f"duration={duration_seconds:.3f}", buffer)


def make_parser():
    """
    Parse input arguments
    """
    parser = argparse.ArgumentParser(
        description='Regression arguments',
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--input',
                        dest='input',
                        help=f'The input folder containing {regression_file_extension} files that describe scenes to be'
                             f' processed and compared against a reference for regression detection.',
                        action='append',
                        default=[],
                        type=str)

    regression_type_choices = ['ALL', *(reg_type.name for reg_type in RegressionSceneList.RegressionSceneList.RegressionType)]
    parser.add_argument('--regression-type',
                        dest='reg_type',
                        choices=regression_type_choices,
                        help=f"The regression type from {regression_type_choices}. Default value is ALL.",
                        type=str,
                        default='ALL')


    parser.add_argument('--filter',
                        dest='filter',
                        help="A regex filter to select scenes to test (e.g., '^demo.*.scn$')",
                        type=str)

    parser.add_argument('-j', '--jobs',
                        dest='jobs',
                        help="Number of scenes to process at the same time (each one still runs in its own\n"
                             "isolated process, so the results are unchanged). 0 means one job per logical\n"
                             "core. Default: 1 (sequential).",
                        type=int,
                        default=1)

    parser.add_argument('--replay',
                        dest='replay',
                        help=f"Will launch runSofa on the scene number X (input number) in the input the list of the {regression_file_extension} file given as input and display the scene references aside from the simulation",
                        type=int)

    parser.add_argument(
        "--write-references",
        dest="write_mode",
        help='If set, will generate new reference files',
        action='store_true'
    )
    parser.add_argument(
        "--disable-progress-bar",
        dest="progress_bar_is_disabled",
        help='If set, will disable progress bars',
        action='store_true'
    )
    parser.add_argument(
        "--verbose",
        dest="verbose",
        help='If set, will display more information',
        type=int,
        default = 1
    )
    parser.add_argument(
        "--quiet",
        dest="quiet",
        help='If set, will only print error messages and results.',
        action='store_true'
    )
    parser.add_argument(
        "--legacy-regression",
        dest="legacy_mode",
        help='If set, will read old format regression files',
        action='store_true'
    )

    parser.add_argument(
        '--output-logs-errors',
        dest='output',
        help="Directory where to export logs errors and summary",
        type=str
    )


    parser.epilog = '''
Examples:
    python SofaRegressionProgram.py --input ./scenes
    python SofaRegressionProgram.py --input ./scenes --input ./other/scenes
    python SofaRegressionProgram.py --input ./scenes --filter \"$demo.*.scn\"
    python SofaRegressionProgram.py --input ./scenes --replay 5
    python SofaRegressionProgram.py --input ./scenes --jobs 8
    python SofaRegressionProgram.py --input ./scenes --write-references -j 0
        '''

    return parser


if __name__ == '__main__':
    start = time.time()

    # 1- Parse arguments to get folder path
    parser = make_parser()
    args = parser.parse_args()

    verbose = args.verbose
    if(args.quiet):
        verbose = -1

    if(args.output):
        Path(args.output).mkdir(parents=True, exist_ok=True)

    # 2- Process file
    if args.input:
        reg_prog = RegressionProgram(args.input, args.filter, args.reg_type, args.progress_bar_is_disabled, verbose, args.jobs, logs_output = args.output)
    else:
        parser.print_help()
        exit("Error: Argument is required ! Quitting.")



    nbr_scenes = 0

    if args.legacy_mode:
        if(args.write_mode):
            exit("Error: Cannot write legacy references, to do so run the original Regression_test binary")
        writeMessage("Legacy regression mode activated.")
        reg_prog.legacy_mode = True


    if reg_prog.nbr_jobs > 1:
        writeMessage(f"Processing up to {reg_prog.nbr_jobs} scenes at the same time.")


    if args.replay is not None:
        replayId = int(args.replay)
        reg_prog.replay_references(replayId)
        sys.exit()


    if args.write_mode:
        nbr_scenes = reg_prog.write_all_sets_references()
    else:
        nbr_scenes = reg_prog.compare_all_sets_references()

    duration_seconds=time.time() - start

    np.set_printoptions(legacy='1.25') # revert printing floating-point type in numpy (concretely remove np.array when displaying a list of np.float)

    writeMessage (f"### Number of sets Done: {len(reg_prog.scene_sets)}")
    writeMessage (f"### Number of scenes Done: {nbr_scenes}")
    if reg_prog.nbr_parsing_error_in_sets() > 0:
        # Those scenes have not been processed at all: report them as an error
        # so that an invalid list file cannot silently reduce the test coverage.
        writeMessage (f"### Number of invalid lines skipped: {reg_prog.nbr_parsing_error_in_sets()}")
    writeMessage (f"### Number of scenes failed: {reg_prog.nbr_error_in_sets()}")
    writeMessage (f"### Number of scenes crashed: {reg_prog.nbr_crash_in_sets()}")
    writeMessage (f"### Regression took : {duration_seconds:.3f} s")

    if args.output is not None:
        #Print in file
        with open(Path(args.output) / "summary.txt", 'w', encoding="utf-8") as summary_file:
            reg_prog.write_summary(summary_file, nbr_scenes, duration_seconds)



    if ( reg_prog.nbr_error_in_sets() > 0) or reg_prog.nbr_parsing_error_in_sets()> 0:
        sys.exit(1) # exit with error(s)

    sys.exit(0) # exit without error
