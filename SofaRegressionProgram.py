import os
import argparse
import sys
import numpy as np

from tqdm import tqdm

if "SOFA_ROOT" not in os.environ:
    print('SOFA_ROOT environment variable has not been detected, quitting.')
    exit(1)
else:
    sofapython3_path = os.environ["SOFA_ROOT"] + "/lib/python3/site-packages"
    sys.path.append(sofapython3_path)

import Sofa
import SofaRuntime # importing SofaRuntime will add the py3 loader to the scene loaders
import tools.RegressionSceneList as RegressionSceneList

regression_file_extension = ".regression-tests"

class RegressionProgram:
    def __init__(self, input_folder, filter, disable_progress_bar = False, verbose = False):
        self.scene_sets = []  # List <RegressionSceneList>
        self.disable_progress_bar = disable_progress_bar
        self.verbose = verbose

        for root, dirs, files in os.walk(input_folder):
            for file in files:
                if file.endswith(regression_file_extension):
                    file_path = os.path.join(root, file)

                    scene_list = RegressionSceneList.RegressionSceneList(file_path, filter, self.disable_progress_bar, verbose)

                    scene_list.process_file()
                    self.scene_sets.append(scene_list)

    def nbr_error_in_sets(self):
        nbr_errors = 0
        for scene_list in self.scene_sets:
            nbr_errors = nbr_errors + scene_list.get_nbr_errors()
        return nbr_errors

    def log_errors_in_sets(self):
        for scene_list in self.scene_sets:
            scene_list.log_scenes_errors()

    def write_sets_references(self, id_set=0):
        scene_list = self.scene_sets[id_set]
        nbr_scenes = scene_list.write_all_references()
        return nbr_scenes

    def write_all_sets_references(self):
        nbr_sets = len(self.scene_sets)
        pbar_sets = tqdm(total=nbr_sets, disable=self.disable_progress_bar)
        pbar_sets.set_description("Write All sets")

        nbr_scenes = 0
        for i in range(0, nbr_sets):
            nbr_scenes = nbr_scenes + self.write_sets_references(i)
            pbar_sets.update(1)

        pbar_sets.close()

        return nbr_scenes

    def compare_sets_references(self, id_set=0):
        scene_list = self.scene_sets[id_set]
        nbr_scenes = scene_list.compare_all_references()
        return nbr_scenes

    def compare_all_sets_references(self):
        nbr_sets = len(self.scene_sets)
        pbar_sets = tqdm(total=nbr_sets, disable=self.disable_progress_bar)
        pbar_sets.set_description("Compare All sets")

        nbr_scenes = 0
        for i in range(0, nbr_sets):
            nbr_scenes = nbr_scenes + self.compare_sets_references(i)
            pbar_sets.update(1)

        pbar_sets.close()

        return nbr_scenes

    def replay_references(self, id_set=0):
        scene_list = self.scene_sets[id_set]
        scene_list.replay_references(0)



def parse_args():
    """
    Parse input arguments
    """
    parser = argparse.ArgumentParser(
        description='Regression arguments')
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
                        help="A regex filter to select scenes to test",
                        type=str)
    
    parser.add_argument('--replay', 
                        dest='replay', 
                        help="test option to replay reference",
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
    
    cmdline_args = parser.parse_args()

    return cmdline_args

        

if __name__ == '__main__':
    # 1- Parse arguments to get folder path
    args = parse_args()
    # 2- Process file
    if args.input is not None:
        reg_prog = RegressionProgram(args.input, args.filter, args.progress_bar_is_disabled, args.verbose)
    else:
        exit("Error: Argument is required ! Quitting.")

    nbr_scenes = 0

    replay = bool(args.replay)
    if replay:
        reg_prog.replay_references()
        sys.exit()

    if args.write_mode:
        nbr_scenes = reg_prog.write_all_sets_references()
    else:
        nbr_scenes = reg_prog.compare_all_sets_references()

    np.set_printoptions(legacy='1.25') # revert printing floating-point type in numpy (concretely remove np.array when displaying a list of np.float)
    
    print ("### Number of sets Done:  " + str(len(reg_prog.scene_sets)))
    print ("### Number of scenes Done:  " + str(nbr_scenes))
    if args.write_mode is False:
        print ("### Number of scenes failed:  " + str(reg_prog.nbr_error_in_sets()))
        reg_prog.log_errors_in_sets()
        if reg_prog.nbr_error_in_sets() > 0:
            sys.exit(1) # exit with error(s)

    sys.exit(0) # exit without error

    
