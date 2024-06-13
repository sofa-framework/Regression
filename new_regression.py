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

    def printInfo(self):
        print("Test scene: " + self.fileScenePath + " vs " + self.fileRefPath + " using: " + self.steps
              + " " + self.epsilon)


class RegressionSceneList:
    def __init__(self, filePath):
        self.filePath = filePath
        self.fileDir = os.path.dirname(filePath)
        self.scenes = []

    def processFile(self):
        print("### Processing Regression file: " + self.filePath)
        with open(self.filePath, 'r') as thefile:
            data = thefile.readlines()
        thefile.close()
        
        count = 0
        for idx, line in enumerate(data):
            if (line[0] == "#"):
                continue

            values = line.split()
            if (len(values) == 0):
                continue

            if (count == 0):
                print("Line ref: " + line)
                self.refDirPath = line
                count = count + 1
                continue

            

            if (len(values) < 4):
                print ("line read has more than 5 arguments: " + str(len(values)) + " -> " + line)
                continue

            fullFilePath = os.path.join(self.fileDir, values[0])
            if (len(values) == 5):
                sceneData = RegressionSceneData(fullFilePath, self.refDirPath, values[1], values[2], values[3], values[4])
            elif (len(values) == 4):
                sceneData = RegressionSceneData(fullFilePath, self.refDirPath, values[1], values[2], values[3], False)
            
            #sceneData.printInfo()
            self.scenes.append(sceneData)
            
        print("## nbrScenes: " + str(len(self.scenes)))
        # target = "SetTopologyAlgorithms"
        
        # new_file = open(filePath, "w")
        
        # for idx, line in enumerate(data):
        #     if re.search(target, line):
        #         continue;
            
        #     new_file.write(line)
        
        # new_file.close()


class RegressionProgram:
    def __init__(self, inputFolder):
        self.sceneSets = []
#def findRegressionFiles(inputFolder):
        for root, dirs, files in os.walk(inputFolder):
            for file in files:
                if file.endswith(".regression-tests"):
                    filePath = os.path.join(root, file)

                    sceneList = RegressionSceneList(filePath)

                    sceneList.processFile()
                    self.sceneSets.append(sceneList)
                    # if (debugInfo):
                    #     print("Regression file found: " + filePath)

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


#def isSimulated(mstate):
    

def parseNode(node, level = 0):
    for child in node.children:
        print (str(level) + " -> " + child.name.value)
        mstate = child.getMechanicalState()
        if (mstate):
            print ("   -> " + mstate.name.value)
        parseNode(child, level+1)
        

if __name__ == '__main__':
    # 1- Parse arguments to get folder path
    args = parse_args()

    # 2- Process file
    prog = RegressionProgram(args.input)
    
    print ("### Number of sets: " + str(len(prog.sceneSets)))

    for i in range(0, 4):
        firstSet = prog.sceneSets[1]
        print(firstSet.scenes[i].fileScenePath)
        rootNode = Sofa.Simulation.load(firstSet.scenes[i].fileScenePath)
        print("######## scene: " + str(firstSet.scenes[i].fileScenePath))
        parseNode(rootNode, 0)

    # if (!createReference)
    # {
    #     // Add CompareState components: as it derives from the ReadState, we use the ReadStateActivator to enable them.
    #     sofa::component::playback::CompareStateCreator compareVisitor(sofa::core::ExecParams::defaultInstance());

    #     compareVisitor.setCreateInMapping(data.m_mecaInMapping);
    #     compareVisitor.setSceneName(data.m_fileRefPath);
    #     compareVisitor.execute(root.get());

    #     sofa::component::playback::ReadStateActivator v_read(sofa::core::ExecParams::defaultInstance() /* PARAMS FIRST */, true);
    #     v_read.execute(root.get());
    # }
    # else // create reference
    # {
    #     msg_warning("StateRegression_test::runTestImpl") << "Non existing reference created: " << data.m_fileRefPath;

    #     // just to create an empty file to know it is already init
    #     std::ofstream filestream(data.m_fileRefPath.c_str());
    #     filestream.close();

    #     sofa::component::playback::WriteStateCreator writeVisitor(sofa::core::ExecParams::defaultInstance());

    #     if (data.m_dumpOnlyLastStep)
    #     {
    #         std::vector<double> times;
    #         times.push_back(0.0);
    #         times.push_back(root->getDt() * (data.m_steps - 1));
    #         writeVisitor.setExportTimes(times);
    #     }
    #     writeVisitor.setCreateInMapping(data.m_mecaInMapping);
    #     writeVisitor.setSceneName(data.m_fileRefPath);
    #     writeVisitor.execute(root.get());

    #     sofa::component::playback::WriteStateActivator v_write(sofa::core::ExecParams::defaultInstance() /* PARAMS FIRST */, true);
    #     v_write.execute(root.get());
    # }

    # for (unsigned int i = 0; i<data.m_steps; ++i)
    # {
    #     sofa::simulation::node::animate(root.get(), root->getDt());
    # }

    # if (!createReference)
    # {
    #     // Read the final error: the summation of all the error made at each time step
    #     sofa::component::playback::CompareStateResult result(sofa::core::ExecParams::defaultInstance());
    #     result.execute(root.get());

    #     double errorByDof = result.getErrorByDof() / double(result.getNumCompareState());
    #     if (errorByDof > data.m_epsilon)
    #     {
    #         msg_error("StateRegression_test::runTestImpl")
    #             << data.m_fileScenePath << ":" << msgendl
    #             << "    TOTALERROR: " << result.getTotalError() << msgendl
    #             << "    ERRORBYDOF: " << errorByDof;
    #     }
    # }
  
    