# -*- encoding: utf-8 -*-
'''
Description:  Simulate e-h pairs drifting and calculate induced current
@Date       : 2021/09/02 14:01:46
@Author     : Yuhang Tan, Chenxi Fu
@version    : 2.0
'''
import random
import numpy as np
import math
import ROOT
from .model import Material
from .model import Vector

t_bin = 50e-12
t_end = 10e-9
t_start = 0
delta_t = 10e-12
pixel = 25 #um
min_intensity = 1 # V/cm

class Carrier:
    """
    Description:
        Definition of carriers and the record of their movement
    Parameters:
        x_init, y_init, z_init, t_init : float
            initial space and time coordinates in um and s
        charge : float
            a set of drifting carriers, absolute value for number, sign for charge
    Attributes:
        x, y, z, t : float
            space and time coordinates in um and s
        path : float[]
            recording the carrier path in [x, y, z, t]
        charge : float
            a set of drifting carriers, absolute value for number, sign for charge
        signal : float[]
            the generated signal current on the reading electrode
        end_condition : 0/string
            tag of how the carrier ended drifting
    Modify:
        2022/10/28
    """
    def __init__(self, x_init, y_init, z_init, t_init, charge, material, read_ele_num):
        self.x = x_init
        self.y = y_init
        self.z = z_init
        self.t = t_init
        self.t_end = t_end
        self.pixel = pixel
        self.path = [[x_init, y_init, z_init, t_init]]
        self.signal = [[] for j in range(int(read_ele_num))]
        self.end_condition = 0
        self.diffuse_end_condition = 0
        self.row=0
        self.column=0

        self.cal_mobility = Material(material).cal_mobility
        self.charge = charge
        if self.charge == 0:
            self.end_condition = "zero charge"

    def not_in_sensor(self,my_d):
        if (self.x<=0) or (self.x>=my_d.l_x)\
            or (self.y<=0) or (self.y>=my_d.l_y)\
            or (self.z<=0) or (self.z>=my_d.l_z):
            self.end_condition = "out of bound"
        return self.end_condition

    def drift_single_step(self, my_d, my_f, delta_t=delta_t):
        e_field = my_f.get_e_field(self.x,self.y,self.z)
        intensity = Vector(e_field[0],e_field[1],e_field[2]).get_length()
        mobility = Material(my_d.material)
        #mu = mobility.cal_mobility(my_d.temperature, my_d.doping_function(self.z+delta_z), self.charge, average_intensity)
        mu = mobility.cal_mobility(my_d.temperature, 1e12, self.charge, intensity)
        # TODO: rebuild the doping function or admit this as an approximation
        velocity_vector = [e_field[0]*mu, e_field[1]*mu, e_field[2]*mu] # cm/s

        if(intensity > min_intensity):
            #project steplength on the direction of electric field
            if(self.charge>0):
                delta_x = velocity_vector[0]*delta_t*1e4 # um
                delta_y = velocity_vector[1]*delta_t*1e4
                delta_z = velocity_vector[2]*delta_t*1e4
            else:
                delta_x = -velocity_vector[0]*delta_t*1e4
                delta_y = -velocity_vector[1]*delta_t*1e4
                delta_z = -velocity_vector[2]*delta_t*1e4
        else:
            self.end_condition = "zero velocity"
            return

        # get diffution from mobility and temperature
        kboltz=8.617385e-5 #eV/K
        diffusion = (2.0*kboltz*mu*my_d.temperature*delta_t)**0.5
        #diffusion = 0.0
        dif_x=random.gauss(0.0,diffusion)*1e4
        dif_y=random.gauss(0.0,diffusion)*1e4
        dif_z=random.gauss(0.0,diffusion)*1e4

        # sum up
        # x axis   
        if((self.x+delta_x+dif_x)>=my_d.l_x): 
            self.x = my_d.l_x
        elif((self.x+delta_x+dif_x)<0):
            self.x = 0
        else:
            self.x = self.x+delta_x+dif_x
        # y axis
        if((self.y+delta_y+dif_y)>=my_d.l_y): 
            self.y = my_d.l_y
        elif((self.y+delta_y+dif_y)<0):
            self.y = 0
        else:
            self.y = self.y+delta_y+dif_y
        # z axis
        if((self.z+delta_z+dif_z)>=my_d.l_z): 
            self.z = my_d.l_z
        elif((self.z+delta_z+dif_z)<0):
            self.z = 0
        else:
            self.z = self.z+delta_z+dif_z
        #time
        self.t = self.t+delta_t
        #record
        self.path.append([self.x,self.y,self.z,self.t]) 

    def get_signal(self,my_f,my_d):
        """Calculate signal from carrier path"""
        # i = -q*v*nabla(U_w) = -q*dx*nabla(U_w)/dt = -q*dU_w(x)/dt
        # signal = i*dt = -q*dU_w(x)
        for j in range(my_f.read_ele_num):
            charge=self.charge
            for i in range(len(self.path)-1): # differentiate of weighting potential
                U_w_1 = my_f.get_w_p(self.path[i][0],self.path[i][1],self.path[i][2],j) # x,y,z
                U_w_2 = my_f.get_w_p(self.path[i+1][0],self.path[i+1][1],self.path[i+1][2],j)
                e0 = 1.60217733e-19
                if i>0:
                    if (my_f.read_ele_num)>1:
                        d_t=self.path[i][3]-self.path[i-1][3]
                        if self.charge>=0:
                            self.trapping_rate=my_f.get_trap_h(self.path[i][0],self.path[i][1],self.path[i][2])
                        else:
                            self.trapping_rate=my_f.get_trap_e(self.path[i][0],self.path[i][1],self.path[i][2])
                        charge=charge*np.exp(-d_t*self.trapping_rate)
                q = charge * e0
                dU_w = U_w_2 - U_w_1
                self.signal[j].append(q*dU_w)
        

    def drift_end(self,my_f):
        e_field = my_f.get_e_field(self.x,self.y,self.z)
        if (e_field[0]==0 and e_field[1]==0 and e_field[2] == 0):
            self.end_condition = "out of bound"
        elif (self.t > t_end):
            self.end_condition = "time out"
        return self.end_condition

    def diffuse_single_step(self,my_d,my_f):
        delta_t=t_bin
        #e_field = my_f.get_e_field(self.x,self.y,self.z)
        intensity = 0

        kboltz=8.617385e-5 #eV/K
        mobility = Material(my_d.material)
        mu = mobility.cal_mobility(my_d.temperature, my_d.doping_function(self.z), self.charge, intensity)
        diffusion = (2.0*kboltz*mu*my_d.temperature*delta_t)**0.5
        #diffusion = 0.0
        dif_x=random.gauss(0.0,diffusion)*1e4
        dif_y=random.gauss(0.0,diffusion)*1e4
        dif_z=0

        if((self.x+dif_x)>=my_d.l_x): 
            self.x = my_d.l_x
        elif((self.x+dif_x)<0):
            self.x = 0
        else:
            self.x = self.x+dif_x
        # y axis
        if((self.y+dif_y)>=my_d.l_y): 
            self.y = my_d.l_y
        elif((self.y+dif_y)<0):
            self.y = 0
        else:
            self.y = self.y+dif_y
        # z axis
        if((self.z+dif_z)>=my_d.l_z): 
            self.z = my_d.l_z
        elif((self.z+dif_z)<0):
            self.z = 0
        else:
            self.z = self.z+dif_z
        #time
        self.t = self.t+delta_t
        #record
        self.path.append([self.x,self.y,self.z,self.t])

    def diffuse_end(self,my_f):
        if (self.z<=0):
        #    self.end_condition = "out of bound"
            self.diffuse_end_condition = "collect"
        return self.diffuse_end_condition

    def diffuse_not_in_sensor(self,my_d):
        if (self.x<=0) or (self.x>=my_d.l_x)\
            or (self.y<=0) or (self.y>=my_d.l_y)\
            or (self.z>=my_d.l_z):
            self.diffuse_end_condition = "out of bound"
        mod_x = self.x % self.pixel
        mod_y = self.y % self.pixel
        if ((mod_x> 7.5) & (mod_x<17.5)) & ((mod_y> 7.5) & (mod_y<17.5)) \
           & (self.t <= self.t_end):
            self.diffuse_end_condition = "collect"
        return self.diffuse_end_condition

        '''
        if (self.z<= 0) or (self.t >= self.t_end):
            self.diffuse_end_condition = "collect"
        #print("diffuse end")
        return self.diffuse_end_condition
        '''

    def pixel_position(self,my_f,my_d):
        if self.diffuse_end_condition == "collect":
            self.row = self.x // self.pixel
            self.column = self.y // self.pixel
        else:
            self.row = -1
            self.column = -1
        return  self.row,self.column,abs(self.charge)

        

