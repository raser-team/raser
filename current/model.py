#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
Description:  Define physical models for different materials   
@Date       : 2021/09/06 18:46:00
@Author     : yangtao
@version    : 1.0
'''

""" Define Material """

import math
import matplotlib.pyplot as plt
import os

class Material:

    def __init__(self,mat_name,mobility_model=None,avalanche_model=None):
        self.mat_name = mat_name
        self.mat_database()
        if mobility_model != None:
            self.mobility_model = mobility_model
        if avalanche_model != None:
            self.avalanche_model = avalanche_model

    def mat_database(self):
        m_e = 9.109e-31
        if self.mat_name == "Si":
            self.permittivity=11.5
            self.hole_mass = 0.386*m_e
            self.electron_mass = 0.26*m_e
            self.avalanche_model = "vanOverstraeten"
            self.mobility_model = 'Reggiani'
        if self.mat_name == "SiC":
            # 4H-SiC, use the longitudinal effective mass
            self.permittivity=9.76
            self.hole_mass = 1.0*m_e
            self.electron_mass = 0.29*m_e
            self.avalanche_model = 'Hatakeyama'
            self.mobility_model = 'Das'


    def cal_mobility(self, temperature, input_doping, charge, electric_field):
        """ Define Mobility Model """
        # L for lattice
        # I for impurity
        # F for driving force (saturation)
        # C for carrier (not included)
        # S for surface (not included)

        T = temperature # K
        t = T/300
        E = electric_field  # V/cm
        Neff = input_doping # cm^-3

        # SiC mobility
        if(self.mat_name == 'SiC'):
            if self.mobility_model == "Das":
                Neff = abs(Neff)
                if(charge>0):
                    mu_L_p = 124 * math.pow(t, -2)
                    mu_min_p = 15.9

                    C_ref_p = 1.76e19
                    alpha_p = 0.34
                    mu_LI_p = mu_min_p + mu_L_p/(1.0 + math.pow(Neff / C_ref_p, alpha_p)) 

                    beta_p = 1.213 * math.pow(t, 0.17)
                    v_sat_p = 2e7 * math.pow(t, 0.52) # saturate velocity
                    mu_LIF_p = mu_LI_p / (math.pow(1.0 + math.pow(mu_LI_p * E / v_sat_p, beta_p), 1.0 / beta_p))

                    mu = mu_LIF_p
                else:
                    mu_L_n = 947 * math.pow(t, -2) # L for lattice
                    mu_min_n = 0

                    C_ref_n = 1.94e19
                    alpha_n = 0.61
                    mu_LI_n = mu_min_n + mu_L_n/ (1 + math.pow(Neff / C_ref_n, alpha_n))

                    beta_n = 1 * math.pow(t, 0.66)
                    v_sat_n = 2e7 * math.pow(t, 0.87)
                    mu_LIF_n = mu_LI_n / (math.pow(1.0 + math.pow(mu_LI_n * E / v_sat_n, beta_n), 1.0/beta_n))

                    mu = mu_LIF_n

        # Si mobility
        if(self.mat_name == 'Si'):
            if self.mobility_model == "Selberherr":
                """Selberherr 1990"""
                Neff = abs(Neff)
                if(charge>0):
                    mu_L_p = 460.0 * math.pow(t, -2.18)
                    mu_min_p = 45.0*math.pow(t, -0.45)

                    alpha_p = 0.72*math.pow(t , 0.065)
                    C_ref_p = 2.23e17*math.pow(t, 3.2)
                    mu_LI_p = mu_min_p + (mu_L_p - mu_min_p)/(1.0 + math.pow(Neff / C_ref_p, alpha_p))

                    beta_p = 1.0
                    v_sat_p = 9.05e6 * math.sqrt(math.tanh(312.0/T))
                    #v_sat_p = 1.45e7 * math.sqrt(math.tanh(312.0/T))
                    mu_LIF_p = mu_LI_p / (1.0+ mu_LI_p * E / v_sat_p)

                    mu = mu_LIF_p

                else:
                    mu_L_n = 1430.0 * math.pow(t, -2.0)
                    mu_min_n = 80.0*math.pow(t, -0.45)

                    alpha_n = 0.72*math.pow(t, 0.065)
                    C_ref_n = 1.12e17*math.pow(t, 3.2)
                    mu_LI_n = mu_min_n + (mu_L_n-mu_min_n)/ (1.0 + math.pow(Neff / C_ref_n, alpha_n))

                    beta_n = 2
                    vsatn = 1.45e7 * math.sqrt(math.tanh(155.0/T))
                    mu_LIF_n = 2*mu_LI_n / (1.0+math.pow(1.0 + math.pow(2*mu_LI_n * E / vsatn, beta_n), 1.0/beta_n))

                    mu = mu_LIF_n
            
            if self.mobility_model == "Reggiani":
                """Reggiani 1999"""
                if Neff > 0:
                    N_D = Neff
                    N_A = 0
                if Neff < 0:
                    N_A = -Neff
                    N_D = 0

                if(charge>0):
                    mu_L_p = 470.50 * math.pow(t, -2.16)
                    mu_0_p_d = 90.0 * math.pow(t, -1.3)
                    mu_0_p_a = 44.0 * math.pow(t, -0.8)
                    mu_1_p_d = 28.2 * math.pow(t, -2.0)
                    mu_1_p_a = 28.2 * math.pow(t, -0.2)
                    mu_0_p = (mu_0_p_d * N_D + mu_0_p_a * N_A)/(N_D + N_A)
                    mu_1_p = (mu_1_p_d * N_D + mu_1_p_a * N_A)/(N_D + N_A)

                    alpha_p_d = 0.77
                    alpha_p_a = 0.719
                    C_r_p_d = 1.30e18 * math.pow(t, 2.2)
                    C_r_p_a = 2.45e17 * math.pow(t, 3.1)
                    C_s_p_d = 1.10e18 * math.pow(t, 6.2)
                    C_s_p_a = 6.10e20
                    mu_LI_p = mu_0_p\
                            +(mu_L_p - mu_0_p)/(1.0 + math.pow(N_D / C_r_p_d, alpha_p_d) + math.pow(N_A / C_r_p_a, alpha_p_a))\
                            - mu_1_p/(1.0 + math.pow(N_D/C_s_p_d + N_A / C_s_p_a, 2))

                    beta_p_1 = 2*math.pow(t, -0.2) + 0.6*math.pow(N_A, 2)/(math.pow(N_A, 2) + math.pow(8e17, 2)) + 0.6*math.pow(N_D, 2)/(math.pow(N_D, 2) + math.pow(1e19, 2))
                    beta_p_2 = 0.15*math.pow(t, 1) + 0.8*math.pow(N_A, 2)/(math.pow(N_A, 2) + math.pow(8e17, 2)) + 0.8*math.pow(N_D, 2)/(math.pow(N_D, 2) + math.pow(1e19, 2))
                    v_sat_p = 9.1e6 * math.pow(t, -0.4)
                    mu_LIF_p = mu_LI_p / math.pow((1.0+ math.pow(mu_LI_p * E / v_sat_p, beta_p_1+beta_p_2)), 1.0 / beta_p_1)

                    mu = mu_LIF_p

                else:
                    mu_L_n = 1441.0 * math.pow(t, -2.45 + 0.07*t)
                    mu_0_n_d = 62.2 * math.pow(t, -1.3)
                    mu_0_n_a = 132.0 * math.pow(t, -1.3)
                    mu_1_n_d = 48.6 * math.pow(t, -0.7)
                    mu_1_n_a = 73.5 * math.pow(t, -1.25)
                    mu_0_n = (mu_0_n_d * N_D + mu_0_n_a * N_A)/(N_D + N_A)
                    mu_1_n = (mu_1_n_d * N_D + mu_1_n_a * N_A)/(N_D + N_A)

                    alpha_n_d = 0.68
                    alpha_n_a = 0.72
                    C_r_n_d = 8.30e16 * math.pow(t, 3.65)
                    C_r_n_a = 1.22e17 * math.pow(t, 2.65)
                    C_s_n_d = 4e20
                    C_s_n_a = 7e20
                    mu_LI_n = mu_0_n\
                            +(mu_L_n - mu_0_n)/(1.0 + math.pow(N_D / C_r_n_d, alpha_n_d) + math.pow(N_A / C_r_n_a, alpha_n_a))\
                            - mu_1_n/(1.0 + math.pow(N_D/C_s_n_d + N_A / C_s_n_a, 2))

                    beta_n = 2.1*math.pow(t, -0.2) + 2*math.pow(N_A, 2)/(math.pow(N_A, 2) + math.pow(1e19, 2)) + 3*math.pow(N_D, 2)/(math.pow(N_D, 2) + math.pow(1e19, 2))
                    v_sat_n = 2.4e7 / (1 + 0.8*math.exp(t/2))
                    mu_LIF_n = mu_LI_n / math.pow((1.0+ math.pow(mu_LI_n * E / v_sat_n, beta_n)), 1.0 / beta_n)

                    mu = mu_LIF_n
        return mu
    
    def draw_velocity(self, temperature, Neff):
        x_field = []
        y_electron_mob = []
        y_hole_mob = []

        for i in range(1001):
            x_step = 1000
            x = i * x_step
            y_e = x*self.cal_mobility(temperature,Neff,-1,x)
            y_h = x*self.cal_mobility(temperature,Neff,+1,x)
            x_field.append(x)
            y_electron_mob.append(y_e)
            y_hole_mob.append(y_h)

        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.plot(x_field,y_electron_mob,label="electron")
        ax.plot(x_field,y_hole_mob,label="hole")
        ax.legend(loc='upper left')
        plt.xscale("log")
        plt.yscale("log")
        plt.xlabel("ElectricField  [V/cm]")
        plt.ylabel("Velocity [cm/s]")
        plt.title("Mobility Model")
        plt.grid(True,ls = '--',which="both")
        fig.show()
        fig.savefig("./output/model/"+self.mat_name+"Mobility"+self.mobility_model+".png")

    def cal_coefficient(self, electric_field, charges, temperature):
        """ Define Avalanche Model """

        coefficient = 0.

        E = electric_field # V/cm
        T = temperature # K

        # van Overstraeten – de Man Model
        if(self.avalanche_model == 'vanOverstraeten'):

            hbarOmega = 0.063 # eV
            E0 = 4.0e5 # V/cm
            T0 = 293.0 # K
            k_T0 = 0.0257 # eV

            # electron
            if( charges < 0 ): 

                a_low = 7.03e5 # cm-1
                a_high = 7.03e5 # cm-1

                b_low = 1.232e6 # cm-1
                b_high = 1.232e6 # cm-1

                #
                # For BandgapDependence parameters
                #

                # Glambda = 62e-8 #cm
                # beta_low = 0.678925 # 1
                # beta_high = 0.678925 # 1

            # hole
            if( charges > 0 ): 

                a_low = 1.582e6 # cm-1
                a_high = 6.71e5 # cm-1

                b_low = 2.036e6 # cm-1
                b_high = 1.693e6 # cm-1

                Glambda = 45e-8 #cm

                beta_low = 0.815009 # 1
                beta_high =  0.677706 # 1

            Ggamma = math.tanh(hbarOmega/(2*k_T0))/math.tanh(hbarOmega/(2*k_T0*T/T0))
            
            if(E>1.75e05):
                if(E>E0):
                    coefficient = Ggamma*a_high*math.exp(-(Ggamma*b_high)/E)
                else:
                    coefficient = Ggamma*a_low*math.exp(-(Ggamma*b_low)/E)
            else:
                coefficient = 0.

        if(self.avalanche_model == 'Okuto'):

            T0 = 300.0 # K
            _gamma = 1.0 # 1
            _delta = 2.0 # 1

            # electron
            if( charges < 0):
                a = 0.426 # V-1
                b = 4.81e5 # V/cm
                c = 3.05e-4 # K-1
                d = 6.86e-4 # K-1

                _lambda = 62.0e-8
                _beta = 0.265283

            # hole
            if( charges < 0):
                a = 0.243 # V-1
                b = 6.53e5 # V/cm
                c = 5.35e-4 # K-1
                d = 5.67e-4 # K-1

                _lambda = 45.0e-8 # cm
                _beta = 0.261395 # 1
            
            if(E>1.0e05):
                coefficient = a*(1+c*(T-T0))*pow(E,_gamma)*math.exp(-(b*(1+d*(T-T0)))/E)
            else:
                coefficient = 0.

        if(self.avalanche_model == 'Hatakeyama'):
            '''
            The Hatakeyama avalanche model describes the anisotropic behavior in 4H-SiC power devices. 
            The impact ionization coefficient is obtained according to the Chynoweth law.
            '''
            hbarOmega = 0.19 # eV
            _theta =1 # 1
            T0 = 300.0 # K
            k_T0 = 0.0257 # eV

            if( charges < 0):
                a_0001 = 1.76e8 # cm-1
                a_1120 = 2.10e7 # cm-1
                b_0001 = 3.30e7 # V/cm 
                b_1120 = 1.70e7 # V/cm
                 
            if (charges > 0):
                a_0001 = 3.41e8 # cm-1
                a_1120 = 2.96e7 # cm-1
                b_0001 = 2.50e7 # V/cm 
                b_1120 = 1.60e7 # V/cm 

            _gamma = math.tanh(hbarOmega/(2*k_T0))/math.tanh(hbarOmega/(2*k_T0*T/T0))

            # only consider the <0001> direction multiplication, no anisotropy now!
            a = a_0001
            b = b_0001
            
            if(E>1.0e04):
                coefficient = _gamma*a*math.exp(-(_gamma*b/E))
            else:
                coefficient = 0.
                
        return coefficient

class Vector:
    def __init__(self,a1,a2,a3):
        self.components = [a1,a2,a3]
        
    def cross(self,Vector_b):
        """ Get vector cross product of self and another Vector"""
        o1 = self.components[1]*Vector_b.components[2]-self.components[2]*Vector_b.components[1]
        o2 = self.components[2]*Vector_b.components[0]-self.components[0]*Vector_b.components[2]
        o3 = self.components[0]*Vector_b.components[1]-self.components[1]*Vector_b.components[0]
        return Vector(o1,o2,o3)

    def get_length(self):
        " Return length of self"
        return math.sqrt(self.components[0]*self.components[0]+self.components[1]*self.components[1]+self.components[2]*self.components[2])

    def add(self,Vector_b):
        " Return the sum of two Vectors. eg: [1,2,3]+[1,2,3] = [2,4,6]"
        o1 = self.components[0]+Vector_b.components[0]
        o2 = self.components[1]+Vector_b.components[1]
        o3 = self.components[2]+Vector_b.components[2]
        return Vector(o1,o2,o3)

    def sub(self,Vector_b):
        " Return the subtraction of two Vectors. eg: [1,2,3]-[1,2,3] = [0,0,0]"
        o1 = self.components[0]-Vector_b.components[0]
        o2 = self.components[1]-Vector_b.components[1]
        o3 = self.components[2]-Vector_b.components[2]
        return Vector(o1,o2,o3)
    
    def mul(self,k):
        " Return Vector multiplied by number. eg: 2 * [1,2,3] = [2,4,6]"
        return Vector(self.components[0]*k,self.components[1]*k,self.components[2]*k)

def main():
    if not (os.path.exists("./output/model")):
        os.makedirs("./output/model")
    mob = Material("Si")
    mob.draw_velocity(300,5e12)
    mob = Material("SiC")
    mob.draw_velocity(300,5e13)

if __name__ == "__main__":
    main()
