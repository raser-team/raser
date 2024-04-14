#this file is used to make a vitual device

import pymotor
import sys
import os
import re 
import tempfile
import urllib.parse

class VitualDevice(pymotor.Motor):
    def __init__(self,device_name):
        if sys.version_info < (3,0):
            print("Using virtual device needs python3!")
            exit(1)

        # use URI for virtual device when there is new urllib python3 API
        tempdir = tempfile.gettempdir() + "/" + str(device_name)+ ".bin"
        print("\ntempdir: " + tempdir)
        # "\" <-> "/"
        if os.altsep:
            tempdir = tempdir.replace(os.sep, os.altsep)

        uri = urllib.parse.urlunparse(urllib.parse.ParseResult \
                                (scheme="file",netloc=None, path=tempdir,\
                                params=None, query=None, fragment=None))
        # converter address to b
        self.open_name = re.sub(r'^file', 'xi-emu', uri).encode()
        super(VitualDevice,self).__init__(self.open_name)
       
