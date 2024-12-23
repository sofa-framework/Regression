import os
import RegressionSceneData
from tqdm import tqdm


## This class is responsible for loading a file.regression-tests to gather the list of scene to test with all arguments
## It will provide the API to launch the tests or write refs on all scenes contained in this file
class RegressionSceneList:
    def __init__(self, file_path, disable_progress_bar = False):
        """
        /// Path to the file.regression-tests containing the list of scene to tests with all arguments
        std::string filePath;
        """
        self.file_path = file_path
        self.file_dir = os.path.dirname(file_path)
        self.scenes = [] # List<RegressionSceneData>
        self.nbr_errors = 0
        self.ref_dir_path = None
        self.disable_progress_bar = disable_progress_bar


    def get_nbr_scenes(self):
        return len(self.scenes)
    
    def get_nbr_errors(self):
        return self.nbr_errors
    
    def log_scenes_errors(self):
        for scene in self.scenes:
            scene.log_errors()

    def process_file(self):
        with open(self.file_path, 'r') as the_file:
            data = the_file.readlines()
        the_file.close()
        
        count = 0
        for idx, line in enumerate(data):
            if line[0] == "#":
                continue

            values = line.split()
            if len(values) == 0:
                continue

            if count == 0:
                self.ref_dir_path = os.path.join(self.file_dir, values[0])
                self.ref_dir_path = os.path.abspath(self.ref_dir_path)
                count = count + 1
                continue


            if len(values) != 5:
                print ("line read has not 5 arguments: " + str(len(values)) + " -> " + line)
                continue

            full_file_path = os.path.join(self.file_dir, values[0])
            full_ref_file_path = os.path.join(self.ref_dir_path, values[0])

            if len(values) == 5:
                scene_data = RegressionSceneData.RegressionSceneData(full_file_path, full_ref_file_path,
                                                                     values[1], values[2], values[3], values[4],
                                                                     self.disable_progress_bar)
            
                #scene_data.printInfo()
                self.scenes.append(scene_data)


    def write_references(self, id_scene, print_log = False):
        self.scenes[id_scene].load_scene()
        if print_log is True:
            self.scenes[id_scene].print_meca_objs()
            
        self.scenes[id_scene].write_references()

    def write_all_references(self):
        nbr_scenes = len(self.scenes)
        pbar_scenes = tqdm(total=nbr_scenes, disable=self.disable_progress_bar)
        pbar_scenes.set_description("Write all scenes from: " + self.file_path)
        
        for i in range(0, nbr_scenes):
            self.write_references(i)
            pbar_scenes.update(1)
        pbar_scenes.close()
        
        return nbr_scenes


    def compare_references(self, id_scene):
        self.scenes[id_scene].load_scene()
        result = self.scenes[id_scene].compare_references()
        if not result:
            self.nbr_errors = self.nbr_errors + 1
        
    def compare_all_references(self):
        nbr_scenes = len(self.scenes)
        pbar_scenes = tqdm(total=nbr_scenes, disable=self.disable_progress_bar)
        pbar_scenes.set_description("Compare all scenes from: " + self.file_path)
        
        for i in range(0, nbr_scenes):
            self.compare_references(i)
            pbar_scenes.update(1)
        pbar_scenes.close()

        return nbr_scenes


    def replay_references(self, id_scene):
        self.scenes[id_scene].load_scene()
        self.scenes[id_scene].replay_references()
        
        
