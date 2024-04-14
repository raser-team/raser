import time
import pymotor

tctEnable = True

class Stage():
    def __init__(self,device):
        self.Xaxis = device[0]
        self.Yaxis = device[1]
        self.Zaxis = device[2]
        self.flag = 1

    def SetSpeed(self,step,speed):
        self.Xaxis.set_speed(step[0],speed[0])
        self.Yaxis.set_speed(step[1],speed[1])
        self.Zaxis.set_speed(step[2],speed[2])
        

    def Home(self,motor):
        if tctEnable:
            motor.home()

    def Zero(self,motor):
        if tctEnable:
            motor.zero()

    def Stop(self):
        if tctEnable:
            self.Xaxis.stop()
            self.Yaxis.stop()
            self.Zaxis.stop()

    '''
    def Limits(self):
        self.Limits = Limits(self)
    '''
    def MoveAB(self,pos_X,pos_Y,pos_Z):
        if tctEnable:
            self.Xaxis.move(pos_X)
            self.Yaxis.move(pos_Y)
            self.Zaxis.move(pos_Z)
            #waiting for motor moving to (pos_X,pos_Y,pos_Z)
            while True:
                position_flag = (self.Xaxis.get_status_position() == pos_X) and (self.Yaxis.get_status_position() == pos_Y) and (self.Zaxis.get_status_position() == pos_Z)
                if position_flag:
                    break

    def MoveRE(self,motor,movement):
        UpperLimit = 100000     
        LowerLimit = -100000    
        currentPos = motor.get_status_position()
        movePos = currentPos + movement
        if currentPos + movement > UpperLimit:
            movement = UpperLimit - currentPos
        elif currentPos + movement < LowerLimit:
            movement = LowerLimit - currentPos

        if tctEnable:
            motor.forward(movement)
            #wait for accomplishing move
            while True:
                move_flag = movePos == motor.get_status_position()
                if move_flag:
                    break


    
    def Scan(self,pos_o,dp,Np):
        self.x0 = pos_o[0] 
        self.y0 = pos_o[1]
        self.z0 = pos_o[2]
        self.dx = dp[0]
        self.dy = dp[1]
        self.dz = dp[2]
        self.Nx = Np[0]
        self.Ny = Np[1]
        self.Nz = Np[2]
        self.scan_signal = False

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

        if self.flag == 1:
            self.MoveAB(self.x0,self.y0,self.z0)
            
            # scan step by step
            self.flag1 = self.flag2 = -1
            for self.i in range(0, self.Nz):
                if self.flag == 0:
                    break
                self.MoveRE(self.Zaxis, self.dz)
                if self.dz != 0:
                    self.scan_signal = True
                self.flag1 = self.flag1 * (-1)
                for self.j in range(0, self.Nx):
                    if self.flag == 0:
                        break
                    self.MoveRE(self.Xaxis, self.flag1 * self.dx)
                    if self.dx != 0:
                        self.scan_signal = True
                    print(self.Xaxis.get_status_position(),self.Yaxis.get_status_position(),self.Zaxis.get_status_position())

                    self.flag2 = self.flag2 * (-1)
                    for self.k in range(0, self.Ny):
                        if self.flag == 0:
                            break
                        self.MoveRE(self.Yaxis, self.flag2 * self.dy)
                        if self.dy != 0:
                            self.scan_signal = True
                        #time.sleep(1)
                        print(self.Xaxis.get_status_position(),self.Yaxis.get_status_position(),self.Zaxis.get_status_position())
                        #print(self.ui.CurrentPosX_2.value(),self.ui.CurrentPosY_2.value(),self.ui.CurrentPosZ_2.value())
                        #self.timer.timeout.connect(self.UpdateDesiredPos)
                        #self.timer.start(100)
                        #self.UpdateDesiredPos() 