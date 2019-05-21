cmake_minimum_required(VERSION 3.1)

# Meta CMakeLists used to build Regression_test within SOFA

find_package(SofaFramework) # Load SofaMacros

sofa_add_application(Regression_test Regression_test)
