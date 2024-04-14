import ctypes
from ctypes import *
import time
import os
import sys
import re
import platform
#from VitualDevice import *
import tempfile

cur_dir = os.path.abspath(os.path.dirname(__file__))
ximc_dir = os.path.join(cur_dir, "..", "ximc")
ximc_package_dir = os.path.join(ximc_dir, "crossplatform", "wrappers", "python")
sys.path.append(ximc_package_dir)  # add ximc.py wrapper to python path

print(ximc_package_dir)

if platform.system()  == "Windows":
    print("windows#################")
    if platform.architecture() == ('64bit', 'WindowsPE') :
        libdir = os.path.join(ximc_dir, "win64")
        #print(platform.architecture())
    else:
        libdir = os.path.join(ximc_dir,"win32")
        #print(platform.architecture())
        

    #print(libdir)
os.environ["Path"] = libdir + ";" + os.environ["Path"]  # add dll

if sys.version_info >= (3,0):

    try:
        from pyximc import *
    except ImportError as err:
        print ("Can't import pyximc module.\
               The most probable reason is that \
               you haven't copied pyximc.py to the working directory.\
               See developers' documentation for details.")
        exit()
    except OSError as err:
        print ("Can't load libximc library.\
               Please add all shared libraries to the appropriate places \
               (next to pyximc.py on Windows). \
               It is decribed in detailes in developers' documentation.")
        exit()

# variable 'lib' points to a loaded library
# note that ximc uses stdcall on win
print("Library loaded")
sbuf = create_string_buffer(64)
lib.ximc_version(sbuf)
print("Library version: " + sbuf.raw.decode())

DEBUG = False
def log(s):
    if DEBUG:
        print(s)

def enum_device():
    devenum = lib.enumerate_devices(EnumerateFlags.ENUMERATE_PROBE, None)
    print("Device enum handle: " + repr(devenum))
    print("Device enum handle type: " + repr(type(devenum)))

    dev_count = lib.get_device_count(devenum)
    print("Device count: " + repr(dev_count))

    controller_name = controller_name_t()
    enum_name = ['','','']
    friend_name = ['', '', '']
    for dev_ind in range(0, dev_count):
        enum_name[dev_ind] = lib.get_device_name(devenum, dev_ind)
        result = lib.get_enumerate_device_controller_name(devenum, dev_ind,
                                                                   byref(controller_name))
        if result == Result.Ok:
            friend_name[dev_ind] = controller_name.ControllerName
            print("Enumerated device #{} name (port name): ".format(dev_ind) \
                    + repr(enum_name[dev_ind]) \
                    + ". Friendly name: " \
                    + repr(controller_name.ControllerName) \
                    + ".")

    return enum_name, dev_count, friend_name

class Motor():
    def __init__(self, device_name = None):
        self.lib = lib
        self.device_id = self.open_device(device_name)


    def set_speed(self,step,speed):
        log("\nset speed\n")
        speed_settings = move_settings_t()
        speed_settings.Speed = speed
        speed_settings.uSpeed = step
        speed_settings.Accel = 1000
        speed_settings.Decel = 2000
        speed_settings.AntiplaySpeed = 50
        speed_settings.uAntiplaySpeed = 0
        result = self.lib.set_move_settings(self.device_id,byref(speed_settings))
        print("move settings Result:" + repr(result))
        move_settings = move_settings_t()
        result = self.lib.get_move_settings(self.device_id,byref(move_settings))
        if result == 0:
            print("move settings:",move_settings.Speed,move_settings.uSpeed,move_settings.Accel,move_settings.Decel)


    def home(self):
        log("\nMoving home")
        result = self.lib.command_homezero(self.device_id)
        log("Result: " + repr(result))

    def zero(self):
        log("\nzero the position")
        result = self.lib.command_zero(self.device_id)
        log("Result: " + repr(result))

    def forward(self, distance):      # move forward Deltaposition
        log("\nShifting")
        log(distance)
        dis = ctypes.c_int()
        dis.value = int(distance)
        move_settings = move_settings_t()
        result = self.lib.get_move_settings(self.device_id,byref(move_settings))
        if result == 0:
            print("move settings:",move_settings.Speed,move_settings.uSpeed,move_settings.Accel,move_settings.Decel,move_settings.AntiplaySpeed,move_settings.uAntiplaySpeed)
        result = self.lib.command_movr(self.device_id, dis, 0)
        log("Result: " + repr(result))

    def backward(self, distance):    # move backward Deltaposition
        log("\nShifting")
        shift = ctypes.c_int()
        shift.value = 0 - int(distance) # in oppsite direction
        result = self.lib.command_movr(self.device_id, shift, 0)
        log("Result: " + repr(result))

    def moveforward(self):       
        log("\nMoving forward")
        result = self.lib.command_right(self.device_id)
        log("Result: " + repr(result))

    def movebackward(self):
        log("\nMoving backward")
        result = self.lib.command_left(self.device_id)
        log("Result: " + repr(result))

    def move(self, position):        # move to the Setposition
        log("\nMoving position")
        pos = ctypes.c_int()
        pos.value = int(position)
        result = self.lib.command_move(self.device_id, pos, 0)
        print("Result: " + repr(result))

    def stop(self):
        log("\nStopping")
        result = self.lib.command_stop(self.device_id)
        log("Result: " + repr(result))

    def get_position(self):
        print("\nRead position")
        pos = get_position_t()
        result = self.lib.get_position(self.device_id, byref(pos))
        print("Result: " + repr(result))
        if result == Result.Ok:
            print("Position: " + repr(pos.Position))
            return pos.Position

    def set_position(self, position):
        print("\nSet position")
        pos = set_position_t()
        pos.Position = position
        result = self.lib.set_position(self.device_id, byref(pos))
        print("Result: " + repr(result))
        if result == Result.Ok:
            print("Setting Position Done")

    def get_status_position(self):
        log("\nGet status")
        status = status_t()
        result = self.lib.get_status(self.device_id, byref(status))
        log("Result: " + repr(result))
        if result == Result.Ok:
            log("Status.CurPosition: " + repr(status.CurPosition))
        return status.CurPosition

    def get_status(self):
        log("\nGet status")
        status = status_t()
        result = self.lib.get_status(self.device_id, byref(status))
        log("Result: " + repr(result))
        if result == Result.Ok:
            log("Status.CurPosition: " + repr(status.CurPosition))

    def get_name(self,devenum,dev_index):
        return self.lib.get_device_name(devenum,dev_index)


    def open_device(self, open_name):
        device_id = ctypes.c_int()
        print("\nOpen device " + repr(open_name))
        device_id = self.lib.open_device(open_name)
        
        print("\ndevice id:" + repr(device_id))
        return device_id

    def close_device(self):
        result = self.lib.close_device(byref(cast(self.device_id, POINTER(c_int))))
        if result == Result.Ok:
            print("Close device " + repr(self.device_id))


