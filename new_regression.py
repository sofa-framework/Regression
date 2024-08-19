import glob, os
import argparse
import sys
import Sofa
import SofaRuntime
import numpy as np
from tqdm import tqdm
from json import JSONEncoder
import json
import gzip

debugInfo = True

def isSimulated(node):
    if (node.hasODESolver()):
        return True

    # if no Solver in current node, check parent nodes
    for parent in node.parents:
        solverFound = isSimulated(parent)
        if (solverFound):
            return True
        
    return False


class NumpyArrayEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return JSONEncoder.default(self, obj)

def exportJson():

    numpyArrayOne = np.array([[11 ,22, 33], [44, 55, 66], [77, 88, 99]])
    numpyArrayTwo = np.array([[51, 61, 91], [121 ,118, 127]])

    # Serialization
    numpyData = {"arrayOne": numpyArrayOne, "arrayTwo": numpyArrayTwo}
    print("serialize NumPy array into JSON and write into a file")
    with gzip.open("numpyData.json.gz", 'w') as zipfile:
        for key in numpyData:
            print(numpyData[key])

        #write_file.write(json.dumps(numpyData, cls=NumpyArrayEncoder, indent=4))
        #res = json.dumps(numpyData, cls=NumpyArrayEncoder, indent=4)
        #print(res)
        #json.dump(numpyData, zipfile, cls=NumpyArrayEncoder)
        zipfile.write(json.dumps(numpyData, cls=NumpyArrayEncoder).encode('utf-8'))
    
    print("Done writing serialized NumPy array into file")

def readJson():
    # Deserialization
    print("Started Reading JSON file")
    with gzip.open("numpyData.json.gz", 'r') as zipfile:

    #with open("numpyData.json", "r") as read_file:
        print("Converting JSON encoded data into Numpy array")
        decodedArray = json.loads(zipfile.read().decode('utf-8'))
        #decodedArray = json.load(zipfile)

        finalNumpyArrayOne = np.asarray(decodedArray["arrayOne"])
        print("NumPy Array One")
        print(finalNumpyArrayOne)
        finalNumpyArrayTwo = np.asarray(decodedArray["arrayTwo"])
        print("NumPy Array Two")
        print(finalNumpyArrayTwo)



