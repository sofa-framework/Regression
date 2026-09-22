cmake_minimum_required(VERSION 3.22)
project(SofaRegressionProgram)

set(REGRESSION_PROGRAM_INSTALL_DIR plugins/SofaRegressionProgram)
install(FILES SofaRegressionProgram.py DESTINATION ${REGRESSION_PROGRAM_INSTALL_DIR})
install(DIRECTORY tools DESTINATION ${REGRESSION_PROGRAM_INSTALL_DIR})
