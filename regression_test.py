import os
import sys
from pathlib import Path

#example of use:
# on linux
#python regression_test.py /home/epernod/projects/regression_test_sofa/build/bin/Regression_test ~/projects/sofa-src ~/projects/regression_test_sofa/src/references ~/projects/sofa-build/
# on windows
#python ./sofa-src/applications/projects/Regression/regression_test.py /c/projects/sofa-build/bin/Release/Regression_test.exe /c/projects/sofa-src/ /c/projects/sofa-src/applications/projects/Regression/references/ /c/projects/sofa-build/

#arguments:
# 0 - script name
# 1 - regression_test binary path
# 2 - regression scenes dir
# 3 - sofa build dir
# 4 (optional) - Refrence plugin directory. If not set, will take the parent dir of this file.


os.environ["REGRESSION_SCENES_DIR"] = sys.argv[2]

os.environ["SOFA_ROOT"] = sys.argv[3]
os.environ["SOFA_PLUGIN_PATH"] = sys.argv[3] + '/lib'


if len(sys.argv) == 5:
    os.environ["REGRESSION_DIR"] = sys.argv[4]
else:
    script_dir = Path( __file__ ).parent.absolute()
    os.environ["REGRESSION_DIR"] = script_dir



os.system(sys.argv[1])
