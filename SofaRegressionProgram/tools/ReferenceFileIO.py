import gzip
import csv
import json
from json import JSONEncoder
import numpy as np

regression_version = "1.0"

class NumpyArrayEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return JSONEncoder.default(self, obj)


# --------------------------------------------------
# Helper: read CSV + metadata
# --------------------------------------------------
def read_CSV_reference_file(file_path):
    meta = {}
    data_rows = []

    with gzip.open(file_path, "rt") as f:
        # Read metadata
        while True:
            pos = f.tell()
            line = f.readline()
            if not line:
                break

            if line.startswith("#"):
                if "=" in line:
                    k, v = line[1:].strip().split("=", 1)
                    meta[k.strip()] = v.strip()
            else:
                f.seek(pos)
                break

        reader = csv.reader(f)
        for row in reader:
            if row:
                data_rows.append(row)

    return meta, data_rows

# --------------------------------------------------
# Helper: write CSV + metadata
# --------------------------------------------------
def write_CSV_reference_file(file_path, dof_per_point, num_points, csv_rows):
    with gzip.open(file_path, "wt", newline="") as f:
        writer = csv.writer(f)
        f.write(f"# format_version={regression_version}\n")
        f.write(f"# dof_per_point={dof_per_point}\n")
        f.write(f"# num_points={num_points}\n")

        if dof_per_point == 2:
            f.write("# layout=time,X0,Y1,...,Xn,Yn\n")
        elif dof_per_point == 3:
            f.write("# layout=time,X0,Y1,Z1,...,Xn,Yn,Zn\n")
        elif dof_per_point == 7:
            f.write("# layout=time,X0,Y1,Z1,Qx1,Qy1,Qz1,Qw1,...,Xn,Yn,Zn,QxN,QyN,QzN1,QwN\n")
        else:
            f.write("# layout=unknown\n")

        writer.writerows(csv_rows)


# --------------------------------------------------
# Helper: write numpy array to JSON
# --------------------------------------------------
def write_JSON_reference_file(file_path, numpy_data):
    with gzip.open(file_path, 'wb') as write_file:
        write_file.write(json.dumps(numpy_data, cls=NumpyArrayEncoder).encode('utf-8'))

# --------------------------------------------------
# Helper: read JSON and convert to numpy array
# --------------------------------------------------
def read_JSON_reference_file(file_path):
    with gzip.open(file_path, 'r') as zipfile:
        decoded_array = json.loads(zipfile.read().decode('utf-8'))

        keyframes = []
        for key in decoded_array:
            keyframes.append(float(key))

        return decoded_array, keyframes

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

# --------------------------------------------------
# Helper: read the legacy topology reference format
# --------------------------------------------------
# Written by the former C++ WriteTopology component, one block per timestep:
#   T= <time>
#     Edges= <nbr>
#   <nbr edges, 2 ints each, space separated, on one line (blank if nbr==0)>
#     Triangles= <nbr>
#   <...>
#     Quads= <nbr>
#   <...>
#     Tetrahedra= <nbr>
#   <...>
#     Hexahedra= <nbr>
#   <...>
_legacy_topology_categories = (
    ("Edges=", "edges", 2),
    ("Triangles=", "triangles", 3),
    ("Quads=", "quads", 4),
    ("Tetrahedra=", "tetrahedra", 4),
    ("Hexahedra=", "hexahedra", 8),
)


def read_legacy_topology_reference(filename):
    times = []
    values = []
    current_entry = None

    with gzip.open(filename, "rt") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("T="):
                if current_entry is not None:
                    values.append(current_entry)
                times.append(float(stripped.split("=", 1)[1]))
                current_entry = {key: [] for _, key, _ in _legacy_topology_categories}
                continue

            for label, key, arity in _legacy_topology_categories:
                if not stripped.startswith(label):
                    continue

                nbr = int(stripped.split("=", 1)[1].strip())
                if nbr > 0:
                    raw = next(f).split()
                    if len(raw) != nbr * arity:
                        raise ValueError(
                            f"Legacy topology reference corrupted in {filename}: "
                            f"expected {nbr * arity} values for '{key}', got {len(raw)}"
                        )
                    current_entry[key] = [
                        tuple(int(v) for v in raw[i * arity:(i + 1) * arity])
                        for i in range(nbr)
                    ]
                break

    if current_entry is not None:
        values.append(current_entry)

    if len(times) != len(values):
        raise RuntimeError(
            f"Legacy topology reference corrupted in {filename}: "
            f"{len(times)} times vs {len(values)} entries"
        )

    return times, values
