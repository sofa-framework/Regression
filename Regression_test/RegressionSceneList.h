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

#include <string>
#include <vector>

namespace sofa 
{

/// a struct to store all info to perform the regression test
struct RegressionSceneData
{
    RegressionSceneData(const std::string& fileScenePath, const std::string& fileRefPath, unsigned int steps, double epsilon)
        : m_fileScenePath(fileScenePath)
        , m_fileRefPath(fileRefPath)
        , m_steps(steps)
        , m_epsilon(epsilon)
    {}

    std::string m_fileScenePath;
    std::string m_fileRefPath;
    unsigned int m_steps;
    double m_epsilon;
};


/**
    This class will parse a given list of path (project env paths) and search for list of scene files to collect
    for future regression test.
    Main method is @sa collectScenesFromPaths
    All collected data will be store inside the vector @sa m_listScenes
*/
class RegressionSceneList
{
public:
    std::string m_scenesDir;
    std::string m_referencesDir;

    /// List of regression Data to perform @sa RegressionSceneTest_Data
    std::vector<RegressionSceneData> m_scenes;

    RegressionSceneList();

protected:
    /// Method called by collectScenesFromDir to search specific regression file list inside a directory
    void collectScenesFromList(const std::string& listFile);

    /// Method called by @sa collectScenesFromPaths to loop on the subdirectories to find regression file list
    void collectScenesFromDir(const std::string& directory, const std::string &listFilename);

    /// Main method to start the parsing of regression file list on specific Sofa src paths
    virtual void collectScenesFromPaths(const std::string& listFilename);
};

} // namespace sofa

#endif // SOFA_RegressionScene_list_H
