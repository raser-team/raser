#!/usr/bin/env bash

# Main driver to build GEANT4 as user inside raser 
# Author SHI Xin <shixin@ihep.ac.cn>
# Created [2021-06-28 Mon 12:47]
home_path=$PWD
cd $home_path
python3 ext/geant4_install_boost_change.py

