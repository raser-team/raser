#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import re



def main():

	rootpath = os.getcwd()
	input_txt = rootpath+"/geant4/build/CMakeCache.txt"
	f = open(input_txt,'r')
	alllines = f.readlines()
	f.close()
	f = open(input_txt,'w+')
	for line in alllines:
		if "Boost_INCLUDE_DIR:PATH" in line:
			line = "Boost_INCLUDE_DIR:PATH=/cvmfs/exo.ihep.ac.cn/sw/nEXO_new/ExternalLibs/Boost/1.73.0/include"
		if "Boost_LIBRARY_DIR_DEBUG" in line:
			line = "Boost_LIBRARY_DIR_DEBUG:PATH=/cvmfs/exo.ihep.ac.cn/sw/nEXO_new/ExternalLibs/Boost/1.73.0/lib"
		if "Boost_LIBRARY_DIR_RELEASE" in line:
			line = "Boost_LIBRARY_DIR_RELEASE:PATH=/cvmfs/exo.ihep.ac.cn/sw/nEXO_new/ExternalLibs/Boost/1.73.0/lib"
		if "Boost_PYTHON_LIBRARY_DEBUG" in line:
			line = "Boost_PYTHON_LIBRARY_DEBUG:FILEPATH=/cvmfs/exo.ihep.ac.cn/sw/nEXO_new/ExternalLibs/Boost/1.73.0/lib/libboost_python36.so"
		if "Boost_PYTHON_LIBRARY_RELEASE" in line:
			line = "Boost_PYTHON_LIBRARY_RELEASE:FILEPATH=/cvmfs/exo.ihep.ac.cn/sw/nEXO_new/ExternalLibs/Boost/1.73.0/lib/libboost_python36.so"		
		f.writelines(line)
	
if __name__ == '__main__':
    main()