#!/usr/bin/env bash

# Main driver to build GEANT4 as user inside raser 
# Author SHI Xin <shixin@ihep.ac.cn>
# Created [2021-06-28 Mon 12:47]
source /cvmfs/sft.cern.ch/lcg/contrib/gcc/10/x86_64-centos7/setup.sh
source /cvmfs/geant4.cern.ch/geant4/10.7.p02/x86_64-centos7-gcc10-optdeb/CMake-setup.sh
source /cvmfs/geant4.cern.ch/geant4/10.7.p02/x86_64-centos7-gcc10-optdeb/bin/geant4.sh
home_path=$PWD
cd $home_path/geant4/build 
echo "----cmake----"
cmake3 -DCMAKE_INSTALL_PREFIX=$home_path/geant4/install  -DGEANT4_INSTALL_DATA=ON -DGEANT4_USE_OPENGL_X11=ON -DGEANT4_INSTALL_DATADIR=$home_path/geant4/data -DGEANT4_BUILD_MULTITHREADED=ON  -DGEANT4_BUILD_TLS_MODEL=global-dynamic  -DGEANT4_USE_PYTHON=ON ../src/geant4.10.07.p02  
make -j 24 
make install 

