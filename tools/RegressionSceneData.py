from tqdm import tqdm
import numpy as np
import pathlib

import gzip
import tools.ReferenceFileIO as reference_io
import Sofa

class TermColor:
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def is_simulated(node):
    if node.hasODESolver():
        return True

    # if no Solver in current node, check parent nodes
    for parent in node.parents:
        solver_found = is_simulated(parent)
        if solver_found:
            return True
        
    return False


class ReplayState(Sofa.Core.Controller):
    def __init__(self, node, slave_mo, state_filename, **kwargs):
        super().__init__(**kwargs)
        self.node = node
        self.slave_mo = slave_mo
        self.keyframes = []
        self.frame_step = 0
        self.t_sim = 0.0

        try:
            self.ref_data, self.keyframes = reference_io.read_JSON_reference_file(state_filename)
        except Exception as e:
            print(f"{TermColor.RED}[Error]{TermColor.RESET} While reading reference for replay: {str(e)}")
            raise RuntimeError(f"Failed to read reference for replay: {str(e)}")
        
        if (self.keyframes[0] == 0.0): # frame 0.0
            tmp_position = np.asarray(self.ref_data[str(self.keyframes[0])])
            self.slave_mo.position = tmp_position.tolist()
            self.frame_step = 1
           
    def onAnimateEndEvent(self, event):
       dt = float(self.node.getRootContext().dt.value)
       self.t_sim += dt

       if abs(self.t_sim - self.keyframes[self.frame_step]) < 0.000001:
           tmp_position = np.asarray(self.ref_data[str(self.keyframes[self.frame_step])])
           self.slave_mo.position = tmp_position.tolist()
           self.frame_step += 1


# --------------------------------------------------
# Helper: read the legacy state reference format
# --------------------------------------------------
def read_legacy_reference(filename, mechanical_object):
    ref_data = []
    times = []
    values = []

    # Infer layout from MechanicalObject
    n_points, dof_per_point = mechanical_object.position.value.shape
    expected_size = n_points * dof_per_point


    with gzip.open(filename, "rt") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            # Time marker
            if line.startswith("T="):
                current_time = float(line.split("=", 1)[1])
                times.append(current_time)
         
            # Positions
            elif line.startswith("X="):
                if current_time is None:
                    raise RuntimeError(f"X found before T in {filename}")

                raw = line.split("=", 1)[1].strip().split()
                flat = np.asarray(raw, dtype=float)

                if flat.size != expected_size:
                    raise ValueError(
                        f"Legacy reference size mismatch in {filename}: "
                        f"expected {expected_size}, got {flat.size}\n"
                    )

                values.append(flat.reshape((n_points, dof_per_point)))

            # Velocity (ignored)
            elif line.startswith("V="):
                continue

    if len(times) != len(values):
        raise RuntimeError(
            f"Legacy reference corrupted in {filename}: "
            f"{len(times)} times vs {len(values)} X blocks"
        )

    return times, values




    
def is_mapped(node):
    mapping = node.getMechanicalMapping()

    return mapping != None
    # no mapping in this node context



