cmake_minimum_required(VERSION 3.1)
project(Regression_test)

include(cmake/environment.cmake)

find_package(SofaMisc) # to include all SOFA
find_package(SofaGTestMain)

set(HEADER_FILES
    RegressionScene_list.h
)

set(SOURCE_FILES
    RegressionScene_list.cpp
    RegressionScene_test.cpp
)

add_executable(${PROJECT_NAME} ${SOURCE_FILES} ${HEADER_FILES})
add_definitions("-DSOFA_SRC_DIR=\"${CMAKE_SOURCE_DIR}\"")
target_link_libraries(${PROJECT_NAME} SofaCore SofaGTestMain SofaComponentBase SofaComponentCommon SofaComponentGeneral SofaComponentAdvanced SofaComponentMisc)

