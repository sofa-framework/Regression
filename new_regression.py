import glob, os
import argparse
import sys
import numpy as np

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

dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), './tools')
sys.path.append(os.path.abspath(dir))
import RegressionSceneData
import RegressionSceneParsing


class RegressionProgram:
    def __init__(self, inputFolder):
        self.sceneSets = [] # List <RegressionSceneList>

        for root, dirs, files in os.walk(inputFolder):
            for file in files:
                if file.endswith(".regression-tests"):
                    filePath = os.path.join(root, file)

                    sceneList = RegressionSceneParsing.RegressionSceneList(filePath)

                    sceneList.processFile()
                    self.sceneSets.append(sceneList)

    def nbrErrorInSets(self):
        nbrErrors = 0
        for sceneList in self.sceneSets:
            nbrErrors = nbrErrors + sceneList.getNbrErrors()
        return nbrErrors
    
    def logErrorsInSets(self):
        for sceneList in self.sceneSets:
            sceneList.logScenesErrors()

    def writeSetsReferences(self, idSet = 0):
        sceneList = self.sceneSets[idSet]
        nbrScenes = sceneList.writeAllReferences()
        return nbrScenes
    
    def writeAllSetsReferences(self):
        nbrSets = len(self.sceneSets)
        pbarSets = tqdm(total=nbrSets)
        pbarSets.set_description("Write All sets")
        
        nbrScenes = 0
        for i in range(0, nbrSets):
            nbrScenes = nbrScenes + self.writeSetsReferences(i)
            pbarSets.update(1)

        pbarSets.close()

        return nbrScenes


    def compareSetsReferences(self, idSet = 0):
        sceneList = self.sceneSets[idSet]
        nbrScenes = sceneList.compareAllReferences()
        return nbrScenes
        
    def compareAllSetsReferences(self):
        nbrSets = len(self.sceneSets)
        pbarSets = tqdm(total=nbrSets)
        pbarSets.set_description("Compare All sets")

        nbrScenes = 0
        for i in range(0, nbrSets):
            nbrScenes = nbrScenes + self.compareSetsReferences(i)
            pbarSets.update(1)

        pbarSets.close()

        return nbrScenes
    
    def replayReferences(self, idSet = 0):
        sceneList = self.sceneSets[idSet]
        sceneList.replayReferences(0)



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
        "--writeRef",
        dest="writeMode",      
        help='If true, will generate new reference files',
        type=int
    )
    
    args = parser.parse_args()

    return args

        

if __name__ == '__main__':
    # 1- Parse arguments to get folder path
    args = parse_args()
    # 2- Process file
    if args.input is not None:
        regProg = RegressionProgram(args.input)
    else:
        exit("Error: Argument is required ! Quitting.")
    #SofaRuntime.disable_messages()
    SofaRuntime.importPlugin("SofaPython3")

    nbrScenes = 0
    writeMode = bool(args.writeMode)

    replay = bool(args.replay)
    if replay is True:
        regProg.replayReferences()
        sys.exit()

    if writeMode is True:
        nbrScenes = regProg.writeAllSetsReferences()
    else:
        nbrScenes = regProg.compareAllSetsReferences()

    print ("### Number of sets Done:  " + str(len(regProg.sceneSets)))
    print ("### Number of scenes Done:  " + str(nbrScenes))
    if writeMode is False:
        print ("### Number of scenes failed:  " + str(regProg.nbrErrorInSets()))
        #np.set_printoptions(precision=8)
        regProg.logErrorsInSets()
   
    sys.exit()

    
