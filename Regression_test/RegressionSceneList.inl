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
#pragma once
#include "RegressionSceneList.h"

#include <sofa/helper/logging/Messaging.h>
#include <sofa/helper/system/FileRepository.h>
#include <sofa/helper/system/FileSystem.h>
using sofa::helper::system::FileSystem;
#include <sofa/testing/BaseTest.h>
#include <sofa/core/ExecParams.h>
#include <sofa/helper/logging/Messaging.h>
#include <fstream>

namespace sofa
{

template <typename T>
RegressionSceneList<T>::RegressionSceneList()
{
    const auto listType = static_cast<T*>(this)->getListType();

    char* scenesDirVar = getenv("REGRESSION_SCENES_DIR");
    if (scenesDirVar == nullptr)
    {
        msg_error(listType) << "The environment variable REGRESSION_SCENES_DIR is required but is missing or is empty.";
        return;
    }


    char* refDirVar = getenv("REGRESSION_REFERENCES_DIR");
    if (refDirVar == nullptr)
    {
        msg_error(listType) << "The environment variable REGRESSION_REFERENCES_DIR is required but is missing or is empty.";
        return;
    }

    //Iterate through the environement variables to find substrings delimited by ':'
    size_t pos_start = 0;
    size_t pos_end;

    std::string multipleSceneDir(scenesDirVar);
    std::string tempSceneFolder;
    std::vector<std::string>  sceneFolderVector;

    std::string multipleRefDir(refDirVar);
    std::string tempRefFolder;
    std::vector<std::string>  refFolderVector;

    //REGRESSION_SCENES_DIR
    while ((pos_end = multipleSceneDir.find('|', pos_start)) != std::string::npos)
    {
        tempSceneFolder = multipleSceneDir.substr (pos_start, pos_end - pos_start);
        pos_start = pos_end + 1;
        sceneFolderVector.push_back(tempSceneFolder);
    }
    if(multipleSceneDir.substr(pos_start,std::string::npos).size()) //get what's after the last '|' if exists
        sceneFolderVector.push_back(multipleSceneDir.substr(pos_start,std::string::npos));

    //REGRESSION_REFERENCES_DIR
    pos_start = 0;
    while ((pos_end = multipleRefDir.find('|', pos_start)) != std::string::npos)
    {
        tempRefFolder = multipleRefDir.substr (pos_start, pos_end - pos_start);
        pos_start = pos_end + 1;
        refFolderVector.push_back(tempRefFolder);
    }
    if(multipleRefDir.substr(pos_start,std::string::npos).size()) //get what's after the last '|' if exists
        refFolderVector.push_back(multipleRefDir.substr(pos_start,std::string::npos));

    if(sceneFolderVector.size() != refFolderVector.size())
    {
        msg_error(listType) << "The environment variables REGRESSION_SCENES_DIR and REGRESSION_REFERENCES_DIR must contain the same number of folder, corresponding to a pair of matching scene/reference folder.";
        return;
    }

    //Now gather all the regression test file in all the given directories
    for(size_t i=0; i<sceneFolderVector.size(); ++i)
    {
        if (!FileSystem::exists(FileSystem::cleanPath(sceneFolderVector[i])))
        {
            msg_error(listType) << "The environment variable REGRESSION_SCENES_DIR is invalid (its content does not exist or is incorrect); the faulty directory is " << sceneFolderVector[i];
            return;
        }
        const std::string scenesDir = std::string(FileSystem::cleanPath(sceneFolderVector[i]));


        if (!FileSystem::exists(FileSystem::cleanPath(refFolderVector[i])))
        {
            msg_error(listType) << "The environment variable REGRESSION_REFERENCES_DIR is invalid (its content does not exist or is incorrect); the faulty directory is " << refFolderVector[i];
            return;
        }

        const std::string referencesDir = std::string(FileSystem::cleanPath(refFolderVector[i]));

        collectScenesFromPaths(referencesDir, scenesDir, static_cast<T*>(this)->getListFilename());


    }
}

template <typename T>
void RegressionSceneList<T>::collectScenesFromList(const std::string& referencesDir, const std::string& scenesDir, const std::string& listFile)
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

template <typename T>
void RegressionSceneList<T>::collectScenesFromDir(const std::string& referencesDir, const std::string& scenesDir, const std::string& listFilename)
{
    std::vector<std::string> regressionListFiles;
    int error = helper::system::FileSystem::findFiles(scenesDir, regressionListFiles, listFilename, 5);
    if(error <= 0)
    {
        msg_error("RegressionSceneList") << "findFiles failed, error code returned: " << error;
    }

    for (const std::string& regressionListFile : regressionListFiles)
    {
        if ( helper::system::FileSystem::exists(regressionListFile) && helper::system::FileSystem::isFile(regressionListFile) )
        {
            collectScenesFromList(referencesDir, scenesDir, regressionListFile);
        }
    }
}


template <typename T>
void RegressionSceneList<T>::collectScenesFromPaths(const std::string& referencesDir, const std::string& scenesDir, const std::string& listFilename)
{
    collectScenesFromDir(referencesDir, scenesDir, listFilename); // m_sofaSrcDir should be an input to the test (not an env var)
}

} // namespace sofa
