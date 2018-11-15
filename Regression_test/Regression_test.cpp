#include "RegressionSceneList.h"

#include <sofa/helper/system/FileRepository.h>
#include <sofa/helper/system/FileSystem.h>
#include <sofa/helper/testing/BaseTest.h>
using sofa::helper::testing::BaseTest;

#include <SofaComponentBase/initComponentBase.h>
#include <SofaComponentCommon/initComponentCommon.h>
#include <SofaComponentGeneral/initComponentGeneral.h>
#include <SofaComponentAdvanced/initComponentAdvanced.h>
#include <SofaComponentMisc/initComponentMisc.h>

#include <SofaExporter/WriteState.h>
#include <SofaGeneralLoader/ReadState.h>
#include <SofaSimulationGraph/DAGSimulation.h>
#include <SofaSimulationGraph/testing/BaseSimulationTest.h>
using sofa::helper::testing::BaseSimulationTest;
#include <SofaValidation/CompareState.h>

namespace sofa 
{

/// To Perform a Regression Test on scenes
///
/// A scene is run for a given number of steps and the state (position/velocity) of every independent dofs is stored in files. These files must be added to the repository.
/// At each commit, a test runs the scenes again for the same given number of steps. Then the independent states are compared to the references stored in the files.
///
/// The reference files are generated when running the test for the first time on a scene.
/// @warning These newly created reference files must be added to the repository.
/// If the result of the simulation changed voluntarily, these files must be manually deleted (locally) so they can be created again (by running the test).
/// Their modifications must be pushed to the repository.
///
/// Scene tested for regression must be listed in a file "list.txt" located in a "regression" directory in the test directory ( e.g. myplugin/myplugin_test/regression/list.txt)
/// Each line of the "list.txt" file must contain: a local path to the scene, the number of simulation steps to run, and a numerical epsilon for comparison.
/// e.g. "gravity.scn 5 1e-10" to run the scene "regression/gravity.scn" for 5 time steps, and the state difference must be smaller than 1e-10
///
/// As an example, have a look to SofaTest_test/regression
///
/// @author Matthieu Nesme
/// @date 2015
class Regression_test: public BaseSimulationTest, public ::testing::WithParamInterface<RegressionSceneData>
{
public:
    /// Method that given the RegressionSceneTest_Data will return the name of the file tested without the path neither the extension
    static std::string getTestName(const testing::TestParamInfo<RegressionSceneData>& p)
    {
        const std::string& path = p.param.m_fileScenePath;
        std::size_t pos = path.find_last_of("/"); // get name of the file without path

        if (pos != std::string::npos)
            pos++;

        std::string name = path.substr(pos);
        name = name.substr(0, name.find_last_of(".")); // get name of the file without extension

        return name;
    }

    /// Method to really perfom the test and compare the states vector between current simulation and reference file.
    void runStateRegressionTest(RegressionSceneData data)
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
            //            compareVisitor.setCreateInMapping(true);
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
            //            writeVisitor.setCreateInMapping(true);
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
};


/// Structure creating and storing the RegressionSceneData from Sofa src paths as a list for gtest
static struct StateRegressionSceneList : public RegressionSceneList
{
    StateRegressionSceneList()
    {
        if(!m_defaultScenesDir.empty() && !m_defaultReferencesDir.empty())
        {
            collectScenesFromPaths(m_defaultReferencesDir, m_defaultScenesDir, "RegressionStateScenes.regression-tests");
        }
        else
        {
            msg_error("StateRegressionSceneList") << "REGRESSION_SCENES_DIR and REGRESSION_REFERENCES_DIR env vars are required.";
        }
    }
} stateRegressionSceneList; // construction will fill m_scenes

// Create one GTest per scene in stateRegressionSceneList.m_scenes
INSTANTIATE_TEST_CASE_P(Regression,
    Regression_test,
    ::testing::ValuesIn( stateRegressionSceneList.m_scenes ),
    Regression_test::getTestName);
// Run state regression test on these scenes
TEST_P(Regression_test, runStateRegressionTest)
{
    runStateRegressionTest(GetParam());
}


} // namespace sofa