class CalCurrent:
    """
    Description:
        Calculate sum of the generated current by carriers drifting
    Parameters:
        my_d : R3dDetector
        my_f : FenicsCal 
        ionized_pairs : float[]
            the generated carrier amount from MIP or laser
        track_position : float[]
            position of the generated carriers
    Attributes:
        electrons, holes : Carrier[]
            the generated carriers, able to calculate their movement
    Modify:
        2022/10/28
    """
    def __init__(self, my_d, my_f, ionized_pairs, track_position):
        self.electrons = []
        self.holes = []
        for i in range(len(track_position)):
            electron = Carrier(track_position[i][0],\
                               track_position[i][1],\
                               track_position[i][2],\
                               track_position[i][3],\
                               -1*ionized_pairs[i],\
                               my_d.material,\
                               my_f.read_ele_num)
            hole = Carrier(track_position[i][0],\
                           track_position[i][1],\
                           track_position[i][2],
                           track_position[i][3],\
                           ionized_pairs[i],\
                           my_d.material,\
                           my_f.read_ele_num)
            if not electron.not_in_sensor(my_d):
                self.electrons.append(electron)
                self.holes.append(hole)
        
        self.drifting_loop(my_d, my_f)

        self.t_bin = t_bin
        self.t_end = t_end
        self.t_start = t_start
        self.n_bin = int((self.t_end-self.t_start)/self.t_bin)

        self.current_define(my_f.read_ele_num)
        for i in range(my_f.read_ele_num):
            self.sum_cu[i].Reset()
            self.positive_cu[i].Reset()
            self.negative_cu[i].Reset()
        self.get_current(my_d,my_f.read_ele_num)
        if "lgad3D" in my_d.det_model:
            self.gain_current = CalCurrentGain(my_d, my_f, self)
            for i in range(my_f.read_ele_num):
                self.gain_positive_cu[i].Reset()
                self.gain_negative_cu[i].Reset()
            self.get_current_gain(my_f.read_ele_num)

    def drifting_loop(self, my_d, my_f):
        for electron in self.electrons:
            while not electron.not_in_sensor(my_d) and not electron.drift_end(my_f):
                electron.drift_single_step(my_d, my_f)
            electron.get_signal(my_f,my_d)
        for hole in self.holes:
            while not hole.not_in_sensor(my_d) and not hole.drift_end(my_f):
                hole.drift_single_step(my_d, my_f)
            hole.get_signal(my_f,my_d)

    def current_define(self,read_ele_num):
        """
        @description: 
            Parameter current setting     
        @param:
            positive_cu -- Current from holes move
            negative_cu -- Current from electrons move
            sum_cu -- Current from e-h move
        @Returns:
            None
        @Modify:
            2021/08/31
        """
        self.positive_cu=[]
        self.negative_cu=[]
        self.gain_positive_cu=[]
        self.gain_negative_cu=[]
        self.sum_cu=[]

        for i in range(read_ele_num):
            self.positive_cu.append(ROOT.TH1F("charge+"+str(i+1), " No."+str(i+1)+"Positive Current",
                                        self.n_bin, self.t_start, self.t_end))
            self.negative_cu.append(ROOT.TH1F("charge-"+str(i+1), " No."+str(i+1)+"Negative Current",
                                        self.n_bin, self.t_start, self.t_end))
            self.gain_positive_cu.append(ROOT.TH1F("gain_charge+"+str(i+1)," No."+str(i+1)+"Gain Positive Current",
                                        self.n_bin, self.t_start, self.t_end))
            self.gain_negative_cu.append(ROOT.TH1F("gain_charge-"+str(i+1)," No."+str(i+1)+"Gain Negative Current",
                                        self.n_bin, self.t_start, self.t_end))
            self.sum_cu.append(ROOT.TH1F("charge"+str(i+1),"Total Current"+" No."+str(i+1)+"electrode",
                                    self.n_bin, self.t_start, self.t_end))
            
        
    def get_current(self,my_d,read_ele_num):
        test_p = ROOT.TH1F("test+","test+",self.n_bin,self.t_start,self.t_end)
        test_p.Reset()
        for j in range(read_ele_num):
            sum_max_hole=0
            sum_min_hole=0
            for hole in self.holes:
                if (len(hole.signal[j])!=0):
                    sum_max_hole=sum_max_hole+max(hole.signal[j])/self.t_bin
                    sum_min_hole=sum_min_hole+min(hole.signal[j])/self.t_bin
            if(sum_max_hole<1e-11 or abs(sum_min_hole)<1e-11) and (my_d.det_model == "Si_Strip"):
                pass
            else:
                for hole in self.holes:
                    for i in range(len(hole.path)-1):
                        test_p.Fill(hole.path[i][3],hole.signal[j][i]/self.t_bin)# time,current=int(i*dt)/Δt
                    self.positive_cu[j].Add(test_p)
                    test_p.Reset()


        test_n = ROOT.TH1F("test-","test-",self.n_bin,self.t_start,self.t_end)
        test_n.Reset()
        for j in range(read_ele_num):
            sum_max_electron=0
            sum_min_electron=0
            for electron in self.electrons:
                if (len(electron.signal[j])!=0):
                    sum_max_electron=sum_max_electron+max(electron.signal[j])/self.t_bin
                    sum_min_electron=sum_min_electron+min(electron.signal[j])/self.t_bin
            if(sum_max_hole<1e-11 or abs(sum_min_hole)<1e-11) and (my_d.det_model == "Si_Strip"):
                pass
            else:
                for electron in self.electrons:             
                    for i in range(len(electron.path)-1):
                        test_n.Fill(electron.path[i][3],electron.signal[j][i]/self.t_bin)# time,current=int(i*dt)/Δt
                    self.negative_cu[j].Add(test_n)
                    test_n.Reset()
    
        for i in range(read_ele_num):
            self.sum_cu[i].Add(self.positive_cu[i])
            self.sum_cu[i].Add(self.negative_cu[i])

    def get_current_gain(self,read_ele_num):
        for i in range(read_ele_num):
            self.gain_negative_cu[i] = self.gain_current.negative_cu[i]
            self.gain_positive_cu[i] = self.gain_current.positive_cu[i]
        for i in range(read_ele_num):
            self.sum_cu[i].Add(self.gain_negative_cu[i])
            self.sum_cu[i].Add(self.gain_positive_cu[i])
    
