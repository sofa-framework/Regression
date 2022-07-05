cmake_minimum_required(VERSION 3.1)
project(Regression_test)

include(cmake/environment.cmake)

# regression_test itself just needs Sofa.Component.Playback
# But Sofa.Component ensures that we have all the Sofa.Component.* components needed in the tested scenes.
find_package(Sofa.Component REQUIRED)
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
target_link_libraries(${PROJECT_NAME} PUBLIC Sofa.Testing)
target_link_libraries(${PROJECT_NAME} PUBLIC Sofa.Component)
