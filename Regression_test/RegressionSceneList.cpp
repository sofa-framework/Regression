/******************************************************************************
*       SOFA, Simulation Open-Framework Architecture, development version     *
*                (c) 2006-2018 INRIA, USTL, UJF, CNRS, MGH                    *
*                                                                             *
* This program is free software; you can redistribute it and/or modify it     *
* under the terms of the GNU General Public License as published by the Free  *
* Software Foundation; either version 2 of the License, or (at your option)   *
* any later version.                                                          *
*                                                                             *
* This program is distributed in the hope that it will be useful, but WITHOUT *
* ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or       *
* FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for    *
* more details.                                                               *
*                                                                             *
* You should have received a copy of the GNU General Public License along     *
* with this program. If not, see <http://www.gnu.org/licenses/>.              *
*******************************************************************************
* Authors: The SOFA Team and external contributors (see Authors.txt)          *
*                                                                             *
* Contact information: contact@sofa-framework.org                             *
******************************************************************************/
#include "RegressionSceneList.h"

#include <sofa/helper/system/FileRepository.h>
#include <sofa/helper/system/FileSystem.h>
using sofa::helper::system::FileSystem;
#include <sofa/helper/testing/BaseTest.h>

#include <fstream>

namespace sofa
{

RegressionSceneList::RegressionSceneList()
{
    char* scenesDirVar = getenv("REGRESSION_SCENES_DIR");
    if (scenesDirVar != NULL && FileSystem::exists(scenesDirVar))
    {
        m_defaultScenesDir = std::string(scenesDirVar);
    }

    char* refDirVar = getenv("REGRESSION_REFERENCES_DIR");
    if (refDirVar != NULL && FileSystem::exists(refDirVar))
    {
        m_defaultReferencesDir = std::string(refDirVar);
    }
}


void RegressionSceneList::collectScenesFromList(const std::string& referencesDir, const std::string& scenesDir, const std::string& listFile)
{
    // lire plugin_test/regression_scene_list -> (file,nb time steps,epsilon)
    // pour toutes les scenes
    const std::string listDir = FileSystem::getParentDirectory(listFile);
    msg_info("Regression_test") << "Parsing " << listFile;

    // parser le fichier -> (file,nb time steps,epsilon)
    std::ifstream iniFileStream(listFile.c_str());
    while (!iniFileStream.eof())
    {
        std::string line;
        std::string sceneFromList;
        unsigned int steps = 100;
        double epsilon = 1e-4;
        bool testInMapping = false;
        bool dumpOnlyLastStep = false;

        getline(iniFileStream, line);

        if (line.empty() || line[0] == '#')
            continue;

        std::istringstream lineStream(line);
        lineStream >> sceneFromList;
        lineStream >> steps;
        lineStream >> epsilon;
        lineStream >> testInMapping;
        lineStream >> dumpOnlyLastStep;


        std::string scene = listDir + "/" + sceneFromList;
        std::string sceneFromScenesDir(scene);
        sceneFromScenesDir.erase( sceneFromScenesDir.find(scenesDir+"/"), scenesDir.size()+1 );
        std::string reference = referencesDir + "/" + sceneFromScenesDir + ".reference";

#ifdef WIN32
        // Minimize absolute scene path to avoid MAX_PATH problem
        if (scene.length() > MAX_PATH)
        {
            ADD_FAILURE() << scene << ": path is longer than " << MAX_PATH;
            continue;
        }
        char buffer[MAX_PATH];
        GetFullPathNameA(scene.c_str(), MAX_PATH, buffer, nullptr);
        scene = std::string(buffer);
        std::replace(scene.begin(), scene.end(), '\\', '/');
#endif // WIN32
        m_scenes.push_back( RegressionSceneData(scene, reference, steps, epsilon, testInMapping, dumpOnlyLastStep) );
    }
}


void RegressionSceneList::collectScenesFromDir(const std::string& referencesDir, const std::string& scenesDir, const std::string& listFilename)
{
    std::vector<std::string> regressionListFiles;
    bool error = helper::system::FileSystem::findFiles(scenesDir, regressionListFiles, listFilename, 5);
    if(error <= 0)
    {
        msg_error("RegressionSceneList") << "findFiles failed";
    }

    for (const std::string& regressionListFile : regressionListFiles)
    {
        if ( helper::system::FileSystem::exists(regressionListFile) && helper::system::FileSystem::isFile(regressionListFile) )
        {
            collectScenesFromList(referencesDir, scenesDir, regressionListFile);
        }
    }
}


void RegressionSceneList::collectScenesFromPaths(const std::string& referencesDir, const std::string& scenesDir, const std::string& listFilename)
{
    collectScenesFromDir(referencesDir, scenesDir, listFilename); // m_sofaSrcDir should be an input to the test (not an env var)
}

} // namespace sofa