class CalCurrentGain(CalCurrent):
    '''Calculation of gain carriers and gain current, simplified version'''
    def __init__(self, my_d, my_f, my_current):
        self.electrons = [] # gain carriers
        self.holes = []
        cal_coefficient = Material(my_d.material).cal_coefficient
        gain_rate = self.gain_rate(my_d,my_f,cal_coefficient)
        print("gain_rate="+str(gain_rate))
        # assuming gain layer at d>0
        if my_d.voltage<0 : # p layer at d=0, holes multiplicated into electrons
            for hole in my_current.holes:
                self.electrons.append(Carrier(hole.path[-1][0],\
                                              hole.path[-1][1],\
                                              my_d.avalanche_bond,\
                                              hole.path[-1][3],\
                                              -1*hole.charge*gain_rate,\
                                              my_d.material,\
                                              my_f.read_ele_num))
                
                self.holes.append(Carrier(hole.path[-1][0],\
                                          hole.path[-1][1],\
                                          my_d.avalanche_bond,\
                                          hole.path[-1][3],\
                                          hole.charge*gain_rate,\
                                          my_d.material,\
                                          my_f.read_ele_num))

        else : # n layer at d=0, electrons multiplicated into holes
            for electron in my_current.electrons:
                self.holes.append(Carrier(electron.path[-1][0],\
                                          electron.path[-1][1],\
                                          my_d.avalanche_bond,\
                                          electron.path[-1][3],\
                                          -1*electron.charge*gain_rate,\
                                          my_d.material,\
                                          my_f.read_ele_num))

                self.electrons.append(Carrier(electron.path[-1][0],\
                                                electron.path[-1][1],\
                                                my_d.avalanche_bond,\
                                                electron.path[-1][3],\
                                                electron.charge*gain_rate,\
                                                my_d.material,\
                                                my_f.read_ele_num))

        self.drifting_loop(my_d, my_f)

        self.t_bin = t_bin
        self.t_end = t_end
        self.t_start = t_start
        self.n_bin = int((self.t_end-self.t_start)/self.t_bin)

        self.current_define(my_f.read_ele_num)
        for i in range(my_f.read_ele_num):
            self.positive_cu[i].Reset()
            self.negative_cu[i].Reset()
        self.get_current(my_d,my_f.read_ele_num)

    def gain_rate(self, my_d, my_f, cal_coefficient):

        # gain = exp[K(d_gain)] / {1-int[alpha_minor * K(x) dx]}
        # K(x) = exp{int[(alpha_major - alpha_minor) dx]}

        n = 1001
        z_list = np.linspace(0, my_d.avalanche_bond * 1e-4, n) # in cm
        alpha_n_list = np.zeros(n)
        alpha_p_list = np.zeros(n)
        for i in range(n):
            Ex,Ey,Ez = my_f.get_e_field(0.5*my_d.l_x,0.5*my_d.l_y,z_list[i] * 1e4) # in V/cm
            E_field = Vector(Ex,Ey,Ez).get_length()
            alpha_n = cal_coefficient(E_field, -1, my_d.temperature)
            alpha_p = cal_coefficient(E_field, +1, my_d.temperature)
            alpha_n_list[i] = alpha_n
            alpha_p_list[i] = alpha_p

        if my_d.voltage>0:
            alpha_major_list = alpha_n_list # multiplication contributed mainly by electrons in Si
            alpha_minor_list = alpha_p_list
        elif my_d.voltage<0:
            alpha_major_list = alpha_p_list # multiplication contributed mainly by holes in SiC
            alpha_minor_list = alpha_n_list
        diff_list = alpha_major_list - alpha_minor_list
        int_alpha_list = np.zeros(n-1)

        for i in range(1,n):
            int_alpha = 0
            for j in range(i):
                int_alpha += (diff_list[j] + diff_list[j+1]) * (z_list[j+1] - z_list[j]) /2
            int_alpha_list[i-1] = int_alpha
        exp_list = np.exp(int_alpha_list)

        det = 0 # determinant of breakdown
        for i in range(0,n-1):
            average_alpha_minor = (alpha_minor_list[i] + alpha_minor_list[i+1])/2
            det_derivative = average_alpha_minor * exp_list[i]
            det += det_derivative*(z_list[i+1]-z_list[i])        
        if det>1:
            print("det="+str(det))
            print("The detector broke down")
            raise(ValueError)
        
        gain_rate = exp_list[n-2]/(1-det) -1
        return gain_rate

    def current_define(self,read_ele_num):
        """
        @description: 
            Parameter current setting     
        @param:
            positive_cu -- Current from holes move
            negative_cu -- Current from electrons move
            sum_cu -- Current from e-h move
        @Returns:
            None
        @Modify:
            2021/08/31
        """
        self.positive_cu=[]
        self.negative_cu=[]

        for i in range(read_ele_num):
            self.positive_cu.append(ROOT.TH1F("gain_charge_tmp+"+str(i+1)," No."+str(i+1)+"Gain Positive Current",
                                        self.n_bin, self.t_start, self.t_end))
            self.negative_cu.append(ROOT.TH1F("gain_charge_tmp-"+str(i+1)," No."+str(i+1)+"Gain Positive Current",
                                        self.n_bin, self.t_start, self.t_end))
        
    def get_current(self,my_d,read_ele_num):
        test_p = ROOT.TH1F("test+","test+",self.n_bin,self.t_start,self.t_end)
        test_p.Reset()
        for j in range(read_ele_num):
            sum_max_hole=0
            sum_min_hole=0
            for hole in self.holes:
                if (len(hole.signal[j])!=0):
                    sum_max_hole=sum_max_hole+max(hole.signal[j])/self.t_bin
                    sum_min_hole=sum_min_hole+min(hole.signal[j])/self.t_bin
            if(sum_max_hole<1e-11 or abs(sum_min_hole)<1e-11) and (my_d.det_model == "Si_Strip"):
                pass
            else:
                for hole in self.holes:
                    for i in range(len(hole.path)-1):
                        test_p.Fill(hole.path[i][3],hole.signal[j][i]/self.t_bin)# time,current=int(i*dt)/Δt
                    self.positive_cu[j].Add(test_p)
                    test_p.Reset()

        test_n = ROOT.TH1F("test-","test-",self.n_bin,self.t_start,self.t_end)
        test_n.Reset()
        for j in range(read_ele_num):
            sum_max_electron=0
            sum_min_electron=0
            for electron in self.electrons:
                if (len(electron.signal[j])!=0):
                    sum_max_electron=sum_max_electron+max(electron.signal[j])/self.t_bin
                    sum_min_electron=sum_min_electron+min(electron.signal[j])/self.t_bin
            if(sum_max_hole<1e-11 or abs(sum_min_hole)<1e-11) and (my_d.det_model == "Si_Strip"):
                pass
            else:
                for electron in self.electrons:             
                    for i in range(len(electron.path)-1):
                        test_n.Fill(electron.path[i][3],electron.signal[j][i]/self.t_bin)# time,current=int(i*dt)/Δt
                    self.negative_cu[j].Add(test_n)
                    test_n.Reset()

