import sys, os
import RegressionSceneData
from tqdm import tqdm


## This class is responsible for loading a file.regression-tests to gather the list of scene to test with all arguments
## It will provide the API to launch the tests or write refs on all scenes contained in this file
class RegressionSceneList:
    def __init__(self, filePath):
        """
        /// Path to the file.regression-tests containing the list of scene to tests with all arguments
        std::string filePath;
        """
        self.filePath = filePath
        self.fileDir = os.path.dirname(filePath)
        self.scenes = [] # List<RegressionSceneData>
        self.nbrErrors = 0


    def getNbrScenes(self):
        return len(self.scenes)
    
    def getNbrErrors(self):
        return self.nbrErrors
    
    def logScenesErrors(self):
        for scene in self.scenes:
            scene.logErrors()

    def processFile(self):
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
                sceneData = RegressionSceneData.RegressionSceneData(fullFilePath, fullRefFilePath, values[1], values[2], values[3], values[4])
            
            #sceneData.printInfo()
            self.scenes.append(sceneData)


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
        
        return nbrScenes


    def compareReferences(self, idScene):
        self.scenes[idScene].loadScene()
        result = self.scenes[idScene].compareReferences()
        if (result == False):
            self.nbrErrors = self.nbrErrors + 1
        
    def compareAllReferences(self):
        nbrScenes = len(self.scenes)
        pbarScenes = tqdm(total=nbrScenes)
        pbarScenes.set_description("Compare all scenes from: " + self.filePath)
        
        for i in range(0, nbrScenes):
            self.compareReferences(i)
            pbarScenes.update(1)
        pbarScenes.close()
        
        return nbrScenes