class RegressionSceneData:
    def __init__(self, fileScenePath: str = None, fileRefPath: str = None, steps = 1000, 
                 epsilon = 0.0001, mecaInMapping = True, dumpNumberStep = 1):
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
        bool m_dumpNumberStep;    
        """
        self.fileScenePath = fileScenePath
        self.fileRefPath = fileRefPath
        self.steps = int(steps) + 1
        self.epsilon = float(epsilon)
        self.mecaInMapping = mecaInMapping
        self.dumpNumberStep = int(dumpNumberStep)
        self.mecaObjs = []
        self.fileNames = []
        self.mins = []
        self.maxs = []

    def printInfo(self):
        print("Test scene: " + self.fileScenePath + " vs " + self.fileRefPath + " using: " + self.steps
              + " " + self.epsilon)
    
    
    def printMecaObjs(self):
        print ("# Nbr Meca: " + str(len(self.mecaObjs)))
        counter = 0
        for mecaObj in self.mecaObjs:
            filename = self.fileRefPath + ".reference_" + str(counter) + "_" + mecaObj.name.value + "_mstate" + ".txt.gz"
            counter = counter+1
            print ("# File attached: " + filename)


    def parseNode(self, node, level = 0):
        for child in node.children:
            mstate = child.getMechanicalState()
            if (mstate):
                if (isSimulated(child)):
                    self.mecaObjs.append(mstate)
            
            self.parseNode(child, level+1)
    

    def addCompareState(self):
        counter = 0
        for mecaObj in self.mecaObjs:
            _filename = self.fileRefPath + ".reference_" + str(counter) + "_" + mecaObj.name.value + "_mstate" + ".txt.gz"
            
            mecaObj.getContext().addObject('CompareState', filename=_filename)
            counter = counter+1


    def addWriteState(self):
        counter = 0
        for mecaObj in self.mecaObjs:
            _filename = self.fileRefPath + ".reference_" + str(counter) + "_" + mecaObj.name.value + "_mstate" + ".txt.gz"
            
            mecaObj.getContext().addObject('WriteState', filename=_filename)
            counter = counter+1
    

    def loadScene(self):
        self.rootNode = Sofa.Simulation.load(self.fileScenePath)
        Sofa.Simulation.init(self.rootNode)
        
        # prepare ref files per mecaObjs:
        self.parseNode(self.rootNode, 0)
        counter = 0
        for mecaObj in self.mecaObjs:
            _filename = self.fileRefPath + ".reference_mstate_" + str(counter) + "_" + mecaObj.name.value + ".json.gz"
            self.fileNames.append(_filename)
            counter = counter+1
        


    def writeReferences(self):
        pbarSimu = tqdm(total=self.steps)
        pbarSimu.set_description("Simulate: " + self.fileScenePath)
        
        nbrMeca = len(self.mecaObjs)
        numpyData = [] # List<map>
        for mecaId in range(0, nbrMeca):
            mecaDofs = {}
            numpyData.append(mecaDofs)

        
        counterStep = 0
        moduloStep = (self.steps-1) / self.dumpNumberStep
        
        # export rest position:
        for mecaId in range(0, nbrMeca):
            numpyData[mecaId][0.0] = np.copy(self.mecaObjs[mecaId].position.value)

        for step in range(0, self.steps):
            Sofa.Simulation.animate(self.rootNode, self.rootNode.dt.value)
            
            #print("step: " + str(step) + " | counterStep: " + str(counterStep) + " | moduloStep: " + str(moduloStep) + " | dt: " + str(self.rootNode.dt.value*(step)))
            if (counterStep >= moduloStep or step == self.steps - 1):
                for mecaId in range(0, nbrMeca):
                    numpyData[mecaId][self.rootNode.dt.value*(step)] = np.copy(self.mecaObjs[mecaId].position.value)
                counterStep = 0
            
            counterStep = counterStep + 1
            pbarSimu.update(1)
        pbarSimu.close()

        for mecaId in range(0, nbrMeca):
            #for key in numpyData[mecaId]:
            #    print("key: %s , value: %s" % (key, numpyData[mecaId][key][820]))
            with gzip.open(self.fileNames[mecaId], "w") as write_file:
                write_file.write(json.dumps(numpyData[mecaId], cls=NumpyArrayEncoder).encode('utf-8'))

        Sofa.Simulation.unload(self.rootNode)
        

    def compareReferences(self):
        pbarSimu = tqdm(total=float(self.steps))
        pbarSimu.set_description("compareReferences: " + self.fileScenePath)
        
        nbrMeca = len(self.mecaObjs)
        numpyData = [] # List<map>
        keyframes = []
        for mecaId in range(0, nbrMeca):
            with gzip.open(self.fileNames[mecaId], 'r') as zipfile:
                decodedArray = json.loads(zipfile.read().decode('utf-8'))
                numpyData.append(decodedArray)

                if (mecaId is 0):
                    for key in decodedArray:
                        keyframes.append(float(key))
                    
        frameStep = 0
        nbrFrames = len(keyframes)
        for step in range(0, self.steps):
            Sofa.Simulation.animate(self.rootNode, self.rootNode.dt.value)
            simuTime = self.rootNode.dt.value*(step)
            #print ("time: " + str(simuTime))
            if (simuTime == keyframes[frameStep]):
                print("### Found same time: " + str(keyframes[frameStep]))

                for mecaId in range(0, nbrMeca):
                    #numpyData[mecaId][self.rootNode.dt.value*(step)] = np.copy(self.mecaObjs[mecaId].position.value)
                    print(self.mecaObjs[mecaId].position.value[820])
                    mecaDofs = np.copy(self.mecaObjs[mecaId].position.value)
                    dataRef = np.asarray(numpyData[mecaId][str(keyframes[frameStep])]) - mecaDofs
                    print(dataRef[820])
                    dist = np.linalg.norm(dataRef)
                    print("dist: " + str(dist))

                frameStep = frameStep + 1
                if (frameStep == nbrFrames):
                    print ("exit comparison")
                    return
            
            pbarSimu.update(1)
        pbarSimu.close()


class RegressionSceneList:
    def __init__(self, filePath):
        self.filePath = filePath
        self.fileDir = os.path.dirname(filePath)
        self.scenes = [] # List<RegressionSceneData>

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
                self.refDirPath = os.path.join(self.fileDir, values[0])
                self.refDirPath = os.path.abspath(self.refDirPath)
                count = count + 1
                continue


            if (len(values) != 5):
                print ("line read has not 5 arguments: " + str(len(values)) + " -> " + line)
                continue

            fullFilePath = os.path.join(self.fileDir, values[0])
            fullRefFilePath = os.path.join(self.refDirPath, values[0])

            if (len(values) == 5):
                sceneData = RegressionSceneData(fullFilePath, fullRefFilePath, values[1], values[2], values[3], values[4])
            
            #sceneData.printInfo()
            self.scenes.append(sceneData)
            
        print("## nbrScenes: " + str(len(self.scenes)))

    def writeReferences(self, idScene, printLog = False):
        self.scenes[idScene].loadScene()
        if (printLog is True):
            self.scenes[idScene].printMecaObjs()
            
        self.scenes[idScene].writeReferences()

    def writeAllReferences(self):
        nbrScenes = len(self.scenes)
        pbarScenes = tqdm(total=nbrScenes)
        pbarScenes.set_description("Write all scenes from: " + self.filePath)
        for i in range(0, nbrScenes):
            self.writeReferences(i)
            pbarScenes.update(1)
        pbarScenes.close()


    def compareReferences(self, idScene):
        self.scenes[idScene].loadScene()
        self.scenes[idScene].compareReferences()
        
    def compareAllReferences(self):
        nbrScenes = len(self.scenes)
        pbarScenes = tqdm(total=nbrScenes)
        pbarScenes.set_description("Compare all scenes from: " + self.filePath)
        for i in range(0, nbrScenes):
            self.compareReferences(i)
            pbarScenes.update(1)
        pbarScenes.close()



class RegressionProgram:
    def __init__(self, inputFolder):
        self.sceneSets = [] # List <RegressionSceneList>

        for root, dirs, files in os.walk(inputFolder):
            for file in files:
                if file.endswith(".regression-tests"):
                    filePath = os.path.join(root, file)

                    sceneList = RegressionSceneList(filePath)

                    sceneList.processFile()
                    self.sceneSets.append(sceneList)

    def writeSetsReferences(self, idSet = 0):
        sceneList = self.sceneSets[idSet]
        sceneList.writeAllReferences()
    
    def writeAllSetsReferences(self):
        nbrSets = len(self.sceneSets)
        pbarSets = tqdm(total=nbrSets)
        pbarSets.set_description("Write All sets")
        for i in range(0, nbrSets):
            self.writeSetsReferences(i)
            pbarSets.update(1)
        pbarSets.close()


    def compareSetsReferences(self, idSet = 0):
        sceneList = self.sceneSets[idSet]
        sceneList.compareAllReferences()
        
    def compareAllSetsReferences(self):
        nbrSets = len(self.sceneSets)
        pbarSets = tqdm(total=nbrSets)
        pbarSets.set_description("Compare All sets")
        for i in range(0, nbrSets):
            self.compareSetsReferences(i)
            pbarSets.update(1)
        pbarSets.close()



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
        "--writeRef",
        dest="writeMode",
        default=False,
        help='If true, will generate new reference files'
    )
    
    args = parser.parse_args()

    return args



        

if __name__ == '__main__':
    # 1- Parse arguments to get folder path
    args = parse_args()
    # 2- Process file
    regProg = RegressionProgram(args.input)
    SofaRuntime.importPlugin("SofaPython3")

    print ("### Number of sets: " + str(len(regProg.sceneSets)))
    if (args.writeMode):
        regProg.writeAllSetsReferences()
    else:
        regProg.compareAllSetsReferences(0)
    print ("### Number of sets Done:  " + str(len(regProg.sceneSets)))
   
    sys.exit()

    