class CalCurrentG4P(CalCurrent):
    def __init__(self, my_d, my_f, my_g4p, batch):
        G4P_carrier_list = CarrierListFromG4P(my_d.material, my_g4p, batch)
        self.read_ele_num = my_f.read_ele_num
        super().__init__(my_d, my_f, G4P_carrier_list.ionized_pairs, G4P_carrier_list.track_position)

class CalCurrentStrip(CalCurrent):
    def __init__(self, my_d, my_f, my_g4p, batch):
        G4P_carrier_list = StripCarrierListFromG4P(my_d.material, my_g4p, batch)
        self.read_ele_num = my_f.read_ele_num
        super().__init__(my_d, my_f, G4P_carrier_list.ionized_pairs, G4P_carrier_list.track_position)


class CalCurrentPixel:
    """Calculation of diffusion electrons in pixel detector"""
    def __init__(self, my_d, my_f, my_g4p):
        batch = len(my_g4p.localposition)
        layer = len(my_d.lt_z)
        G4P_carrier_list = PixelCarrierListFromG4P(my_d, my_g4p)                 
        self.collected_charge=[] #temp paras don't save as self.
        self.sum_signal = []
        self.event = []        
        for k in range(batch):
            l_dict = {}
            signal_charge = []
            for j in range(layer):
                self.electrons = []
                self.charge,self.collected_charge = [],[]#same like before
                self.row,self.column=[],[]
                Hit = {'index':[],'charge':[]} 
                #print(len(G4P_carrier_list.ionized_pairs[k][j]))
                print("%f pairs of carriers are generated from G4 in event_ %d layer %d" %(sum(G4P_carrier_list.ionized_pairs[k][j]),k,j))
                #print(G4P_carrier_list.track_position[k][j])
                for i in range(len(G4P_carrier_list.track_position[k][j])):
                    electron = Carrier(G4P_carrier_list.track_position[k][j][i][0],\
                                       G4P_carrier_list.track_position[k][j][i][1],\
                                       G4P_carrier_list.track_position[k][j][i][2],\
                                       0,\
                                       -1*G4P_carrier_list.ionized_pairs[k][j][i],\
                                       my_d.material,\
                                       1)
                    if not electron.not_in_sensor(my_d):
                        self.electrons.append(electron)
                self.diffuse_loop(my_d,my_f)

                Xbins=int(my_d.l_x // electron.pixel)
                Ybins=int(my_d.l_y // electron.pixel)
                Xup=my_d.l_x // electron.pixel
                Yup=my_d.l_y // electron.pixel
                test_charge = ROOT.TH2F("charge", "charge",Xbins, 0, Xup, Ybins, 0, Yup)
                for i in range(len(self.row)):
                    #test_charge.SetBinContent(int(self.row[i]),int(self.column[i]),self.charge[i])
                    test_charge.Fill(self.row[i],self.column[i],self.charge[i])
                    
                sum_fired = ROOT.TH2F("charge", "Pixel Detector charge",Xbins, 0, Xup, Ybins, 0, Yup)
                sum_fired.Add(test_charge)
                
                self.sum_charge = ROOT.TH2F("charge", "Pixel Detector charge",Xbins, 0, Xup, Ybins, 0, Yup)
                self.sum_charge.Add(test_charge)
                
                test_charge.Reset
                collected_charge=self.pixel_charge(my_d,Xbins,Ybins)
                signal_charge.append(collected_charge)
                
                Hit["index"],Hit["charge"] = self.pixel_fired(sum_fired,Xbins,Ybins)
                l_dict[j] = Hit
                print("%f electrons are collected in event_ %d,layer %d" %(sum(self.charge),k,j))
            self.sum_signal.append(signal_charge)
            self.event.append(l_dict)
            #print(signal_charge)
            del signal_charge
        #print(self.sum_signal)
        #print(self.event)

    def diffuse_loop(self, my_d, my_f):
        for electron in self.electrons:
            while not electron.diffuse_not_in_sensor(my_d):
                electron.diffuse_single_step(my_d, my_f)
                electron.diffuse_end(my_f)
            x,y,charge_quantity = electron.pixel_position(my_f,my_d)
            if (x != -1)&(y != -1): 
                self.row.append(x)
                self.column.append(y)
                self.charge.append(charge_quantity)

    def pixel_charge(self,my_d,Xbins,Ybins):
        for x in range(Xbins):
            for y in range(Ybins):
                charge =self.sum_charge.GetBinContent(x,y)
                if (charge>0.2):
                    self.collected_charge.append([x,y,charge])        
        return self.collected_charge
    
    def pixel_fired(self,tot,Xbins,Ybins):
        Hit = {'index':[],'charge':[]} 
        for x in range(Xbins):
            for y in range(Ybins):
                charge =tot.GetBinContent(x,y)
                if (charge>0.2):
                    Hit["index"].append([x,y])
                    Hit["charge"].append(charge)       
        return Hit["index"],Hit["charge"]


class CalCurrentLaser(CalCurrent):
    def __init__(self, my_d, my_f, my_l):
        super().__init__(my_d, my_f, my_l.ionized_pairs, my_l.track_position)
        self.read_ele_num = my_f.read_ele_num
        
        for i in range(self.read_ele_num):
            
            # convolute the signal with the laser pulse shape in time
            convolved_positive_cu = ROOT.TH1F("convolved_charge+", "Positive Current",
                                        self.n_bin, self.t_start, self.t_end)
            convolved_negative_cu = ROOT.TH1F("convolved_charge-", "Negative Current",
                                        self.n_bin, self.t_start, self.t_end)
            convolved_gain_positive_cu = ROOT.TH1F("convolved_gain_charge+","Gain Positive Current",
                                        self.n_bin, self.t_start, self.t_end)
            convolved_gain_negative_cu = ROOT.TH1F("convolved_gain_charge-","Gain Negative Current",
                                        self.n_bin, self.t_start, self.t_end)
            convolved_sum_cu = ROOT.TH1F("convolved_charge","Total Current",
                                    self.n_bin, self.t_start, self.t_end)
            
            convolved_positive_cu.Reset()
            convolved_negative_cu.Reset()
            convolved_gain_positive_cu.Reset()
            convolved_gain_negative_cu.Reset()
            convolved_sum_cu.Reset()

            self.signalConvolution(self.positive_cu[i],my_l.timePulse,convolved_positive_cu)
            self.signalConvolution(self.negative_cu[i],my_l.timePulse,convolved_negative_cu)
            self.signalConvolution(self.gain_positive_cu[i],my_l.timePulse,convolved_gain_positive_cu)
            self.signalConvolution(self.gain_negative_cu[i],my_l.timePulse,convolved_gain_negative_cu)
            self.signalConvolution(self.sum_cu[i],my_l.timePulse,convolved_sum_cu)

            self.positive_cu[i] = convolved_positive_cu
            self.negative_cu[i] = convolved_negative_cu
            self.gain_positive_cu[i] = convolved_gain_positive_cu
            self.gain_negative_cu[i] = convolved_gain_negative_cu
            self.sum_cu[i] = convolved_sum_cu

    def signalConvolution(self,cu,timePulse,convolved_cu):
        for i in range(self.n_bin):
            pulse_responce = cu.GetBinContent(i)
            for j in range(-i,self.n_bin-i): 
                time_pulse = timePulse(j*self.t_bin)
                convolved_cu.Fill((i+j)*self.t_bin - 1e-14, pulse_responce*time_pulse*self.t_bin)
                #resolve float error

class CarrierListFromG4P:
    def __init__(self, material, my_g4p, batch):
        """
        Description:
            Events position and energy depositon
        Parameters:
            material : string
                deciding the energy loss of MIP
            my_g4p : Particles
            batch : int
                batch = 0: Single event, select particle with long enough track
                batch != 0: Multi event, assign particle with batch number
        Modify:
            2022/10/25
        """
        if (material == "SiC"):
            self.energy_loss = 8.4 #ev
        elif (material == "Si"):
            self.energy_loss = 3.6 #ev

        if batch == 0:
            total_step=0
            particle_number=0
            for p_step in my_g4p.p_steps_current:   # selecting particle with long enough track
                if len(p_step)>1:
                    particle_number=1+particle_number
                    total_step=len(p_step)+total_step
            for j in range(len(my_g4p.p_steps_current)):
                if(len(my_g4p.p_steps_current[j])>((total_step/particle_number)*0.5)):
                    self.batch_def(my_g4p,j)
                    break
            if particle_number > 0:
                batch=1

            if batch == 0:
                print("the sensor didn't have particles hitted")
                raise ValueError
        else:
            self.batch_def(my_g4p,batch)

    def batch_def(self,my_g4p,j):
        self.beam_number = j
        self.track_position = [[single_step[0],single_step[1],single_step[2],1e-9] for single_step in my_g4p.p_steps_current[j]]
        self.tracks_step = my_g4p.energy_steps[j]
        self.tracks_t_energy_deposition = my_g4p.edep_devices[j] #为什么不使用？
        self.ionized_pairs = [step*1e6/self.energy_loss for step in self.tracks_step]
    
class PixelCarrierListFromG4P:
    def __init__(self, my_d,my_g4p):
        """
        Description:
            Events position and energy depositon
        Parameters:
            material : string
                deciding the energy loss of MIP
            my_g4p : Particles
            batch : int
                batch = 0: Single event, select particle with long enough track
                batch != 0: Multi event, assign particle with batch number
        Modify:
            2022/10/25
        """
        batch = len(my_g4p.localposition)
        layer = len(my_d.lt_z)
        material = my_d.material
        self.pixelsize_x = my_d.p_x
        self.pixelsize_y = my_d.p_y
        self.pixelsize_z = my_d.p_z
        
        if (material == "SiC"):
            self.energy_loss = 8.4 #ev
        elif (material == "Si"):
            self.energy_loss = 3.6 #ev
        
        self.track_position, self.ionized_pairs= [],[]
        self.layer= layer
        for j in range(batch):
            self.single_event(my_g4p,j)

    def single_event(self,my_g4p,j):
        s_track_position,s_energy= [],[]
        for i in range(self.layer):
            position = []
            energy = []
            name = "Layer_"+str(i)
            #print(name)
            for k in range(len(my_g4p.devicenames[j])):
                px,py,pz = self.split_name(my_g4p.devicenames[j][k])
                if name in my_g4p.devicenames[j][k]:
                    tp = [0 for i in range(3)]
                    tp[0] = my_g4p.localposition[j][k][0]+(px-0.5)*self.pixelsize_x
                    tp[1] = my_g4p.localposition[j][k][1]+(py-0.5)*self.pixelsize_y
                    tp[2] = my_g4p.localposition[j][k][2]+self.pixelsize_z/2
                    position.append(tp) 
                    energy.append(my_g4p.energy_steps[j][k])
            s_track_position.append(position)
            pairs = [step*1e6/self.energy_loss for step in energy]
            s_energy.append(pairs)
            del position,energy
        self.track_position.append(s_track_position)
        self.ionized_pairs.append(s_energy)
        
    def split_name(self,volume_name):
        parts = volume_name.split('_')
        return int(parts[1]),int(parts[2]),int(parts[4])


class StripCarrierListFromG4P:
    def __init__(self, material, my_g4p, batch):
        if (material == "SiC"):
            self.energy_loss = 8.4 #ev
        elif (material == "Si"):
            self.energy_loss = 3.6 #ev

        if batch == 0:
            h1 = ROOT.TH1F("Edep_device", "Energy deposition in Detector", 100, 0, max(my_g4p.edep_devices)*1.1)
            for i in range (len(my_g4p.edep_devices)):
                h1.Fill(my_g4p.edep_devices[i])
            max_event_bin=h1.GetMaximumBin()
            bin_wide=max(my_g4p.edep_devices)*1.1/100
            for j in range (len(my_g4p.edep_devices)):
                #compare to experimental data
                if (my_g4p.edep_devices[j]<0.084 and my_g4p.edep_devices[j]>0.083):
                    try_p=1
                    for single_step in my_g4p.p_steps_current[j]:
                        if abs(single_step[0]-my_g4p.p_steps_current[j][0][0])>5:
                            try_p=0
                    if try_p==1:
                        self.batch_def(my_g4p,j)
                        batch = 1
                        break

            if batch == 0:
                print("the sensor didn't have particles hitted")
                raise ValueError
        else:
            self.batch_def(my_g4p,batch)

    def batch_def(self,my_g4p,j):
        self.beam_number = j
        self.track_position = [[single_step[0],single_step[1],single_step[2],1e-9] for single_step in my_g4p.p_steps_current[j]]
        self.tracks_step = my_g4p.energy_steps[j]
        self.tracks_t_energy_deposition = my_g4p.edep_devices[j] #为什么不使用？
        self.ionized_pairs = [step*1e6/self.energy_loss for step in self.tracks_step]

# TODO: change this to a method of CalCurrent
def save_current(my_d,my_l,my_current,my_f,key):
    if "planar3D" in my_d.det_model or "planarRing" in my_d.det_model:
        path = os.path.join('output', 'pintct', my_d.det_name, )
    elif "lgad3D" in my_d.det_model:
        path = os.path.join('output', 'lgadtct', my_d.det_name, )
    create_path(path) 
    L = eval("my_l.{}".format(key))
    #L is defined by different keys
    time = array('d', [999.])
    current = array('d', [999.])
    fout = ROOT.TFile(os.path.join(path, "sim-TCT-current") + str(L) + ".root", "RECREATE")
    t_out = ROOT.TTree("tree", "signal")
    t_out.Branch("time", time, "time/D")
    for i in range(my_f.read_ele_num):
        t_out.Branch("current"+str(i), current, "current"+str(i)+"/D")
        for j in range(my_current.n_bin):
            current[0]=my_current.sum_cu[i].GetBinContent(j)
            time[0]=j*my_current.t_bin
            t_out.Fill()
        t_out.Write()
        fout.Close()