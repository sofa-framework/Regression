import os
import argparse
import sys

from tqdm import tqdm

if "SOFA_ROOT" not in os.environ:
    sofa_real_root = "/Users/fred/Work/sofa"
    sofa_root = sofa_real_root + "/build/current-ninja"
    sofapython3_path = sofa_root + "/lib/python3/site-packages"
    sofa_build_configuration = "Release"

    os.environ["SOFA_ROOT"] = sofa_root
    os.environ["SOFA_BUILD_CONFIGURATION"] = sofa_build_configuration
    sys.path.append(sofapython3_path)
else:
    sofapython3_path = os.environ["SOFA_ROOT"] + "/lib/python3/site-packages"
    sys.path.append(sofapython3_path)

import Sofa
import SofaRuntime

tools_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), './tools')
sys.path.append(os.path.abspath(tools_dir))
import RegressionSceneData
import RegressionSceneParsing


class RegressionProgram:
    def __init__(self, input_folder, disable_progress_bar = False):
        self.scene_sets = []  # List <RegressionSceneList>
        self.disable_progress_bar = disable_progress_bar

        for root, dirs, files in os.walk(input_folder):
            for file in files:
                if file.endswith(".regression-tests"):
                    file_path = os.path.join(root, file)

                    scene_list = RegressionSceneParsing.RegressionSceneList(file_path, self.disable_progress_bar)

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
        nbr_scenes = scene_list.write_all_references(self.disable_progress_bar)
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
                        help='help input', 
                        type=str)
    
    parser.add_argument('--output', 
                        dest='output', 
                        help="Directory where to export data preprocessed",
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
    
    cmdline_args = parser.parse_args()

    return cmdline_args

        

if __name__ == '__main__':
    # 1- Parse arguments to get folder path
    args = parse_args()
    # 2- Process file
    if args.input is not None:
        regProg = RegressionProgram(args.input, args.progress_bar_is_disabled)
    else:
        exit("Error: Argument is required ! Quitting.")
    #SofaRuntime.disable_messages()
    SofaRuntime.importPlugin("SofaPython3")

    nbr_scenes = 0

    replay = bool(args.replay)
    if replay is True:
        regProg.replay_references()
        sys.exit()

    if args.write_mode is True:
        nbr_scenes = regProg.write_all_sets_references()
    else:
        nbr_scenes = regProg.compare_all_sets_references()

    print ("### Number of sets Done:  " + str(len(regProg.scene_sets)))
    print ("### Number of scenes Done:  " + str(nbr_scenes))
    if args.write_mode is False:
        print ("### Number of scenes failed:  " + str(regProg.nbr_error_in_sets()))
        #np.set_printoptions(precision=8)
        regProg.log_errors_in_sets()
   
    sys.exit()

    