class RegressionSceneData:
    def __init__(self, file_scene_path: str = None, file_ref_path: str = None, steps = 1000,
                 epsilon = 0.0001, meca_in_mapping = True, dump_number_step = 1, disable_progress_bar = False, verbose = False):
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
        self.meca_in_mapping = bool(meca_in_mapping)
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
        self.verbose = verbose

    def print_info(self):
        print("Test scene: " + self.file_scene_path + " vs " + self.file_ref_path + " using: " + str(self.steps)
              + " " + str(self.epsilon))
        
    def log_errors(self):
        if self.regression_failed is True:
            print(f"### {TermColor.RED}[Failed]{TermColor.RESET} {self.file_scene_path}")
            print("    ### Total Error per MechanicalObject: " + str(self.total_error))
            print("    ### Error by Dofs: " + str(self.error_by_dof))
        elif self.nbr_tested_frame == 0:
            print(f"### {TermColor.RED}[Failed]{TermColor.RESET} No frames were tested for {self.file_scene_path}")
        else:
            print(f"### {TermColor.GREEN}[Success]{TermColor.RESET} {self.file_scene_path} | Number of key frames compared without error: {self.nbr_tested_frame}")

    def print_meca_objs(self):
        print ("# Nbr Meca: " + str(len(self.meca_objs)))
        counter = 0
        for mecaObj in self.meca_objs:
            filename = self.file_ref_path + ".reference_" + str(counter) + "_" + mecaObj.name.value + "_mstate" + ".txt.gz"
            counter = counter+1
            print ("# File attached: " + filename)


    def parse_node(self, node, level = 0):
        # first check current node
        mstate = node.getMechanicalState()
        if mstate and is_simulated(node):
            if self.meca_in_mapping is True or is_mapped(node) is False:
                self.meca_objs.append(mstate)
                if self.verbose:
                    print("  " * level + f"- Adding MechanicalObject: {mstate.name.value} from Node: {node.name.value}")

        # recursively check children
        for child in node.children:
            self.parse_node(child, level + 1)


    def add_compare_state(self):
        counter = 0
        for meca_obj in self.meca_objs:
            # Use this filename format to be compatible with previous version
            #_filename = self.file_ref_path + ".reference_" + str(counter) + "_" + meca_obj.name.value + "_mstate" + ".txt.gz"
            _filename = self.file_ref_path + ".reference_mstate_" + str(counter) + "_" + meca_obj.name.value + ".json.gz"
            
            compareNode = meca_obj.getContext().addChild("CompareStateNode_"+str(counter))
            cloudPoint = compareNode.addObject('VisualPointCloud', pointSize=10, drawMode="Point", color="green")
            compareNode.addObject(ReplayState(node=compareNode, slave_mo=cloudPoint, state_filename=_filename))
            counter = counter+1


    def add_write_state(self):
        counter = 0
        for meca_obj in self.meca_objs:
            _filename = self.file_ref_path + ".reference_" + str(counter) + "_" + meca_obj.name.value + "_mstate" + ".txt.gz"
            
            meca_obj.getContext().addObject('WriteState', filename=_filename)
            counter = counter+1
    

    def load_scene(self, format = "JSON"):
        self.root_node = Sofa.Simulation.load(self.file_scene_path)
        if not self.root_node: # error while loading
            print(f'{TermColor.RED}[Error]{TermColor.RESET} While trying to load {self.file_scene_path}')
            raise RuntimeError
        else:
            Sofa.Simulation.initRoot(self.root_node)

            # prepare ref files per mecaObjs:
            self.parse_node(self.root_node, 0)
            counter = 0
            for mecaObj in self.meca_objs:
                if format == "CSV":
                    _filename = self.file_ref_path + ".reference_mstate_" + str(counter) + "_" + mecaObj.name.value + ".csv.gz"
                elif format == "JSON":
                    _filename = self.file_ref_path + ".reference_mstate_" + str(counter) + "_" + mecaObj.name.value + ".json.gz"
                self.filenames.append(_filename)
                counter = counter+1
        

    def write_references(self, format = "JSON"):
        pbar_simu = tqdm(total=self.steps, disable=self.disable_progress_bar)
        pbar_simu.set_description("Simulate: " + self.file_scene_path)

        # compute stepping parameters for the simulation
        counter_step = 0
        modulo_step = self.steps / self.dump_number_step
        dt = self.root_node.dt.value
        
        # prepae per-mechanical-object data
        nbr_meca = len(self.meca_objs)
        if format == "CSV":
            csv_rows = [[] for _ in range(nbr_meca)]
        elif format == "JSON":
            numpy_data = [] # List<map>
            for meca_id in range(0, nbr_meca):
                meca_dofs = {}
                numpy_data.append(meca_dofs)
        else:
            print(f"Unsupported format: {format}")
            raise ValueError(f"Unsupported format: {format}")

        for step in range(0, self.steps + 1):
            if step == 0 or counter_step >= modulo_step or step == self.steps:
                t = dt * step
                for meca_id in range(nbr_meca):
                    positions = np.asarray(self.meca_objs[meca_id].position.value)

                    if format == "CSV":
                        row = [t]
                        row.extend(positions.reshape(-1).tolist())  # flatten vec3d
                        csv_rows[meca_id].append(row)
                    elif format == "JSON":
                        numpy_data[meca_id][t] = np.copy(positions)
                
                counter_step = 0
            
            Sofa.Simulation.animate(self.root_node, dt)
            counter_step += 1
            pbar_simu.update(1)

        pbar_simu.close()

        # write reference files
        for meca_id in range(nbr_meca):
            output_file = pathlib.Path(self.filenames[meca_id])
            output_file.parent.mkdir(exist_ok=True, parents=True)

            if format == "CSV":
                dof_per_point = self.meca_objs[meca_id].position.value.shape[1]
                n_points = self.meca_objs[meca_id].position.value.shape[0]
                reference_io.write_CSV_reference_file(self.filenames[meca_id], dof_per_point, n_points, csv_rows[meca_id])               
            elif format == "JSON":
                reference_io.write_JSON_reference_file(self.filenames[meca_id], numpy_data[meca_id])

        Sofa.Simulation.unload(self.root_node)


    def compare_references(self, format = "JSON"):
        pbar_simu = tqdm(total=float(self.steps), disable=self.disable_progress_bar)
        pbar_simu.set_description("compare_references: " + self.file_scene_path)

        nbr_meca = len(self.meca_objs)
        
        # Reference data
        keyframes = []  # shared timeline
        if format == "CSV":
            ref_values = []         # List[List[np.ndarray]]
        elif format == "JSON":
            numpy_data = [] # List<map>
        else:
            print(f"Unsupported format: {format}")
            raise ValueError(f"Unsupported format: {format}")

        # Outputs init
        self.total_error = []
        self.error_by_dof = []
        self.nbr_tested_frame = 0
        self.regression_failed = False

        # --------------------------------------------------
        # Load reference files
        # --------------------------------------------------
        for meca_id in range(nbr_meca):
            try:
                if format == "CSV":
                    meta, rows = reference_io.read_CSV_reference_file(self.filenames[meca_id])

                    dof_per_point = int(meta["dof_per_point"])
                    n_points = int(meta["num_points"])

                    times = []
                    values = []

                    for row in rows:
                        t = float(row[0])
                        flat = np.asarray(row[1:], dtype=float)

                        expected_size = n_points * dof_per_point
                        if flat.size != expected_size:
                            print(
                                f"Reference size mismatch for file {self.file_scene_path}, "
                                f"MechanicalObject {meca_id}: "
                                f"expected {expected_size}, got {flat.size}"
                            )
                            return False

                        values.append(flat.reshape((n_points, dof_per_point)))
                        times.append(t)
                    
                    ref_values.append(values)

                    # Keep timeline from first MechanicalObject
                    if meca_id == 0:
                        keyframes = times
                    else:
                        if len(times) != len(keyframes):
                            print(
                                f"Reference timeline mismatch for file {self.file_scene_path}, "
                                f"MechanicalObject {meca_id}"
                            )
                            return False

                elif format == "JSON":
                    decoded_array, decoded_keyframes = reference_io.read_JSON_reference_file(self.filenames[meca_id])
                    numpy_data.append(decoded_array)

                    # Keep timeline from first MechanicalObject
                    if meca_id == 0:
                        keyframes = decoded_keyframes

                self.total_error.append(0.0)
                self.error_by_dof.append(0.0)

            except FileNotFoundError as e:
                print(f"{TermColor.RED}[Error]{TermColor.RESET} While reading references: {str(e)}")
                return False
            except KeyError as e:
                print(f"Missing metadata in reference file: {str(e)}")
                return False

        # --------------------------------------------------
        # Simulation + comparison
        # --------------------------------------------------
        frame_step = 0
        nbr_frames = len(keyframes)
        dt = self.root_node.dt.value
        for step in range(0, self.steps + 1):
            simu_time = dt * step

            # Use tolerance for float comparison
            if frame_step < nbr_frames and np.isclose(simu_time, keyframes[frame_step]):
                for meca_id in range(nbr_meca):
                    meca_dofs = np.copy(self.meca_objs[meca_id].position.value)

                    if format == "CSV":
                        data_ref = ref_values[meca_id][frame_step]
                    elif format == "JSON":
                        data_ref = np.asarray(numpy_data[meca_id][str(keyframes[frame_step])])

                    if meca_dofs.shape != data_ref.shape:
                        print(
                            f"{TermColor.RED}[Error]{TermColor.RESET} "
                            f"Shape mismatch for file {self.file_scene_path}, "
                            f"MechanicalObject {meca_id}: "
                            f"reference {data_ref.shape} vs current {meca_dofs.shape}"
                        )
                        return False

                    data_diff = data_ref - meca_dofs

                    # Compute total distance between the 2 sets
                    full_dist = np.linalg.norm(data_diff)
                    error_by_dof = full_dist / float(data_diff.size)

                    if self.verbose:
                        print(
                            f"{step} | {self.meca_objs[meca_id].name.value} | "
                            f"full_dist: {full_dist} | "
                            f"error_by_dof: {error_by_dof} | "
                            f"nbrDofs: {data_ref.size}"
                        )

                    self.total_error[meca_id] += full_dist
                    self.error_by_dof[meca_id] += error_by_dof

                frame_step += 1
                self.nbr_tested_frame += 1

                # security exit if simulation steps exceed nbr_frames
                if frame_step == nbr_frames:
                    break

            Sofa.Simulation.animate(self.root_node, dt)

            pbar_simu.update(1)
        pbar_simu.close()

        # Final regression returns value
        for meca_id in range(nbr_meca):
            if self.total_error[meca_id] > self.epsilon:
                self.regression_failed = True
                return False

        return True
    


    def compare_legacy_references(self):
        pbar_simu = tqdm(total=float(self.steps), disable=self.disable_progress_bar)
        pbar_simu.set_description("compare_legacy_references: " + self.file_scene_path)

        nbr_meca = len(self.meca_objs)

        # Reference data
        ref_times = []          # shared timeline
        ref_values = []         # List[List[np.ndarray]]

        self.total_error = []
        self.error_by_dof = []
        self.nbr_tested_frame = 0
        self.regression_failed = False

        # --------------------------------------------------
        # Load legacy reference files
        # --------------------------------------------------
        for meca_id in range(nbr_meca):
            try:
                times, values = read_legacy_reference(self.file_ref_path + ".reference_" + str(meca_id) + "_" + self.meca_objs[meca_id].name.value + "_mstate" + ".txt.gz",
                                                     self.meca_objs[meca_id])
            except Exception as e:
                print(
                    f"Error while reading legacy references for MechanicalObject "
                    f"{self.meca_objs[meca_id].name.value}: {str(e)}"
                )
                return False

            # Keep timeline from first MechanicalObject
            if meca_id == 0:
                ref_times = times
            else:
                if len(times) != len(ref_times):
                    print(
                        f"Reference timeline mismatch for file {self.file_scene_path}, "
                        f"MechanicalObject {meca_id}"
                    )
                    return False

            ref_values.append(values)
            self.total_error.append(0.0)
            self.error_by_dof.append(0.0)

        if self.verbose:
            print(f"ref_times len: {len(ref_times)}\n")
            print(f"ref_values[0] len: {len(ref_values[0])}\n")    
            print(f"ref_values[0][0] shape: {ref_values[0][0].shape}\n")

        # --------------------------------------------------
        # Simulation + comparison
        # --------------------------------------------------

        frame_step = 0
        nbr_frames = len(ref_times)
        dt = self.root_node.dt.value

        for step in range(0, self.steps + 1):
            simu_time = dt * step

            # Use tolerance for float comparison
            if frame_step < nbr_frames and np.isclose(simu_time, ref_times[frame_step]):
                for meca_id in range(nbr_meca):
                    meca_dofs = np.copy(self.meca_objs[meca_id].position.value)
                    data_ref = ref_values[meca_id][frame_step]

                    if meca_dofs.shape != data_ref.shape:
                        print(
                            f"Shape mismatch for file {self.file_scene_path}, "
                            f"MechanicalObject {meca_id}: "
                            f"reference {data_ref.shape} vs current {meca_dofs.shape}"
                        )
                        return False

                    data_diff = data_ref - meca_dofs

                    # Compute total distance between the 2 sets
                    full_dist = np.linalg.norm(data_diff)
                    error_by_dof = full_dist / float(data_diff.size)

                    if self.verbose:
                        print(
                            f"{step} | {self.meca_objs[meca_id].name.value} | "
                            f"full_dist: {full_dist} | "
                            f"error_by_dof: {error_by_dof} | "
                            f"nbrDofs: {data_ref.size}"
                        )

                    self.total_error[meca_id] += full_dist
                    self.error_by_dof[meca_id] += error_by_dof

                frame_step += 1
                self.nbr_tested_frame += 1

                # security exit if simulation steps exceed nbr_frames
                if frame_step == nbr_frames:
                    break

            Sofa.Simulation.animate(self.root_node, dt)
            
            pbar_simu.update(1)
        pbar_simu.close()

        # Final regression returns value
        if nbr_meca == 0:
            self.regression_failed = True
            return False

        # use the same way of computing errors as legacy mode
        mean_total_error = 0.0
        mean_error_by_dof = 0.0
        for meca_id in range(nbr_meca):
            mean_total_error += self.total_error[meca_id]
            mean_error_by_dof += self.error_by_dof[meca_id]

        mean_total_error = mean_total_error / float(nbr_meca)
        mean_error_by_dof = mean_error_by_dof / float(nbr_meca)
        print ("Mean Total Error: " + str(mean_total_error) + " | Mean Error by Dof: " + str(mean_error_by_dof) + "epsilon: " + str(self.epsilon))
        if mean_error_by_dof > self.epsilon:
            self.regression_failed = True
            return False

        return True


    def replay_references(self):
        
        # Import the GUI package
        import SofaImGui
        import Sofa.Gui
        Sofa.Gui.GUIManager.Init("myscene", "imgui")
        Sofa.Gui.GUIManager.createGUI(self.root_node, __file__)
        Sofa.Gui.GUIManager.SetDimension(1920, 1080)
        Sofa.Gui.GUIManager.MainLoop(self.root_node)
        Sofa.Gui.GUIManager.closeGUI()



