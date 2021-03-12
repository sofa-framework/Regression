cmake_minimum_required(VERSION 3.1)
project(Regression_test)

include(cmake/environment.cmake)

find_package(SofaBase REQUIRED)
find_package(SofaCommon REQUIRED)
find_package(SofaGeneral REQUIRED)
find_package(SofaAdvanced REQUIRED)
find_package(SofaMisc REQUIRED)
find_package(SofaValidation REQUIRED)
find_package(SofaExporter REQUIRED)
find_package(Sofa.Testing REQUIRED)

set(HEADER_FILES
    RegressionSceneList.h
    Regression_test.h
)

set(SOURCE_FILES
    RegressionSceneList.cpp
    Regression_test.cpp
)

add_executable(${PROJECT_NAME} ${SOURCE_FILES} ${HEADER_FILES})
add_definitions("-DSOFA_SRC_DIR=\"${CMAKE_SOURCE_DIR}\"")
target_link_libraries(${PROJECT_NAME} SofaCore SofaBase SofaCommon SofaGeneral SofaAdvanced SofaMisc)
target_link_libraries(${PROJECT_NAME} SofaExporter SofaValidation Sofa.Testing)
