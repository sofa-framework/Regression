import gzip
import zlib
import re
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
# Helpers mirroring the C++ legacy readers (gzgets + istream >> double)
# --------------------------------------------------
def _read_gz_lines_tolerant(filename):
    """Return the lines of a gzip file, keeping whatever can be decompressed
    when the stream is truncated (zlib's gzgets does the same: it just returns
    what it could read instead of failing)."""
    with open(filename, "rb") as f:
        raw = f.read()
    d = zlib.decompressobj(zlib.MAX_WBITS | 16)
    try:
        data = d.decompress(raw)
    except zlib.error:
        data = b""
    return data.decode("utf-8", errors="replace").split("\n")


_cpp_double_re = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def parse_cpp_doubles(tokens):
    """Convert tokens like `while (stream >> value)` would: stop at the first
    token that is not a plain number (nan, inf, -nan(ind), ...)."""
    values = []
    for tok in tokens:
        if not _cpp_double_re.match(tok):
            break
        values.append(float(tok))
    return np.asarray(values, dtype=float)


def round_like_cpp_ostream(values):
    """C++ writes the current state with the default ostream precision (6
    significant digits) before parsing it back for the comparison."""
    return np.asarray([float("%.6g" % v) if np.isfinite(v) else v for v in values], dtype=float)


# --------------------------------------------------
# Helper: read the legacy state reference format
# --------------------------------------------------
def read_legacy_reference(filename):
    """Read a legacy (C++ WriteState) state reference file.

    Returns a list of frames, each one a dict {"time": float, "X": flat ndarray
    or None, "V": flat ndarray or None}. No reshaping is done: the legacy
    comparison works on the flat list of scalars, exactly like
    MechanicalObject::compareVec.
    """
    frames = []

    for line in _read_gz_lines_tolerant(filename):
        line = line.strip()
        if not line:
            continue

        if line.startswith("T="):
            frames.append({"time": float(line.split("=", 1)[1]), "X": None, "V": None})
        elif line.startswith("X=") or line.startswith("V="):
            if not frames:
                raise RuntimeError(f"{line[:2]} found before T in {filename}")
            key = line[0]
            frames[-1][key] = parse_cpp_doubles(line.split("=", 1)[1].split())

    return frames

# --------------------------------------------------
# Helper: read the legacy topology reference format
# --------------------------------------------------
# Written by the former C++ WriteTopology component, one block per timestep:
#   T= <time>
#     Edges= <nbr>
#   <raw edges list, 2 ints each, space separated, on one line (blank if nbr==0)>
#     Triangles= <nbr>
#   <raw triangles list, 3 ints each, space separated, on one line (blank if nbr==0)>
#     Quads= <nbr>
#   <raw quads list, 4 ints each, space separated, on one line (blank if nbr==0)>
#     Tetrahedra= <nbr>
#   <raw tetrahedra list, 4 ints each, space separated, on one line (blank if nbr==0)>
#     Hexahedra= <nbr>
#   <raw hexahedra list, 8 ints each, space separated, on one line (blank if nbr==0)>
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

    lines = iter(_read_gz_lines_tolerant(filename))
    for line in lines:
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
                raw = next(lines, "").split()
                if len(raw) != nbr * arity:
                    # truncated file (last block cut): ignore this incomplete block
                    # like the C++ reader that would stop at the end of the stream
                    if current_entry is not None:
                        times.pop()
                        current_entry = None
                    break
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
