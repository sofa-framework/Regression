import os
import sys

#example of use:
#python regression_test.py /home/epernod/projects/regression_test_sofa/build/bin/Regression_test ~/projects/sofa-src ~/projects/regression_test_sofa/src/references ~/projects/sofa-build/

#arguments:
# 0 - script name
# 1 - regression_test binary path
# 2 - regression scenes dir
# 3 - regression references dir
# 4 - sofa build dir

os.environ["REGRESSION_SCENES_DIR"] = sys.argv[2]
os.environ["REGRESSION_REFERENCES_DIR"] = sys.argv[3]

os.environ["SOFA_ROOT"] = sys.argv[4]
os.environ["SOFA_PLUGIN_PATH"] = sys.argv[4] + '/lib'

os.system(sys.argv[1])
