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
#include "RegressionScene_list.h"

#include <sofa/helper/system/FileRepository.h>
#include <sofa/helper/system/FileSystem.h>
using sofa::helper::system::FileSystem;
#include <sofa/helper/Utils.h>
using sofa::helper::Utils;

#include <sofa/helper/testing/BaseTest.h>

#include <fstream>

namespace sofa 
{

std::string getFileName(const std::string& s)
{
    char sep = '/';

    size_t i = s.rfind(sep, s.length());
    if (i != std::string::npos)
    {
        return(s.substr(i + 1, s.length() - i));
    }

    return s;
}


RegressionSceneList::RegressionSceneList()
{
    char* scenesDirVar = getenv("REGRESSION_SCENES_DIR");
    if (scenesDirVar == NULL || !FileSystem::exists(scenesDirVar))
    {
        msg_error("RegressionSceneList") << "env var REGRESSION_SCENES_DIR must be defined";
    }
    m_scenesDir = std::string(scenesDirVar);

    char* refDirVar = getenv("REGRESSION_REFERENCES_DIR");
    if (refDirVar == NULL || !FileSystem::exists(refDirVar))
    {
        msg_error("RegressionSceneList") << "env var REGRESSION_REFERENCES_DIR must be defined";
    }
    m_referencesDir = std::string(refDirVar);
}

void RegressionSceneList::collectScenesFromList(const std::string& listFile)
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
        std::string scene;
        unsigned int steps;
        double epsilon;

        getline(iniFileStream, line);
        std::istringstream lineStream(line);
        lineStream >> scene;
        lineStream >> steps;
        lineStream >> epsilon;

        scene = listDir + "/" + scene;
        std::string reference = getFileName(scene) + ".reference";

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
        m_scenes.push_back(RegressionTestData(scene, reference, steps, epsilon));
    }
}


void RegressionSceneList::collectScenesFromDir(const std::string& directory)
{
    std::vector<std::string> regressionListFiles;
    bool error = helper::system::FileSystem::findFiles(directory, regressionListFiles, ".regression-tests", 5);
    if(error)
    {
        msg_error("RegressionSceneList") << "findFiles failed";
    }

    for (const std::string& regressionListFile : regressionListFiles)
    {
        if ( helper::system::FileSystem::exists(regressionListFile) && helper::system::FileSystem::isFile(regressionListFile) )
        {
            collectScenesFromList(regressionListFile);
        }
    }
}


void RegressionSceneList::collectScenesFromPaths(const std::string& listFilename)
{
    m_listFilename = listFilename;

    collectScenesFromDir(m_scenesDir); // m_sofaSrcDir should be an input to the test (not an env var)
}

} // namespace sofa
