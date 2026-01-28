from tqdm import tqdm
import json
from json import JSONEncoder
import numpy as np
import gzip
import pathlib

import Sofa
import Sofa.Gui

debug_info = False

def is_simulated(node):
    if node.hasODESolver():
        return True

    # if no Solver in current node, check parent nodes
    for parent in node.parents:
        solver_found = is_simulated(parent)
        if solver_found:
            return True
        
    return False


class NumpyArrayEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return JSONEncoder.default(self, obj)

    
def is_mapped(node):
    mapping = node.getMechanicalMapping()

    if mapping is None:
        return False
    else:
        return True
    # no mapping in this node context



class RegressionSceneData:
    def __init__(self, file_scene_path: str = None, file_ref_path: str = None, steps = 1000,
                 epsilon = 0.0001, meca_in_mapping = True, dump_number_step = 1, disable_progress_bar = False):
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
        self.file_scene_path = file_scene_path
        self.file_ref_path = file_ref_path
        self.steps = int(steps)
        self.epsilon = float(epsilon)
        self.meca_in_mapping = meca_in_mapping
        self.dump_number_step = int(dump_number_step)
        self.meca_objs = []
        self.filenames = []
        self.mins = []
        self.maxs = []
        self.total_error = []
        self.error_by_dof = []
        self.nbr_tested_frame = 0
        self.regression_failed = False
        self.root_node = None
        self.disable_progress_bar = disable_progress_bar

    def print_info(self):
        print("Test scene: " + self.file_scene_path + " vs " + self.file_ref_path + " using: " + str(self.steps)
              + " " + str(self.epsilon))
        
    def log_errors(self):
        if self.regression_failed is True:
            print("### Failed: " + self.file_scene_path)
            print("    ### Total Error per MechanicalObject: " + str(self.total_error))
            print("    ### Error by Dofs: " + str(self.error_by_dof))
        else:
            print ("### Success: " + self.file_scene_path + " | Number of key frames compared without error: " + str(self.nbr_tested_frame))
    
    
    def print_meca_objs(self):
        print ("# Nbr Meca: " + str(len(self.meca_objs)))
        counter = 0
        for mecaObj in self.meca_objs:
            filename = self.file_ref_path + ".reference_" + str(counter) + "_" + mecaObj.name.value + "_mstate" + ".txt.gz"
            counter = counter+1
            print ("# File attached: " + filename)


    def parse_node(self, node, level = 0):
        for child in node.children:
            mstate = child.getMechanicalState()
            if mstate and is_simulated(child):
                
                if self.meca_in_mapping is True or not is_mapped(child):
                    self.meca_objs.append(mstate)

            self.parse_node(child, level + 1)
    

    def add_compare_state(self):
        counter = 0
        for meca_obj in self.meca_objs:
            _filename = self.file_ref_path + ".reference_" + str(counter) + "_" + meca_obj.name.value + "_mstate" + ".txt.gz"
            
            meca_obj.getContext().addObject('CompareState', filename=_filename)
            counter = counter+1


    def add_write_state(self):
        counter = 0
        for meca_obj in self.meca_objs:
            _filename = self.file_ref_path + ".reference_" + str(counter) + "_" + meca_obj.name.value + "_mstate" + ".txt.gz"
            
            meca_obj.getContext().addObject('WriteState', filename=_filename)
            counter = counter+1
    

    def load_scene(self):
        self.root_node = Sofa.Simulation.load(self.file_scene_path)
        if not self.root_node: # error while loading
            print(f'Error while trying to load {self.file_scene_path}')
            raise RuntimeError
        else:
            Sofa.Simulation.init(self.root_node)

            # prepare ref files per mecaObjs:
            self.parse_node(self.root_node, 0)
            counter = 0
            for mecaObj in self.meca_objs:
                _filename = self.file_ref_path + ".reference_mstate_" + str(counter) + "_" + mecaObj.name.value + ".json.gz"
                self.filenames.append(_filename)
                counter = counter+1
        


    def write_references(self):
        pbar_simu = tqdm(total=self.steps, disable=self.disable_progress_bar)
        pbar_simu.set_description("Simulate: " + self.file_scene_path)
        
        nbr_meca = len(self.meca_objs)
        numpy_data = [] # List<map>
        for meca_id in range(0, nbr_meca):
            meca_dofs = {}
            numpy_data.append(meca_dofs)

        
        counter_step = 0
        modulo_step = self.steps / self.dump_number_step
        
        for step in range(0, self.steps + 1):
            # export rest position, final position + modulo steps:
            if step == 0 or counter_step >= modulo_step or step == self.steps:
                for meca_id in range(0, nbr_meca):
                    numpy_data[meca_id][self.root_node.dt.value * step] = np.copy(self.meca_objs[meca_id].position.value)
                counter_step = 0
            
            Sofa.Simulation.animate(self.root_node, self.root_node.dt.value)
            counter_step = counter_step + 1
                        
            pbar_simu.update(1)
        pbar_simu.close()

        for meca_id in range(0, nbr_meca):
            # make sure the parent directory of the references exists
            output_file = pathlib.Path(self.filenames[meca_id])
            output_file.parent.mkdir(exist_ok=True, parents=True)

            with gzip.open(self.filenames[meca_id], 'wb') as write_file:
                write_file.write(json.dumps(numpy_data[meca_id], cls=NumpyArrayEncoder).encode('utf-8'))

        Sofa.Simulation.unload(self.root_node)
        

    def compare_references(self):
        pbar_simu = tqdm(total=float(self.steps), disable=self.disable_progress_bar)
        pbar_simu.set_description("compare_references: " + self.file_scene_path)
        
        nbr_meca = len(self.meca_objs)
        numpy_data = [] # List<map>
        keyframes = []
        self.total_error = []
        self.error_by_dof = []

        try:
            for meca_id in range(0, nbr_meca):
                with gzip.open(self.filenames[meca_id], 'r') as zipfile:
                    decoded_array = json.loads(zipfile.read().decode('utf-8'))
                    numpy_data.append(decoded_array)

                    if meca_id == 0:
                        for key in decoded_array:
                            keyframes.append(float(key))

                self.total_error.append(0.0)
                self.error_by_dof.append(0.0)
        except FileNotFoundError as e:
            print(f'Error while reading references: {str(e)}')
            return False

                    
        frame_step = 0
        nbr_frames = len(keyframes)
        self.nbr_tested_frame = 0
        for step in range(0, self.steps + 1):
            simu_time = self.root_node.dt.value * step

            if simu_time == keyframes[frame_step]:
                for meca_id in range(0, nbr_meca):
                    meca_dofs = np.copy(self.meca_objs[meca_id].position.value)
                    data_ref = np.asarray(numpy_data[meca_id][str(keyframes[frame_step])])
                    if (meca_dofs.size != data_ref.size):
                        print(f'Error while reading reference for file {self.file_scene_path} at mechanicalObject id: {str(meca_id)}. Reference size: {data_ref.size} vs current size: {meca_dofs.size}')
                        return False
                    
                    data_diff = data_ref - meca_dofs
                    
                    # Compute total distance between the 2 sets
                    full_dist = np.linalg.norm(data_diff)
                    error_by_dof = full_dist / float(data_diff.size)
                    
                    if debug_info:
                        print (str(step) + "| " + self.meca_objs[meca_id].name.value + " | full_dist: " + str(full_dist) + " | error_by_dof: " + str(error_by_dof) + " | nbrDofs: " + str(data_ref.size))

                    self.total_error[meca_id] = self.total_error[meca_id] + full_dist
                    self.error_by_dof[meca_id] = self.error_by_dof[meca_id] + error_by_dof

                frame_step = frame_step + 1
                self.nbr_tested_frame = self.nbr_tested_frame + 1
                
                # security exit if simulation steps exceed nbr_frames
                if frame_step == nbr_frames:
                    break
            
            Sofa.Simulation.animate(self.root_node, self.root_node.dt.value)
            
            pbar_simu.update(1)
        pbar_simu.close()
        
        for meca_id in range(0, nbr_meca):
            if self.total_error[meca_id] > self.epsilon:
                self.regression_failed = True
                return False
        
        return True
    

    def replayReferences(self):
        Sofa.Gui.GUIManager.Init("myscene", "qglviewer")
        Sofa.Gui.GUIManager.createGUI(self.root_node, __file__)
        Sofa.Gui.GUIManager.SetDimension(1080, 1080)
        Sofa.Gui.GUIManager.MainLoop(self.root_node)
        Sofa.Gui.GUIManager.closeGUI()



