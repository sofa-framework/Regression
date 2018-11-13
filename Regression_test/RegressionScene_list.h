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
#ifndef SOFA_RegressionScene_list_H
#define SOFA_RegressionScene_list_H

#include <sofa/helper/system/FileRepository.h>
#include <sofa/helper/system/FileSystem.h>
using sofa::helper::system::FileSystem;
#include <sofa/helper/Utils.h>
using sofa::helper::Utils;

#include <sofa/helper/testing/BaseTest.h>

#include <fstream>

namespace sofa 
{

/// a struct to store all info to perform the regression test
struct RegressionSceneTest_Data
{
    RegressionSceneTest_Data(const std::string& fileScenePath, const std::string& fileRefPath, unsigned int steps, double epsilon)
        : fileScenePath(fileScenePath)
        , fileRefPath(fileRefPath)
        , steps(steps)
        , epsilon(epsilon)
    {}

    std::string fileScenePath;
    std::string fileRefPath;
    unsigned int steps;
    double epsilon;
};

/**
    This class will parse a given list of path (project env paths) and search for list of scene files to collect
    for future regression test.
    Main method is @sa collectScenesFromPaths
    All collected data will be store inside the vector @sa m_listScenes
*/
class RegressionScene_list
{
public:
    /// name of the file list 
    std::string m_listFilename;

    std::string m_sofaSrcDir;
    std::string m_referencesDir;

    /// List of regression Data to perform @sa RegressionSceneTest_Data
    std::vector<RegressionSceneTest_Data> m_listScenes;

    RegressionScene_list()
    {
        char* sofaDirVar = getenv("SOFA_SRC_DIR");
        if (sofaDirVar == NULL || !FileSystem::exists(sofaDirVar))
        {
            msg_error("RegressionScene_test") << "env var SOFA_SRC_DIR must be defined";
        }
        m_sofaSrcDir = std::string(sofaDirVar);

        char* refDirVar = getenv("REFERENCES_DIR");
        if (refDirVar == NULL || !FileSystem::exists(refDirVar))
        {
            msg_error("RegressionScene_test") << "env var REFERENCES_DIR must be defined";
        }
        m_referencesDir = std::string(refDirVar);
    }

protected:
    /// Method called by collectScenesFromDir to search specific regression file list inside a directory
    void collectScenesFromList(const std::string& listFile)
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
            m_listScenes.push_back(RegressionSceneTest_Data(scene, reference, steps, epsilon));
        }
    }


    /// Method called by @sa collectScenesFromPaths to loop on the subdirectories to find regression file list
    void collectScenesFromDir(const std::string& directory)
    {
        std::vector<std::string> regressionListFiles;
        bool error = helper::system::FileSystem::findFiles(directory, regressionListFiles, ".regression-tests", 5);
        if(error)
        {
            msg_error("collectScenesFromDir") << "findFiles failed";
        }

        for (const std::string& regressionListFile : regressionListFiles)
        {
            if ( helper::system::FileSystem::exists(regressionListFile) && helper::system::FileSystem::isFile(regressionListFile) )
            {
                collectScenesFromList(regressionListFile);
            }
        }
    }


    /// Main method to start the parsing of regression file list on specific Sofa src paths
    virtual void collectScenesFromPaths(const std::string& listFilename)
    {
        m_listFilename = listFilename;

        collectScenesFromDir(m_sofaSrcDir); // m_sofaSrcDir should be an input to the test (not an env var)
    }


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
};



} // namespace sofa

#endif // SOFA_RegressionScene_list_H
