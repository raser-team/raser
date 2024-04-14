import pymotor,stage,raser.motor.vitual_device as vitual_device
import raser.motor.mdo_3034_control as MD
import time
from datetime import datetime
import numpy as np
from PyQt5 import QtCore

class ControlThread(QtCore.QThread):
    def __init__(self,device):
        super(ControlThread,self).__init__()
        self.laser_stage = stage.Stage(device)
        #control message initial
        self.operation_num = 0
        self.motor = self.laser_stage.Xaxis
        self.px = 0
        self.py = 0
        self.pz = 0
        self.mv = 0
        self.po = [0,0,0]
        self.dp = [1,1,1]
        self.Np = [0,0,0]
        self.step = [8,8,8]
        self.speed = [0,0,0]

    #############################
    # 1.home 
    # 2.stop
    # 3.move set position
    # 4.move step
    # 5.zero
    # 6.set speed
    ############################
    def run(self):
        if self.operation_num == 1:
            self.laser_stage.Home(self.motor)
        elif self.operation_num == 2:
            self.laser_stage.Stop()
        elif self.operation_num == 3:
            self.laser_stage.MoveAB(self.px,self.py,self.pz)
        elif self.operation_num == 4:
            self.laser_stage.MoveRE(self.motor,self.mv)
        elif self.operation_num == 5:
            self.laser_stage.Zero(self.motor)
        elif self.operation_num == 6:
            self.laser_stage.SetSpeed(self.step,self.speed)
        else:
            time.sleep(1)

class DataCapture(QtCore.QThread):
    stop_signal = QtCore.pyqtSignal(str)
    scan_signal = QtCore.pyqtSignal()
    def __init__(self):
        super(DataCapture,self).__init__()
        self.resource = 'ASRL1::INSTR'
        self.folder = './'
        self.device = []
        self.frequency = 10
        self.point_num = 10000
        self.ymult = 0
        self.yoff = 0
        self.yzero = 0
        self.xincr = 0
        self.xzero = 0
        self.stepmode_flag = True
        self.flag = True
        self.scope = None
        self.info = ''

    def capture(self):
        filename = self.folder + '/TCT' + datetime.now().isoformat().replace(':','') + '.csv'
        self.pos = [self.device[0].get_status_position(),self.device[1].get_status_position(),self.device[2].get_status_position()]
        time,voltage = self.scope.readWave(self.ymult,self.yzero,self.yoff,self.xincr,self.xzero,self.point_num)
        myfile = open(filename,'w+')
        myfile.write('oscilloscope,' + self.info + '\n')
        myfile.write(',' + 'x' + ',' + str(self.pos[0]) + '\n')
        myfile.write(',' + 'y' + ',' + str(self.pos[1]) + '\n')
        myfile.write(',' + 'z' + ',' + str(self.pos[2]) + '\n')
        self.scope.save_wave_data(time,voltage,myfile)
        print("capture done!")
        myfile.close()

        if self.flag == False:
            self.stop_signal.emit('stop')
            #print("pause##########")
            #self.timer.stop()
            #self.finished()
        self.scan_signal.emit()          #emit scan continue signal

    def run(self):
        self.timer = QtCore.QTimer()
        if self.stepmode_flag:
            time.sleep(0.1)
            self.capture()
        else:
            self.timer.start(int(1000/self.frequency))
            self.info = self.scope.testIO()
            self.timer.timeout.connect(self.capture)
            self.stop_signal.connect(self.timer.stop)
            self.exec()


class ReadyThread(QtCore.QThread):
    sinOut = QtCore.pyqtSignal(str)
    def __init__(self):
        super(ReadyThread,self).__init__()
        self.resource_name = ''
        self.channel = 1
        self.point_number = 10000
        self.message = 'Nothing has done!'

    def run(self):
        self.scope = MD.MDO3034C(self.resource_name)
        msg = self.scope.testIO()
        self.message = "ocsilloscope information:" + msg
        self.sinOut.emit('open')
        self.scope.readSet('ch' + str(self.channel),str(self.point_number))
        self.message = "read set complete!"
        self.sinOut.emit('readset')
        self.ymult,self.yzero,self.yoff,self.xincr,self.xzero = self.scope.readOffset()
        self.message = "read offset complete!"
        self.sinOut.emit('offset')

class ScanThread(QtCore.QThread):
    CaptureSignal = QtCore.pyqtSignal(str)
    def __init__(self,device):
        super(ScanThread,self).__init__()
        self.laser_stage = stage.Stage(device)
        self.pos_o = [0,0,0]
        self.dp = [1,1,1]
        self.Np = [0,0,0]
        self.flag = False                #stop flag
        self.continue_flag = True

    def scan(self):
        self.x0 = self.pos_o[0] 
        self.y0 = self.pos_o[1]
        self.z0 = self.pos_o[2]
        self.dx = self.dp[0]
        self.dy = self.dp[1]
        self.dz = self.dp[2]
        self.Nx = self.Np[0]
        self.Ny = self.Np[1]
        self.Nz = self.Np[2]
        #preprocess the situation when Nx = 0 or Ny = 0 or Nz = 0
        if self.Nx == 0:
            self.dx = 0
            self.Nx = 1
        if self.Ny == 0:
            self.dy = 0
            self.Ny = 1
        if self.Nz == 0:
            self.dz = 0
            self.Nz = 1

        if self.flag:
            self.laser_stage.MoveAB(self.x0,self.y0,self.z0)
            print("move ab\n")
            
            # scan step by step
            self.flag1 = self.flag2 = -1
            for self.i in range(0, self.Nz):
                if self.flag == False:
                    print("break\n")
                    break
                if self.dy == 0: self.laser_stage.MoveAB(self.x0, self.laser_stage.Yaxis.get_status_position(), self.laser_stage.Zaxis.get_status_position())
                if self.dx == 0: self.laser_stage.MoveAB(self.laser_stage.Xaxis.get_status_position(), self.y0, self.laser_stage.Zaxis.get_status_position())
                self.laser_stage.MoveRE(self.laser_stage.Zaxis, self.dz)
                if self.dz != 0:
                    self.CaptureSignal.emit('capture')      #one step move complete,emit capture signal
                    time.sleep(0.1)
                    while True:
                        if self.continue_flag:
                            break

                self.flag1 = self.flag1 * (-1)
                for self.j in range(0, self.Nx):
                    if self.flag == False:
                        print("break\n")
                        break
                    if self.dz == 0: self.laser_stage.MoveAB(self.laser_stage.Xaxis.get_status_position(), self.y0, self.laser_stage.Zaxis.get_status_position()) # x-y scan
                    self.laser_stage.MoveRE(self.laser_stage.Xaxis, self.dx)
                    if self.dx != 0:
                        self.CaptureSignal.emit('capture')
                        time.sleep(0.1)
                        while True:
                            if self.continue_flag:
                                break
                    print(self.laser_stage.Xaxis.get_status_position(),self.laser_stage.Yaxis.get_status_position(),self.laser_stage.Zaxis.get_status_position())

                    self.flag2 = self.flag2 * (-1)
                    for self.k in range(0, self.Ny):
                        if self.flag == False:
                            print("break\n")
                            break
                        self.laser_stage.MoveRE(self.laser_stage.Yaxis, self.dy)
                        if self.dy != 0:
                            self.CaptureSignal.emit('capture')
                            time.sleep(0.1)
                            while True:
                                if self.continue_flag:
                                    break
                        print(self.laser_stage.Xaxis.get_status_position(),self.laser_stage.Yaxis.get_status_position(),self.laser_stage.Zaxis.get_status_position())  

    def run(self):
        self.scan()
