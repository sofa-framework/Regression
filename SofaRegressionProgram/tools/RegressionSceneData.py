import dataclasses
import time
import numpy as np
import pathlib
import sys

import tools.ReferenceFileIO as reference_io
import tools.RegressionHelper as helper
import Sofa

from tools import ProgressBarHandler as pbh


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

        self.ref_data, self.keyframes = reference_io.read_JSON_reference_file(state_filename)

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


def is_mapped(node):
    mapping = node.getMechanicalMapping()

    return mapping != None
    # no mapping in this node context



class RegressionSceneData:
    def __init__(self, file_scene_path: str = None, file_ref_path: str = None, steps = 1000,
                 epsilon = 0.0001, meca_in_mapping = True, dump_number_step = 1, disable_progress_bar = False, verbose = 1):
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
        self.filenames = []
        self.mins = []
        self.maxs = []
        self.total_error = []
        self.nbr_tested_frame = 0
        self.regression_failed = False
        self.root_node = None
        self.disable_progress_bar = disable_progress_bar
        self.verbose = verbose
        self.total_run_time = 0

    def print_info(self):
        helper.writeLog("Test scene: " + self.file_scene_path + " vs " + self.file_ref_path + " using: " + str(self.steps)
              + " " + str(self.epsilon), self.verbose)

    def log_errors(self, log_prefix='', err_log_stream=None):
        pass

    def apply_worker_result(self, result):
        pass

    def parse_node(self, node, level = 0):
        pass

    def load_scene(self, format = "JSON"):
        pass

    def write_references(self, format = "JSON"):
        pass

    def compare_references(self, format = "JSON"):
        pass

    def compare_legacy_references(self):
        pass


