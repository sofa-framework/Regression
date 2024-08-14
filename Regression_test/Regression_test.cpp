#include "Regression_test.h"

#include <sofa/helper/system/FileRepository.h>
#include <sofa/helper/system/FileSystem.h>

#include <sofa/component/playback/ReadState.h>
#include <sofa/component/playback/WriteState.h>
#include <sofa/component/playback/ReadTopology.h>
#include <sofa/component/playback/WriteTopology.h>
#include <sofa/component/playback/CompareState.h>
#include <sofa/component/playback/CompareTopology.h>

#include <sofa/simulation/graph/DAGSimulation.h>
#include <sofa/simpleapi/SimpleApi.h>

#include <sofa/core/MechanicalParams.h>

namespace sofa 
{

std::string BaseRegression_test::getTestName(const ::testing::TestParamInfo<RegressionSceneData>& p)
{
    const std::string& path = p.param.m_fileScenePath;
    std::size_t pos = path.find_last_of("/"); // get name of the file without path

    if (pos != std::string::npos)
        pos++;

    std::string name = path.substr(pos);
    name = name.substr(0, name.find_last_of(".")); // get name of the file without extension

    return name;
}



void BaseRegression_test::runTest(RegressionSceneData data)
{
    msg_info("BaseRegression_test::runStateRegressionTest") << "Testing " << data.m_fileScenePath;

    sofa::simpleapi::importPlugin("Sofa.Component");

    simulation::Simulation* simulation = simulation::getSimulation();

    // Load the scene
    sofa::simulation::Node::SPtr root = sofa::simulation::node::load(data.m_fileScenePath.c_str());

    // if no root node -> loading failed
    if (root == NULL)
    {
        msg_error("BaseRegression_test::runStateRegressionTest")
            << data.m_fileScenePath << " could not be loaded." << msgendl;
        return;
    }

    sofa::simulation::node::initRoot(root.get());

    // check if ref file exist will run and compare to references
    if (helper::system::FileSystem::exists(data.m_fileRefPath) && !helper::system::FileSystem::isDirectory(data.m_fileRefPath))
        runTestImpl(data, root, false);
    else // create reference
        runTestImpl(data, root, true);

    // Clear and prepare for next scene
    sofa::simulation::node::unload(root.get());
    root.reset();
}


void StateRegression_test::runTestImpl(RegressionSceneData data, simulation::Node::SPtr root, bool createReference)
{
    if (!createReference)
    {
        // Add CompareState components: as it derives from the ReadState, we use the ReadStateActivator to enable them.
        sofa::component::playback::CompareStateCreator compareVisitor(sofa::core::ExecParams::defaultInstance());

        compareVisitor.setCreateInMapping(data.m_mecaInMapping);
        compareVisitor.setSceneName(data.m_fileRefPath);
        compareVisitor.execute(root.get());

        sofa::component::playback::ReadStateActivator v_read(sofa::core::ExecParams::defaultInstance() /* PARAMS FIRST */, true);
        v_read.execute(root.get());
    }
    else // create reference
    {
        msg_error("StateRegression_test::runTestImpl") << "Non existing reference created: " << data.m_fileRefPath
                                                       << "\nIgnore this error if you are willingly generating a new reference";

        // just to create an empty file to know it is already init
        std::ofstream filestream(data.m_fileRefPath.c_str());
        filestream.close();

        sofa::component::playback::WriteStateCreator writeVisitor(sofa::core::ExecParams::defaultInstance());

        if (data.m_dumpOnlyLastStep)
        {
            std::vector<double> times;
            times.push_back(0.0);
            times.push_back(root->getDt() * (data.m_steps - 1));
            writeVisitor.setExportTimes(times);
        }
        writeVisitor.setCreateInMapping(data.m_mecaInMapping);
        writeVisitor.setSceneName(data.m_fileRefPath);
        writeVisitor.execute(root.get());

        sofa::component::playback::WriteStateActivator v_write(sofa::core::ExecParams::defaultInstance() /* PARAMS FIRST */, true);
        v_write.execute(root.get());
    }

    for (unsigned int i = 0; i<data.m_steps; ++i)
    {
        sofa::simulation::node::animate(root.get(), root->getDt());
    }

    if (!createReference)
    {
        // Read the final error: the summation of all the error made at each time step
        sofa::component::playback::CompareStateResult result(sofa::core::ExecParams::defaultInstance());
        result.execute(root.get());

        double errorByDof = result.getErrorByDof() / double(result.getNumCompareState());
        if (errorByDof > data.m_epsilon)
        {
            msg_error("StateRegression_test::runTestImpl")
                << data.m_fileScenePath << ":" << msgendl
                << "    TOTALERROR: " << result.getTotalError() << msgendl
                << "    ERRORBYDOF: " << errorByDof;
        }
    }
}



void TopologyRegression_test::runTestImpl(RegressionSceneData data, sofa::simulation::Node::SPtr root, bool createReference)
{
    if (!createReference)
    {
        //We add CompareTopology components: as it derives from the ReadTopology, we use the ReadTopologyActivator to enable them.
        sofa::component::playback::CompareTopologyCreator compareVisitor(sofa::core::ExecParams::defaultInstance());
        compareVisitor.setCreateInMapping(data.m_mecaInMapping);
        compareVisitor.setSceneName(data.m_fileRefPath);
        compareVisitor.execute(root.get());

        sofa::component::playback::ReadTopologyActivator v_read(sofa::core::ExecParams::defaultInstance(),true);
        v_read.execute(root.get());
    }
    else
    {
        // just to create an empty file to know it is already init
        std::ofstream filestream(data.m_fileRefPath.c_str());
        filestream.close();

        sofa::component::playback::WriteTopologyCreator writeVisitor(sofa::core::ExecParams::defaultInstance());
        writeVisitor.setCreateInMapping(data.m_mecaInMapping);
        writeVisitor.setSceneName(data.m_fileRefPath);
        writeVisitor.execute(root.get());

        sofa::component::playback::WriteTopologyActivator v_write(sofa::core::ExecParams::defaultInstance() /* PARAMS FIRST */, true);
        v_write.execute(root.get());
    }

    for (unsigned int i = 0; i<data.m_steps; ++i)
    {
        sofa::simulation::node::animate(root.get(), root->getDt());
    }


    if (!createReference)
    {
        sofa::component::playback::CompareTopologyResult result(sofa::core::ExecParams::defaultInstance());
        result.execute(root.get());

        unsigned int totalErr = result.getTotalError();

        if (totalErr != 0)
        {
            const std::vector<unsigned int>& listResult = result.getErrors();
            if (listResult.size() != 5)
            {
                msg_error("TopologyRegression_test::runTestImpl")
                        << "ERROR while reading list of errors per topology type." << msgendl;
                return;
            }

            msg_error("TopologyRegression_test::runTestImpl")
                    << data.m_fileScenePath << ":" << msgendl
                    << "   TOTALERROR: " << totalErr << msgendl
                    << " Number of topology container: " << result.getNumCompareTopology() << msgendl
                    << " Errors per type per step over " << data.m_steps << " steps. "<< msgendl
                    << "   EDGES ERRORS: " << (float)listResult[0]/data.m_steps << msgendl
                    << "   TRIANGLES ERRORS: " << (float)listResult[1]/data.m_steps << msgendl
                    << "   QUADS ERRORS: " << (float)listResult[2]/data.m_steps << msgendl
                    << "   TETRAHEDRA ERRORS: " << (float)listResult[3]/data.m_steps << msgendl
                    << "   HEXAHEDRA ERRORS: " << (float)listResult[4]/data.m_steps << msgendl;
        }
    }
}





GTEST_ALLOW_UNINSTANTIATED_PARAMETERIZED_TEST(StateRegression_test);

/// Create one instance of StateRegression_test per scene in stateRegressionSceneList.m_scenes list
/// Note: if N differents TEST_P(StateRegression_test, test_N) are created this will create M x N gtest. M being the number of values in the list.
INSTANTIATE_TEST_SUITE_P(Regression_test,
    StateRegression_test,
    ::testing::ValuesIn( stateRegressionSceneList.m_scenes ),
    StateRegression_test::getTestName);

// Run state regression test on the listed scenes
TEST_P(StateRegression_test, sceneTest)
{
    runTest(GetParam());
}

GTEST_ALLOW_UNINSTANTIATED_PARAMETERIZED_TEST(TopologyRegression_test);

//// Create one instance or TopologyRegression_test per scene in topologyRegressionSceneList.m_scenes
INSTANTIATE_TEST_SUITE_P(Regression_test,
    TopologyRegression_test,
    ::testing::ValuesIn( topologyRegressionSceneList.m_scenes ),
    TopologyRegression_test::getTestName);

//// Run state regression test on these scenes
TEST_P(TopologyRegression_test, sceneTest)
{
    runTest(GetParam());
}


} // namespace sofa
