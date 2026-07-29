import os
import argparse
import sys
import numpy as np

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

regression_file_extension = ".regression-tests"

class RegressionProgram:
    def __init__(self, input_folder, filter = None, disable_progress_bar = False, verbose = False, nbr_jobs = 1):
        """Initialize the RegressionProgram

        Args:
            input_folder (str): Path to the folder containing regression test files.
            filter (str): Regex pattern to filter scene files (e.g., '^demo.*.scn$'). If None, no filter is applied. Defaults to None.
            disable_progress_bar (bool, optional): If True, disable progress bars. Defaults to False.
            verbose (bool, optional): If True, enable verbose output. Defaults to False.
            nbr_jobs (int, optional): Number of scenes to write/compare at the same time. 0 means one per logical core. Defaults to 1.
        """
        self.scene_sets = []  # List <RegressionSceneList>
        self.disable_progress_bar = disable_progress_bar
        self.verbose = verbose
        self.legacy_mode = False
        self.nbr_jobs = RegressionWorker.resolve_nbr_jobs(nbr_jobs)

        for root, dirs, files in os.walk(input_folder):
            for file in files:
                if file.endswith(regression_file_extension):
                    file_path = os.path.join(root, file)

                    scene_list = RegressionSceneList.RegressionSceneList(file_path, filter, self.disable_progress_bar, verbose, self.nbr_jobs)

                    scene_list.process_file()
                    self.scene_sets.append(scene_list)

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
            on_result=lambda task, result: task["scene_list"].apply_result(task, result),
            description=description,
            disable_progress_bar=self.disable_progress_bar)

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
                        type=str)
    
    parser.add_argument('--output', 
                        dest='output', 
                        help="Directory where to export data preprocessed",
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
        action='store_true'
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

    parser.epilog = '''
Examples:
    python SofaRegressionProgram.py --input ./scenes
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

    # 2- Process file
    if args.input is not None:
        reg_prog = RegressionProgram(args.input, args.filter, args.progress_bar_is_disabled, args.verbose, args.jobs)
    else:
        parser.print_help()
        exit("Error: Argument is required ! Quitting.")

    nbr_scenes = 0

    if args.legacy_mode:
        print("Legacy regression mode activated.")
        reg_prog.legacy_mode = True

    if reg_prog.nbr_jobs > 1:
        print(f"Processing up to {reg_prog.nbr_jobs} scenes at the same time.")


    if args.replay is not None:
        replayId = int(args.replay)
        reg_prog.replay_references(replayId)
        sys.exit()

    old_fd = os.dup(1)
    if args.quiet:
        # Save and redirect
        sys.stdout.flush()
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 1)
        os.close(devnull)

    if args.write_mode:
        nbr_scenes = reg_prog.write_all_sets_references()
    else:
        nbr_scenes = reg_prog.compare_all_sets_references()

    if args.quiet:
        # Restore
        sys.stdout.flush()
        os.dup2(old_fd, 1)
        os.close(old_fd)

    np.set_printoptions(legacy='1.25') # revert printing floating-point type in numpy (concretely remove np.array when displaying a list of np.float)
    
    nbr_parsing_errors = reg_prog.nbr_parsing_error_in_sets()

    print ("### Number of sets Done:  " + str(len(reg_prog.scene_sets)))
    print ("### Number of scenes Done:  " + str(nbr_scenes))
    if nbr_parsing_errors > 0:
        # Those scenes have not been processed at all: report them as an error
        # so that an invalid list file cannot silently reduce the test coverage.
        print ("### Number of invalid lines skipped:  " + str(nbr_parsing_errors))
    if args.write_mode is False:
        print ("### Number of scenes failed:  " + str(reg_prog.nbr_error_in_sets()))
        reg_prog.log_errors_in_sets()
        if reg_prog.nbr_error_in_sets() > 0:
            sys.exit(1) # exit with error(s)

    if nbr_parsing_errors > 0:
        sys.exit(1) # exit with error(s)

    sys.exit(0) # exit without error

    
