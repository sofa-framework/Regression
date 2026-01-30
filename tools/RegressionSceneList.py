import os
import tools.RegressionSceneData as RegressionSceneData
from tqdm import tqdm
import re


## This class is responsible for loading a file.regression-tests to gather the list of scene to test with all arguments
## It will provide the API to launch the tests or write refs on all scenes contained in this file
class RegressionSceneList:
    def __init__(self, file_path, filter, disable_progress_bar = False, verbose = False):
        """
        /// Path to the file.regression-tests containing the list of scene to tests with all arguments
        std::string filePath;
        """
        self.file_path = file_path
        self.filter = filter
        self.file_dir = os.path.dirname(file_path)
        self.scenes_data_sets = [] # List<RegressionSceneData>
        self.nbr_errors = 0
        self.ref_dir_path = None
        self.disable_progress_bar = disable_progress_bar
        self.verbose = verbose


    def get_nbr_scenes(self):
        return len(self.scenes_data_sets)
    
    def get_nbr_errors(self):
        return self.nbr_errors
    
    def log_scenes_errors(self):
        for scene in self.scenes_data_sets:
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

                if not os.path.isdir(self.ref_dir_path):
                    print(f'Error: Reference directory mentioned by file \'{self.file_path}\' does not exist: {self.ref_dir_path}')
                    return

                if self.verbose:
                    print(f'Reference directory mentioned by file \'{self.file_path}\': {self.ref_dir_path}')
                count = count + 1
                continue


            if len(values) != 5:
                print ("line read has not 5 arguments: " + str(len(values)) + " -> " + line)
                continue

            if self.filter is not None and re.search(self.filter, values[0]) is None:
                if self.verbose:
                    print (f'Filtered out {self.filter}: {values[0]}')
                continue

            full_file_path = os.path.join(self.file_dir, values[0])
            full_ref_file_path = os.path.join(self.ref_dir_path, values[0])

            scene_data = RegressionSceneData.RegressionSceneData(full_file_path, full_ref_file_path,
                                                                 values[1], values[2], values[3], values[4],
                                                                 self.disable_progress_bar, self.verbose)

            #scene_data.printInfo()
            self.scenes_data_sets.append(scene_data)


    def write_references(self, id_scene, print_log = False):
        if self.verbose:
            print(f'Writing reference files for {self.scenes_data_sets[id_scene].file_scene_path}.')

        self.scenes_data_sets[id_scene].load_scene()
        if print_log is True:
            self.scenes_data_sets[id_scene].print_meca_objs()
            
        self.scenes_data_sets[id_scene].write_references()

    def write_all_references(self):
        nbr_scenes = len(self.scenes_data_sets)
        pbar_scenes = tqdm(total=nbr_scenes, disable=self.disable_progress_bar)
        pbar_scenes.set_description("Write all scenes from: " + self.file_path)
        
        for i in range(0, nbr_scenes):
            self.write_references(i)
            pbar_scenes.update(1)
        pbar_scenes.close()
        
        return nbr_scenes


    def compare_references(self, id_scene):
        if self.verbose:
            self.scenes_data_sets[id_scene].print_info()

        try:
            self.scenes_data_sets[id_scene].load_scene()
        except Exception as e:
            self.nbr_errors = self.nbr_errors + 1
            print(f'Error while trying to load: {str(e)}')
        else:
            result = self.scenes_data_sets[id_scene].compare_references()
            if not result:
                self.nbr_errors = self.nbr_errors + 1
        
    def compare_all_references(self):
        nbr_scenes = len(self.scenes_data_sets)
        pbar_scenes = tqdm(total=nbr_scenes, disable=self.disable_progress_bar)
        pbar_scenes.set_description("Compare all scenes from: " + self.file_path)
        
        for i in range(0, nbr_scenes):
            self.compare_references(i)
            pbar_scenes.update(1)
        pbar_scenes.close()

        return nbr_scenes


    def replay_references(self, id_scene):
        self.scenes_data_sets[id_scene].load_scene()
        self.scenes_data_sets[id_scene].add_compare_state()
        self.scenes_data_sets[id_scene].replay_references()
        
        
