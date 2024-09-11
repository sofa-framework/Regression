from tqdm import tqdm
import json
from json import JSONEncoder
import numpy as np
import gzip

import Sofa
import Sofa.Simulation
import Sofa.Gui

debugInfo = False

def isSimulated(node):
    if (node.hasODESolver()):
        return True

    # if no Solver in current node, check parent nodes
    for parent in node.parents:
        solverFound = isSimulated(parent)
        if (solverFound):
            return True
        
    return False


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


class NumpyArrayEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return JSONEncoder.default(self, obj)


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
        self.steps = int(steps)
        self.epsilon = float(epsilon)
        self.mecaInMapping = mecaInMapping
        self.dumpNumberStep = int(dumpNumberStep)
        self.mecaObjs = []
        self.fileNames = []
        self.mins = []
        self.maxs = []
        self.totalError = []
        self.errorByDof = []
        self.nbrTestedFrame = 0
        self.regressionFailed = False

    def printInfo(self):
        print("Test scene: " + self.fileScenePath + " vs " + self.fileRefPath + " using: " + self.steps
              + " " + self.epsilon)
        
    def logErrors(self):
        if self.regressionFailed is True:
            print("### Failed: " + self.fileScenePath)
            print("    ### Total Error per MechanicalObject: " + str(self.totalError))
            print("    ### Error by Dofs: " + str(self.errorByDof))
        else:
            print ("### Success: " + self.fileScenePath + " | Number of key frames compared without error: " + str(self.nbrTestedFrame))
    
    
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
        moduloStep = (self.steps) / self.dumpNumberStep
        
        for step in range(0, self.steps + 1):
            # export rest position, final position + modulo steps:
            if (step == 0 or counterStep >= moduloStep or step == self.steps):                
                #print("step: " + str(step) + " | counterStep: " + str(counterStep) + " | moduloStep: " + str(moduloStep) + " | dt: " + str(self.rootNode.dt.value*(step)))
                for mecaId in range(0, nbrMeca):
                    numpyData[mecaId][self.rootNode.dt.value*(step)] = np.copy(self.mecaObjs[mecaId].position.value)
                counterStep = 0
            
            Sofa.Simulation.animate(self.rootNode, self.rootNode.dt.value)
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
        self.totalError = []
        self.errorByDof = []
        
        for mecaId in range(0, nbrMeca):
            with gzip.open(self.fileNames[mecaId], 'r') as zipfile:
                decodedArray = json.loads(zipfile.read().decode('utf-8'))
                numpyData.append(decodedArray)

                if (mecaId is 0):
                    for key in decodedArray:
                        keyframes.append(float(key))
            
            self.totalError.append(0.0)
            self.errorByDof.append(0.0)

                    
        frameStep = 0
        nbrFrames = len(keyframes)        
        self.nbrTestedFrame = 0
        for step in range(0, self.steps + 1):
            simuTime = self.rootNode.dt.value*(step)

            if (simuTime == keyframes[frameStep]):
                for mecaId in range(0, nbrMeca):
                    mecaDofs = np.copy(self.mecaObjs[mecaId].position.value)
                    dataRef = np.asarray(numpyData[mecaId][str(keyframes[frameStep])]) - mecaDofs
                    
                    # Compute total distance between the 2 sets
                    fullDist = np.linalg.norm(dataRef)
                    errorByDof = fullDist / float(dataRef.size)
                    
                    if (debugInfo is True):
                        print (str(step) + "| " + self.mecaObjs[mecaId].name.value + " | fullDist: " + str(fullDist) + " | errorByDof: " + str(errorByDof) + " | nbrDofs: " + str(dataRef.size)) 

                    self.totalError[mecaId] = self.totalError[mecaId] + fullDist
                    self.errorByDof[mecaId] = self.errorByDof[mecaId] + errorByDof

                frameStep = frameStep + 1
                self.nbrTestedFrame = self.nbrTestedFrame + 1
                
                # security exit if simulation steps exceed nbrFrames
                if (frameStep == nbrFrames):
                    break
            
            Sofa.Simulation.animate(self.rootNode, self.rootNode.dt.value)
            
            pbarSimu.update(1)
        pbarSimu.close()
        
        for mecaId in range(0, nbrMeca):
            if (self.totalError[mecaId] > self.epsilon):
                self.regressionFailed = True
                return False
        
        return True
    

    def replayReferences(self):
        Sofa.Gui.GUIManager.Init("myscene", "qglviewer")
        Sofa.Gui.GUIManager.createGUI(self.rootNode, __file__)
        Sofa.Gui.GUIManager.SetDimension(1080, 1080)
        Sofa.Gui.GUIManager.MainLoop(self.rootNode)
        Sofa.Gui.GUIManager.closeGUI()



