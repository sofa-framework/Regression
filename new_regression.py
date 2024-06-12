import glob, os
import argparse
import sys
import Sofa


debugInfo = True

class RegressionSceneData:
    def __init__(self, fileScenePath: str = None, fileRefPath: str = None, steps = 1000, 
                 epsilon = 0.0001, mecaInMapping = True, dumpOnlyLastStep = False):
        """
        /// Path to the file scene to test
        std::string m_fileScenePath;
        /// Path to the reference file corresponding to the scene to test
        std::string m_fileRefPath;
        /// Number of step to perform
        unsigned int m_steps;
        /// Threshold value for dof position comparison
        double m_epsilon;
        /// Option to test mechanicalObject in Node containing a Mapping (true will test them)
        bool m_mecaInMapping;
        /// Option to compare mechanicalObject dof position at each timestep
        bool m_dumpOnlyLastStep;    
        """
        self.fileScenePath = fileScenePath
        self.fileRefPath = fileRefPath
        self.steps = steps
        self.epsilon = epsilon
        self.mecaInMapping = mecaInMapping
        self.dumpOnlyLastStep = dumpOnlyLastStep


class RegressionSceneList:
     def __init__(self, node, logGraph):
    



def findRegressionFiles(inputFolder):
    for root, dirs, files in os.walk(inputFolder):
        for file in files:
            if file.endswith(".regression-tests"):
                filePath = os.path.join(root, file)

                if (debugInfo):
                    print("Regression file found: " + filePath)

                # access header and store all includes
                # with open(filePath, 'r') as thefile:
                #     data = thefile.readlines()
                # thefile.close()
                
                # target = "SetTopologyAlgorithms"
                
                # new_file = open(filePath, "w")
                
                # for idx, line in enumerate(data):
                #     if re.search(target, line):
                #         continue;
                    
                #     new_file.write(line)
                
                # new_file.close()



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
    
    parser.add_argument(
        "--classify",
        dest="classify",
        default=False,
        help='Sort files into folders per class'
    )
    
    args = parser.parse_args()

    return args


if __name__ == '__main__':
    # 1- Parse arguments to get folder path
    args = parse_args()

    # 2- Process file
    findRegressionFiles(args.input)
    