class StateRegressionSceneData(RegressionSceneData):
    def __init__(self, file_scene_path: str = None, file_ref_path: str = None, steps = 1000,
                 epsilon = 0.0001, meca_in_mapping = True, dump_number_step = 1, disable_progress_bar = False, verbose = 1):

        RegressionSceneData.__init__(self, file_scene_path, file_ref_path, steps, epsilon, meca_in_mapping, dump_number_step, disable_progress_bar, verbose)

        self.meca_objs = []
        self.error_by_dof = []

    def log_errors(self, log_prefix='', err_log_stream=None):
        if self.regression_failed:
            helper.writeError(
                                f"{self.file_scene_path} | Number of key frames compared: {self.nbr_tested_frame}  | run time: {self.total_run_time/1e9} seconds. "
                                f"\n    ### Error by dof: {self.error_by_dof} > Threshold: {self.epsilon}"
                                f"\n    ### Total Error: {self.total_error}",
                                self.verbose,
                                log_prefix,
                                err_log_stream = err_log_stream
                            )
        elif self.nbr_tested_frame == 0:
            helper.writeError(f"No frames were tested for {self.file_scene_path}",
                              self.verbose,
                              log_prefix,
                              err_log_stream = err_log_stream)
        else:
            helper.writeSuccess(f"{self.file_scene_path} | Number of key frames compared: {self.nbr_tested_frame} | run time: {self.total_run_time/1e9} seconds. ",
                                self.verbose,
                                log_prefix)

    def apply_worker_result(self, result):
        """Copy the fields reported by an isolated worker process back onto this
        object so that log_errors() and error counting behave as if the scene had
        been compared in-process."""
        self.regression_failed = bool(result.get("regression_failed", False))
        self.nbr_tested_frame = int(result.get("nbr_tested_frame", 0))
        self.total_run_time = result.get("total_run_time", 0)
        self.error_by_dof = result.get("error_by_dof", [])
        self.total_error = result.get("total_error", [])


    def print_meca_objs(self):
        helper.writeLog("# Nbr Meca: " + str(len(self.meca_objs)), self.verbose)
        counter = 0
        for mecaObj in self.meca_objs:
            filename = self.file_ref_path + ".reference_" + str(counter) + "_" + mecaObj.name.value + "_mstate" + ".txt.gz"
            counter = counter+1
            helper.writeLog("# File attached: " + filename, self.verbose)


    def parse_node(self, node, level = 0):
        # first check current node
        mstate = node.getMechanicalState()
        if mstate and is_simulated(node):
            if self.meca_in_mapping is True or is_mapped(node) is False:
                self.meca_objs.append(mstate)
                helper.writeLog("  " * level + f"- Adding MechanicalObject: {mstate.name.value} from Node: {node.name.value}", self.verbose)

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
        helper.writeLog(f"Loading scene: {self.file_scene_path}", self.verbose)
        self.root_node = Sofa.Simulation.load(self.file_scene_path)
        if not self.root_node: # error while loading
            raise RuntimeError("While trying to load {self.file_scene_path}")
        else:
            helper.writeLog("Initializing root node", self.verbose)
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
        pbar_simu = pbh.ProgressBarHandler(total=self.steps, disable=self.disable_progress_bar)
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
            raise ValueError(f"Unsupported format: {format}")

        for step in range(0, self.steps + 1):
            if step == 0 or counter_step >= modulo_step or step == self.steps:
                t = dt * step
                for meca_id in range(nbr_meca):
                    positions = np.asarray(self.meca_objs[meca_id].position.value)

                    if not np.isfinite(positions).all():
                        raise ValueError(
                            f"Non-finite position detected for MechanicalObject "
                            f"{self.meca_objs[meca_id].name.value} while writing references for "
                            f"{self.file_scene_path} at t={t}. Refusing to write a reference "
                            f"containing non-finite values."
                        )

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
        pbar_simu = pbh.ProgressBarHandler(total=float(self.steps), disable=self.disable_progress_bar)
        pbar_simu.set_description("compare_references: " + self.file_scene_path)

        nbr_meca = len(self.meca_objs)

        # Reference data
        keyframes = []  # shared timeline
        if format == "CSV":
            ref_values = []         # List[List[np.ndarray]]
        elif format == "JSON":
            numpy_data = [] # List<map>
        else:
            helper.writeError(f"Unsupported format: {format}", self.verbose)
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
                            raise ValueError(
                                f"Reference size mismatch for file {self.file_scene_path}, "
                                f"MechanicalObject {meca_id}: "
                                f"expected {expected_size}, got {flat.size}",
                                self.verbose
                            )

                        values.append(flat.reshape((n_points, dof_per_point)))
                        times.append(t)

                    ref_values.append(values)

                    # Keep timeline from first MechanicalObject
                    if meca_id == 0:
                        keyframes = times
                    else:
                        if len(times) != len(keyframes):
                            raise ValueError(
                                f"Reference timeline mismatch for file {self.file_scene_path}, "
                                f"MechanicalObject {meca_id}",
                                self.verbose
                            )

                elif format == "JSON":
                    decoded_array, decoded_keyframes = reference_io.read_JSON_reference_file(self.filenames[meca_id])
                    numpy_data.append(decoded_array)

                    # Keep timeline from first MechanicalObject
                    if meca_id == 0:
                        keyframes = decoded_keyframes

                self.total_error.append(0.0)
                self.error_by_dof.append(0.0)


            except KeyError as e:
                e.add_note(f"Missing metadata key {e} in reference file: {self.file_ref_path}")
                raise

        # --------------------------------------------------
        # Simulation + comparison
        # --------------------------------------------------
        frame_step = 0
        nbr_frames = len(keyframes)
        dt = self.root_node.dt.value
        for step in range(0, self.steps + 1):
            simu_time = dt * step

            # Use tolerance for float comparison
            if frame_step < nbr_frames and abs(simu_time - keyframes[frame_step]) < dt / 2.0:
                for meca_id in range(nbr_meca):
                    meca_dofs = np.copy(self.meca_objs[meca_id].position.value)

                    if format == "CSV":
                        data_ref = ref_values[meca_id][frame_step]
                    elif format == "JSON":
                        data_ref = np.asarray(numpy_data[meca_id][str(keyframes[frame_step])])

                    if meca_dofs.size == 0 and data_ref.size == 0:
                        continue

                    if meca_dofs.shape != data_ref.shape:
                        raise ValueError(
                            f"Shape mismatch for file {self.file_scene_path}, "
                            f"MechanicalObject {meca_id}: "
                            f"reference {data_ref.shape} vs current {meca_dofs.shape}",
                            self.verbose
                        )

                    data_diff = data_ref - meca_dofs

                    # Compute total distance between the 2 sets
                    full_dist = np.linalg.norm(data_diff)
                    error_by_dof = full_dist / np.sqrt(float(data_diff.size))

                    helper.writeLog(
                        f"{step} | {self.meca_objs[meca_id].name.value} | "
                        f"full_dist: {full_dist} | "
                        f"error_by_dof: {error_by_dof} | "
                        f"nbrDofs: {data_ref.size}",
                        self.verbose
                    )

                    self.total_error[meca_id] += full_dist
                    self.error_by_dof[meca_id] += error_by_dof

                frame_step += 1
                self.nbr_tested_frame += 1

                # security exit if simulation steps exceed nbr_frames
                if frame_step == nbr_frames:
                    break

            start_time = time.time_ns()
            Sofa.Simulation.animate(self.root_node, dt)
            self.total_run_time += time.time_ns() - start_time

            pbar_simu.update(1)
        pbar_simu.close()

        # Final regression returns value
        for meca_id in range(nbr_meca):
            if not np.isfinite(self.error_by_dof[meca_id]):
                self.regression_failed = True
                return False
            if self.error_by_dof[meca_id] > self.epsilon:
                self.regression_failed = True
                return False

        return True



    def compare_legacy_references(self):
        pbar_simu = pbh.ProgressBarHandler(total=float(self.steps), disable=self.disable_progress_bar)
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
                times, values = reference_io.read_legacy_reference(self.file_ref_path + ".reference_" + str(meca_id) + "_" + self.meca_objs[meca_id].name.value + "_mstate" + ".txt.gz", self.meca_objs[meca_id])
            except Exception as e:
                e.add_note(
                        f"While reading legacy references for MechanicalObject "
                        f"'{self.meca_objs[meca_id].name.value}'"
                    )

            # Keep timeline from first MechanicalObject
            if meca_id == 0:
                ref_times = times
            else:
                if len(times) != len(ref_times):
                    raise ValueError(
                        f"Reference timeline mismatch for file {self.file_scene_path}, "
                        f"MechanicalObject {meca_id}",
                        self.verbose
                    )

            ref_values.append(values)
            self.total_error.append(0.0)
            self.error_by_dof.append(0.0)

        helper.writeLog(f"compare_legacy_references: ref_values[0][0] shape: {ref_values[0][0].shape}", self.verbose)

        # --------------------------------------------------
        # Simulation + comparison
        # --------------------------------------------------

        frame_step = 0
        nbr_frames = len(ref_times)
        dt = self.root_node.dt.value

        if nbr_frames != self.steps:
            helper.writeWarning(f"Number of steps saved in reference file ({nbr_frames}) does not match the number of required steps ({self.steps})", self.verbose)

        helper.writeLog(f"Running {self.steps} simulation steps...", self.verbose)

        for step in range(0, self.steps + 1):
            simu_time = dt * step

            # Use tolerance for float comparison
            if frame_step < nbr_frames and abs(simu_time - ref_times[frame_step]) < dt / 2.0:
                for meca_id in range(nbr_meca):
                    meca_dofs = np.copy(self.meca_objs[meca_id].position.value)
                    data_ref = ref_values[meca_id][frame_step]

                    if meca_dofs.shape != data_ref.shape:
                        raise ValueError(
                            f"Shape mismatch for file {self.file_scene_path}, "
                            f"MechanicalObject {meca_id}: "
                            f"reference {data_ref.shape} vs current {meca_dofs.shape}",
                            self.verbose
                        )

                    data_diff = data_ref - meca_dofs

                    # Compute total distance between the 2 sets
                    full_dist = np.linalg.norm(data_diff)
                    error_by_dof = full_dist / float(data_diff.size)

                    helper.writeLog(
                        f"    {step} | {self.meca_objs[meca_id].name.value} | "
                        f"full_dist: {full_dist} | "
                        f"error_by_dof: {error_by_dof} | "
                        f"nbrDofs: {data_ref.size}",
                        self.verbose
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

        if not np.isfinite(mean_error_by_dof):
            self.regression_failed = True
            return False

        if mean_error_by_dof > self.epsilon:
            self.regression_failed = True
            return False

        return True

    @staticmethod
    def is_replay_available():
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

class TopologyRegressionSceneData(RegressionSceneData):

    # Categories checked by the legacy CompareTopology visitor, in the order
    # they were written to the reference files.
    topology_categories = (("edge", "edges"), ("edge", "triangles"), ("quad", "quads"),
                           ("tetrahedron", "tetrahedra"), ("hexahedron", "hexahedra"),
                           ("prism", "prisms"), ("pyramid", "pyramids"))
    #When the support is complete
    # "quadratic_edges", "quadratic_triangles", "quadratic_quads", "quadratic_tetrahedra", "quadratic_hexahedra", "quadratic_prisms", "quadratic_pyramids"


    def __init__(self, file_scene_path: str = None, file_ref_path: str = None, steps = 1000,
                 epsilon = 0.0001, meca_in_mapping = True, dump_number_step = 1, disable_progress_bar = False, verbose = 1):

        RegressionSceneData.__init__(self, file_scene_path, file_ref_path, steps, epsilon, meca_in_mapping, dump_number_step, disable_progress_bar, verbose)

        self.error_topology = {elemType[1] : [] for elemType in TopologyRegressionSceneData.topology_categories}
        self.topology = []

    @staticmethod
    def is_replay_available():
        return False

    def log_errors(self, log_prefix='', err_log_stream=None):
        if self.regression_failed:
            body = ""
            for topo_type in TopologyRegressionSceneData.topology_categories:
                if len(self.error_topology[topo_type[1]]) > 0 :
                    body += f"\n        {topo_type[1].replace('_',' ').capitalize()}: {self.error_topology[topo_type[1]]}"
            helper.writeError(
                                f"{self.file_scene_path} | Number of key frames compared: {self.nbr_tested_frame} | run time: {self.total_run_time/1e9} seconds. "
                                f"\n    ### Errors by topology container:"
                                f"{body}"
                                f"\n    ### Total Error: {self.total_error} > Threshold: {self.epsilon}",
                                self.verbose,
                                log_prefix,
                                err_log_stream = err_log_stream
                            )
        elif self.nbr_tested_frame == 0:
            helper.writeError(f"No frames were tested for {self.file_scene_path}",
                              self.verbose,
                              log_prefix,
                              err_log_stream = err_log_stream)
        else:
            helper.writeSuccess(f"{self.file_scene_path} | Number of key frames compared: {self.nbr_tested_frame} | run time: {self.total_run_time/1e9} seconds. ",
                                self.verbose,
                                log_prefix)

    def apply_worker_result(self, result):
        """Copy the fields reported by an isolated worker process back onto this
        object so that log_errors() and error counting behave as if the scene had
        been compared in-process."""
        self.regression_failed = bool(result.get("regression_failed", False))
        self.nbr_tested_frame = int(result.get("nbr_tested_frame", 0))
        self.total_run_time = result.get("total_run_time", 0)
        self.error_topology = result.get("error_topology", {})



    def parse_node(self, node, level = 0):
        # Mirrors CompareTopologyCreator::processNodeTopDown: only a topology
        # container attached directly to this node is considered (not one
        # inherited from a parent), so the same physical container is never
        # tested twice through two different nodes.
        topo = node.getMeshTopology(Sofa.Core.BaseContext.SearchDirection.Local)
        if topo is not None and (self.meca_in_mapping is True or is_mapped(node) is False):
                self.topology.append(topo)
                helper.writeLog("  " * level + f"- Adding Topology: {topo.name.value} from Node: {node.name.value}", self.verbose)

        # recursively check children
        for child in node.children:
            self.parse_node(child, level + 1)


    @staticmethod
    def _get_topology_state(topo):
        """Snapshot of a BaseMeshTopology's element containers, read directly
        through the python bindings (no WriteTopology/ReadTopology component
        added to the scene)."""
        return {topo_type[1] : [tuple(topo.__getattribute__(f"get{topo_type[0].capitalize()}")(i)) for i in range(topo.__getattribute__(f"getNb{topo_type[1].capitalize()}")())] for topo_type in TopologyRegressionSceneData.topology_categories}

    @staticmethod
    def _compare_topology_states(ref_state, current_state):
        """Reproduce CompareTopology::processCompareTopology: for each
        category, a count mismatch adds the absolute difference in count as
        the error; otherwise every element is compared and each mismatching
        one adds 1. A reference count of 0 means the category was never
        recorded for this frame (the legacy writer always writes the count,
        even when null, but the legacy reader/comparator only acts on it when
        non-zero), so it is skipped rather than compared against 0.
        """
        errors = {}
        for category in TopologyRegressionSceneData.topology_categories:
            ref_elements = ref_state.get(category[1], [])
            ref_count = len(ref_elements)

            if ref_count == 0:
                errors[category[1]] = 0
                continue

            cur_elements = current_state[category[1]]
            cur_count = len(cur_elements)

            if ref_count != cur_count:
                errors[category[1]] = abs(ref_count - cur_count)
            else:
                errors[category[1]] = sum(
                    1 for ref_elem, cur_elem in zip(ref_elements, cur_elements)
                    if list(ref_elem) != list(cur_elem)
                )
        return errors


    def load_scene(self, format = "JSON"):
        helper.writeLog(f"Loading scene: {self.file_scene_path}", self.verbose)
        self.root_node = Sofa.Simulation.load(self.file_scene_path)
        if not self.root_node: # error while loading
            raise RuntimeError(f"While trying to load {self.file_scene_path}")
        else:
            helper.writeLog("Initializing root node", self.verbose)
            Sofa.Simulation.initRoot(self.root_node)

            # prepare ref files per topology container:
            self.parse_node(self.root_node, 0)
            counter = 0
            for topo in self.topology:
                if format != "JSON":
                    raise ValueError(f"Unsupported format for TOPOLOGY regression: {format}")
                _filename = self.file_ref_path + ".reference_topology_" + str(counter) + "_" + topo.name.value + ".json.gz"
                self.filenames.append(_filename)
                counter = counter + 1


    def write_references(self, format = "JSON"):
        if format != "JSON":
            raise ValueError(f"Unsupported format for TOPOLOGY regression: {format}")

        pbar_simu = pbh.ProgressBarHandler(total=self.steps, disable=self.disable_progress_bar)
        pbar_simu.set_description("Simulate: " + self.file_scene_path)

        dt = self.root_node.dt.value
        nbr_topo = len(self.topology)
        numpy_data = [dict() for _ in range(nbr_topo)] # List<map>

        # Store the topology structure at each time step to catch potential topological changes during the simulation
        for step in range(self.steps):
            Sofa.Simulation.animate(self.root_node, dt)
            pbar_simu.update(1)

            t = dt * step
            for topo_id in range(nbr_topo):
                numpy_data[topo_id][t] = TopologyRegressionSceneData._get_topology_state(self.topology[topo_id])

        pbar_simu.close()

        # write reference files
        for topo_id in range(nbr_topo):
            output_file = pathlib.Path(self.filenames[topo_id])
            output_file.parent.mkdir(exist_ok=True, parents=True)
            reference_io.write_JSON_reference_file(self.filenames[topo_id], numpy_data[topo_id])

        Sofa.Simulation.unload(self.root_node)


    def compare_references(self, format = "JSON"):
        if format != "JSON":
            helper.writeError(f"Unsupported format: {format}", self.verbose)
            raise ValueError(f"Unsupported format: {format}")

        pbar_simu = pbh.ProgressBarHandler(total=float(self.steps), disable=self.disable_progress_bar)
        pbar_simu.set_description("compare_references: " + self.file_scene_path)

        nbr_topo = len(self.topology)

        # Reference data
        keyframes = [] # shared timeline
        numpy_data = [] # List<map>

        # Outputs init
        self.total_error = [0.0] * nbr_topo
        for topo_type in self.error_topology:
            self.error_topology[topo_type] = [0.0] * nbr_topo
        self.nbr_tested_frame = 0
        self.regression_failed = False

        # --------------------------------------------------
        # Load reference files
        # --------------------------------------------------
        for topo_id in range(nbr_topo):
            try:
                decoded_array, decoded_keyframes = reference_io.read_JSON_reference_file(self.filenames[topo_id])
            except KeyError as e:
                e.add_note(f"Missing metadata key {e} in reference file: {self.file_ref_path}")
                raise
            numpy_data.append(decoded_array)

            # Keep timeline from first topology container
            if topo_id == 0:
                keyframes = decoded_keyframes

        # --------------------------------------------------
        # Simulation + comparison
        # --------------------------------------------------
        nbr_frames = len(keyframes)
        dt = self.root_node.dt.value

        if nbr_frames != self.steps:
            helper.writeWarning(f"Number of frames saved in reference file ({nbr_frames}) does not match the number of required steps ({self.steps})", self.verbose)

        for step in range(self.steps):
            start_time = time.time_ns()
            Sofa.Simulation.animate(self.root_node, dt)
            self.total_run_time += time.time_ns() - start_time

            pbar_simu.update(1)

            # Sample right after animate(): see the comment in write_references()
            # for why this mirrors the legacy AnimateBeginEvent-based sampling.
            if step < nbr_frames:
                for topo_id in range(nbr_topo):
                    ref_state = numpy_data[topo_id][str(keyframes[step])]
                    current_state = TopologyRegressionSceneData._get_topology_state(self.topology[topo_id])

                    errors = TopologyRegressionSceneData._compare_topology_states(ref_state, current_state)

                    helper.writeLog(
                        f"{step} | {self.topology[topo_id].name.value} | errors: {errors}",
                        self.verbose
                    )

                    for topo_type in self.error_topology:
                        self.error_topology[topo_type][topo_id] += errors[topo_type]

                    self.total_error[topo_id] += sum(errors.values())

                self.nbr_tested_frame += 1
        pbar_simu.close()

        # Final regression returns value
        for topo_id in range(nbr_topo):
            if not np.isfinite(self.total_error[topo_id]):
                self.regression_failed = True
                return False
            if self.total_error[topo_id] > self.epsilon:
                self.regression_failed = True
                return False

        return True


    def compare_legacy_references(self):
        pbar_simu = pbh.ProgressBarHandler(total=float(self.steps), disable=self.disable_progress_bar)
        pbar_simu.set_description("compare_legacy_references: " + self.file_scene_path)

        nbr_topo = len(self.topology)

        # Reference data
        ref_times = []  # shared timeline
        ref_values = [] # List[List[dict category -> list[tuple]]]

        self.total_error = [0.0] * nbr_topo
        for topo_type in self.error_topology:
            self.error_topology[topo_type] = [0.0] * nbr_topo
        self.nbr_tested_frame = 0
        self.regression_failed = False

        if nbr_topo == 0:
            self.regression_failed = True
            return False

        # --------------------------------------------------
        # Load legacy reference files
        # --------------------------------------------------
        for topo_id in range(nbr_topo):
            legacy_filename = (self.file_ref_path + ".reference_" + str(topo_id) + "_"
                                + self.topology[topo_id].name.value + "_topology.txt.gz")
            try:
                times, values = reference_io.read_legacy_topology_reference(legacy_filename)
            except Exception as e:
                e.add_note(
                        f"While reading legacy topology references for container "
                        f"'{self.topology[topo_id].name.value}'"
                    )
                raise

            # Keep timeline from first topology container
            if topo_id == 0:
                ref_times = times
            else:
                if len(times) != len(ref_times):
                    raise ValueError(
                        f"Reference timeline mismatch for file {self.file_scene_path}, "
                        f"Topology {topo_id}",
                        self.verbose
                    )

            ref_values.append(values)

        # --------------------------------------------------
        # Simulation + comparison
        # --------------------------------------------------
        frame_step = 0
        nbr_frames = len(ref_times)
        dt = self.root_node.dt.value

        if nbr_frames != self.steps:
            helper.writeWarning(f"Number of steps saved in reference file ({nbr_frames}) does not match the number of required steps ({self.steps})", self.verbose)

        for step in range(self.steps):
            Sofa.Simulation.animate(self.root_node, dt)
            pbar_simu.update(1)

            # Sample right after animate(): see the comment in write_references()
            # for why this mirrors the legacy AnimateBeginEvent-based sampling.
            simu_time = dt * step

            # Use tolerance for float comparison
            if frame_step < nbr_frames and abs(simu_time - ref_times[frame_step]) < dt / 2.0:
                for topo_id in range(nbr_topo):
                    ref_state = ref_values[topo_id][frame_step]
                    current_state = TopologyRegressionSceneData._get_topology_state(self.topology[topo_id])

                    errors = TopologyRegressionSceneData._compare_topology_states(ref_state, current_state)

                    helper.writeLog(
                        f"    {step} | {self.topology[topo_id].name.value} | errors: {errors}",
                        self.verbose
                    )

                    for topo_type in self.error_topology:
                        self.error_topology[topo_type][topo_id] += errors[topo_type]

                    self.total_error[topo_id] += sum(errors.values())

                frame_step += 1
                self.nbr_tested_frame += 1

                # security exit if simulation steps exceed nbr_frames
                if frame_step == nbr_frames:
                    break
        pbar_simu.close()

        # Final regression returns value
        for topo_id in range(nbr_topo):
            if not np.isfinite(self.total_error[topo_id]):
                self.regression_failed = True
                return False
            if self.total_error[topo_id] > self.epsilon:
                self.regression_failed = True
                return False

        return True
