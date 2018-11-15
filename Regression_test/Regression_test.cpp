#include "Regression_test.h"

#include <sofa/helper/system/FileRepository.h>
#include <sofa/helper/system/FileSystem.h>

using sofa::helper::testing::BaseTest;

#include <SofaComponentBase/initComponentBase.h>
#include <SofaComponentCommon/initComponentCommon.h>
#include <SofaComponentGeneral/initComponentGeneral.h>
#include <SofaComponentAdvanced/initComponentAdvanced.h>
#include <SofaComponentMisc/initComponentMisc.h>

#include <SofaExporter/WriteState.h>
#include <SofaGeneralLoader/ReadState.h>
#include <SofaSimulationGraph/DAGSimulation.h>

using sofa::helper::testing::BaseSimulationTest;
#include <SofaValidation/CompareState.h>

namespace sofa 
{

std::string BaseRegression_test::getTestName(const testing::TestParamInfo<RegressionSceneData>& p)
{
    const std::string& path = p.param.m_fileScenePath;
    std::size_t pos = path.find_last_of("/"); // get name of the file without path

    if (pos != std::string::npos)
        pos++;

    std::string name = path.substr(pos);
    name = name.substr(0, name.find_last_of(".")); // get name of the file without extension

    return name;
}



void StateRegression_test::runTest(RegressionSceneData data)
{
    msg_info("Regression_test::runStateRegressionTest") << "Testing " << data.m_fileScenePath;

    sofa::component::initComponentBase();
    sofa::component::initComponentCommon();
    sofa::component::initComponentGeneral();
    sofa::component::initComponentAdvanced();
    sofa::component::initComponentMisc();

    simulation::Simulation* simulation = simulation::getSimulation();

    // Load the scene
    sofa::simulation::Node::SPtr root = simulation->load(data.m_fileScenePath.c_str());

    // if no root node -> loading failed
    if (root == NULL)
    {
        msg_error("Regression_test::runStateRegressionTest")
            << data.m_fileScenePath << " could not be loaded." << msgendl;
        return;
    }

    simulation->init(root.get());

    // TODO lancer visiteur pour dumper MO
    // comparer ce dump avec le fichier sceneName.regressionreference

    bool initializing = false;

    if (helper::system::FileSystem::exists(data.m_fileRefPath) && !helper::system::FileSystem::isDirectory(data.m_fileRefPath))
    {
        // Add CompareState components: as it derives from the ReadState, we use the ReadStateActivator to enable them.
        sofa::component::misc::CompareStateCreator compareVisitor(sofa::core::ExecParams::defaultInstance());

        compareVisitor.setCreateInMapping(data.m_mecaInMapping);
        compareVisitor.setSceneName(data.m_fileRefPath);
        compareVisitor.execute(root.get());

        sofa::component::misc::ReadStateActivator v_read(sofa::core::ExecParams::defaultInstance() /* PARAMS FIRST */, true);
        v_read.execute(root.get());
    }
    else // create reference
    {
        msg_warning("Regression_test::runStateRegressionTest") << "Non existing reference created: " << data.m_fileRefPath;

        // just to create an empty file to know it is already init
        std::ofstream filestream(data.m_fileRefPath.c_str());
        filestream.close();

        initializing = true;
        sofa::component::misc::WriteStateCreator writeVisitor(sofa::core::ExecParams::defaultInstance());

        writeVisitor.setCreateInMapping(data.m_mecaInMapping);
        writeVisitor.setSceneName(data.m_fileRefPath);
        writeVisitor.execute(root.get());

        sofa::component::misc::WriteStateActivator v_write(sofa::core::ExecParams::defaultInstance() /* PARAMS FIRST */, true);
        v_write.execute(root.get());
    }

    for (unsigned int i = 0; i<data.m_steps; ++i)
    {
        simulation->animate(root.get(), root->getDt());
    }

    if (!initializing)
    {
        // Read the final error: the summation of all the error made at each time step
        sofa::component::misc::CompareStateResult result(sofa::core::ExecParams::defaultInstance());
        result.execute(root.get());

        double errorByDof = result.getErrorByDof() / double(result.getNumCompareState());
        if (errorByDof > data.m_epsilon)
        {
            msg_error("Regression_test::runStateRegressionTest")
                << data.m_fileScenePath << ":" << msgendl
                << "    TOTALERROR: " << result.getTotalError() << msgendl
                << "    ERRORBYDOF: " << errorByDof;
        }
    }

    // Clear and prepare for next scene
    simulation->unload(root.get());
    root.reset();
}



void TopologyRegression_test::runTest(RegressionSceneData data)
{

}








/// Create one instance of StateRegression_test per scene in stateRegressionSceneList.m_scenes list
/// Note: if N differents TEST_P(StateRegression_test, test_N) are created this will create M x N gtest. M being the number of values in the list.
INSTANTIATE_TEST_CASE_P(Regression_test,
    StateRegression_test,
    ::testing::ValuesIn( stateRegressionSceneList.m_scenes ),
    StateRegression_test::getTestName);

// Run state regression test on the listed scenes
TEST_P(StateRegression_test, sceneTest)
{
    runTest(GetParam());
}


//// Create one instance or TopologyRegression_test per scene in topologyRegressionSceneList.m_scenes
INSTANTIATE_TEST_CASE_P(Regression_test,
    TopologyRegression_test,
    ::testing::ValuesIn( topologyRegressionSceneList.m_scenes ),
    TopologyRegression_test::getTestName);

//// Run state regression test on these scenes
TEST_P(TopologyRegression_test, sceneTest)
{
    runTest(GetParam());
}


} // namespace sofa
