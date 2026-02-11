import gzip
import csv
import json
from json import JSONEncoder


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


def write_CSV_reference_file(file_path, dof_per_point, num_points, csv_rows):
    with gzip.open(file_path, "wt", newline="") as f:
        writer = csv.writer(f)
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


def write_JSON_reference_file(file_path, numpy_data):
    with gzip.open(file_path, 'wb') as write_file:
        write_file.write(json.dumps(numpy_data, cls=NumpyArrayEncoder).encode('utf-8'))

def read_JSON_reference_file(file_path):
    with gzip.open(self.filenames[meca_id], 'r') as zipfile:
        decoded_array = json.loads(zipfile.read().decode('utf-8'))

        keyframes = []
        for key in decoded_array:
            keyframes.append(float(key))
    
        return decoded_array, keyframes