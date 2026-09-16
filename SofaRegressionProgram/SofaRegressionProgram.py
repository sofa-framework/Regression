import os
import io
import argparse
import sys
import numpy as np
from pathlib import Path

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
from tools.RegressionHelper import writeMessage

regression_file_extension = ".regression-tests"

class RegressionProgram:
    def __init__(self, input_folders, filter = None, disable_progress_bar = False, verbose = 1, nbr_jobs = 1, logs_output = None):
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

        err_logs_stream = None
        if self.logs_output is not None :
            err_logs_stream = io.StringIO()
        try:

            for directory in input_folders :
                for root, dirs, files in os.walk(directory):
                    for file in files:
                        if file.endswith(regression_file_extension):
                            file_path = os.path.join(root, file)

                            scene_list = RegressionSceneList.RegressionSceneList(file_path, filter, self.disable_progress_bar, verbose, self.nbr_jobs)

                            if err_logs_stream is not None:
                                start_steam_out_size = err_logs_stream.tell()

                            scene_list.process_file(err_log_stream = err_logs_stream)

                            if err_logs_stream is not None and start_steam_out_size != err_logs_stream.tell():
                                print("", file=err_logs_stream)

                            self.scene_sets.append(scene_list)
        finally:
            if self.logs_output is not None :
                with open(Path(self.logs_output) / "parse_errors_logs.txt", 'w', encoding="utf-8") as summary_file:
                    summary_file.write(err_logs_stream.getvalue())


    def nbr_error_in_sets(self):
        nbr_errors = 0
        for scene_list in self.scene_sets:
            nbr_errors = nbr_errors + scene_list.get_nbr_errors()
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
        scene_list = self.scene_sets[id_set]
        scene_list.replay_references(id_scene)



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
    # 1- Parse arguments to get folder path
    parser = make_parser()
    args = parser.parse_args()

    verbose = args.verbose
    if(args.quiet):
        verbose = -1

    # 2- Process file
    if args.input:
        reg_prog = RegressionProgram(args.input, args.filter, args.progress_bar_is_disabled, verbose, args.jobs, logs_output = args.output)
    else:
        parser.print_help()
        exit("Error: Argument is required ! Quitting.")



    nbr_scenes = 0

    if args.legacy_mode:
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

    np.set_printoptions(legacy='1.25') # revert printing floating-point type in numpy (concretely remove np.array when displaying a list of np.float)

    nbr_parsing_errors = reg_prog.nbr_parsing_error_in_sets()


    stream_out = io.StringIO()

    writeMessage ("### Number of sets Done:  " + str(len(reg_prog.scene_sets)), stream = stream_out)
    writeMessage ("### Number of scenes Done:  " + str(nbr_scenes), stream = stream_out)
    if nbr_parsing_errors > 0:
        # Those scenes have not been processed at all: report them as an error
        # so that an invalid list file cannot silently reduce the test coverage.
        writeMessage ("### Number of invalid lines skipped:  " + str(nbr_parsing_errors), stream = stream_out)
    if args.write_mode is False:
        writeMessage ("### Number of scenes failed:  " + str(reg_prog.nbr_error_in_sets()), stream = stream_out)

    if args.output is not None:
        #Print in file
        with open(Path(args.output) / "summary.txt", 'w', encoding="utf-8") as summary_file:
            summary_file.write(stream_out.getvalue())

    #Print in stdout
    print(stream_out.getvalue(), end='')


    if ( args.write_mode is False and reg_prog.nbr_error_in_sets() > 0) or nbr_parsing_errors > 0:
        sys.exit(1) # exit with error(s)

    sys.exit(0) # exit without error
