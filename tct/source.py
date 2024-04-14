import math
import ROOT
import numpy as np
from particle.geometry import R3dDetector

class TCTTracks():
    """
    Description:
        Transfer Carrier Distribution from Laser Coordinate System 
        to Detector Coordinate System
    Parameters:
    ---------
    my_d : R3dDetector
        the Detector
    laser : dict
        the Parameter List of Your Laser
    x_rel,y_rel,z_rel:
        the Normalized Coordinate for Laser Focus 
        in Detector Coordinate System
    @Modify:
    ---------
        2021/09/13
    """
    def __init__(self, my_d, laser):
        #technique used
        self.tech = laser["tech"]
        self.direction = laser["direction"]
        #material parameters to certain wavelength of the beam
        self.refractionIndex = laser["refractionIndex"]
        if self.tech == "SPA":
            self.alpha = laser["alpha"] # m^-1
        if self.tech == "TPA":
            self.beta_2 = laser["beta_2"]
        #laser parameters
        self.wavelength = laser["wavelength"]*1e-3 #um
        self.temporal_FWHM = laser["temporal_FWHM"]
        self.pulse_energy = laser["pulse_energy"]
        self.spacial_FWHM = laser["spacial_FWHM"]#um
        self.central_time = laser["central_time"]
        if "l_Reyleigh" not in laser:
            w_0 = self.spacial_FWHM / (2 * np.log(2))**0.5
            self.l_Rayleigh = np.pi*w_0**2*self.refractionIndex/self.wavelength
        else:
            self.l_Rayleigh = laser["l_Rayleigh"]#um
        #the size of the detector
        self.lx = my_d.l_x#um
        self.ly = my_d.l_y
        self.lz = my_d.l_z
        #relative and absolute position of the focus
        self.fx_rel = laser["fx_rel"]
        self.fy_rel = laser["fy_rel"]
        self.fz_rel = laser["fz_rel"]
        self.fx_abs = self.fx_rel * self.lx
        self.fy_abs = self.fy_rel * self.ly
        self.fz_abs = self.fz_rel * self.lz
        #accuracy parameters
        self.r_step = laser["r_step"]#um
        self.h_step = laser["h_step"]#um
      
        self.mesh_definition(my_d)

    def mesh_definition(self,my_d):
        self.r_char = self.spacial_FWHM / 2
        if self.tech == "SPA":
            self.h_char = max(my_d.l_x, my_d.l_y, my_d.l_z)
        elif self.tech == "TPA":
            self.h_char = self.l_Rayleigh
        else:
            raise NameError(self.tech)

        self.change_coordinate()
        x_min = max(0,self.fx_abs - 3 * self.x_char)
        x_max = min(my_d.l_x,self.fx_abs + 3 * self.x_char)
        y_min = max(0,self.fy_abs - 3 * self.y_char)
        y_max = min(my_d.l_y,self.fy_abs + 3 * self.y_char)
        z_min = max(0,self.fz_abs - 3 * self.z_char)
        z_max = min(my_d.l_z,self.fz_abs + 3 * self.z_char)

        self.x_left_most, self.x_right_most = self.window(x_min, x_max, 0, my_d.l_x)
        self.y_left_most, self.y_right_most = self.window(y_min, y_max, 0, my_d.l_y)
        self.z_left_most, self.z_right_most = self.window(z_min, z_max, 0, my_d.l_z)
        
        xArray = np.linspace(x_min, x_max, int((x_max - x_min) / self.x_step) + 1)
        yArray = np.linspace(y_min, y_max, int((y_max - y_min) / self.y_step) + 1)
        zArray = np.linspace(z_min, z_max, int((z_max - z_min) / self.z_step) + 1)

        xCenter = (xArray[:-1] + xArray[1:]) / 2
        yCenter = (yArray[:-1] + yArray[1:]) / 2
        zCenter = (zArray[:-1] + zArray[1:]) / 2

        xDiff = (xArray[1:] - xArray[:-1])
        yDiff = (yArray[1:] - yArray[:-1])
        zDiff = (zArray[1:] - zArray[:-1])

        YC, XC, ZC = np.meshgrid(yCenter, xCenter, zCenter) #Feature of numpy.meshgrid
        YD, XD, ZD = np.meshgrid(yDiff, xDiff, zDiff)
        self.projGrid = self._getCarrierDensity(XC, YC, ZC)\
            * XD * YD * ZD * 1e-18
        self.track_position = list(np.transpose(np.array([
            list(np.ravel(XC)),\
            list(np.ravel(YC)),\
            list(np.ravel(ZC)),\
            [self.central_time for x in np.ravel(XC)]])))
        self.ionized_pairs = list(np.ravel(self.projGrid))

        # seperate the carrier groups to simulate diffusion
        group_unit = 100 # the max number of carriers in one group
        cut = 0.1
        temp_position, temp_pairs = [],[]
        for position, pairs in zip(self.track_position, self.ionized_pairs):
            if pairs < cut:
                continue
            else:
                k = int(pairs//group_unit + 1) # divide the carrier pairs into k groups
                for i in range(k):
                    temp_position.append(position)
                    temp_pairs.append(pairs/k)

        self.track_position = temp_position
        self.ionized_pairs = temp_pairs

        print(len(self.ionized_pairs),"pairs of carrier models to drift")
        print(sum(self.ionized_pairs),"total pairs of carriers")

    def change_coordinate(self):
        #from cylindral coordinate (axis parallel with the beam, origin at focus)
        #to rectilinear coordinate inside the detector
        if self.direction in ("top","bottom"):
            self.z_step = self.h_step
            self.z_char = self.h_char
            self.x_step = self.y_step = self.r_step
            self.x_char = self.y_char = self.r_char
            if self.direction == "top":
                absorb_depth = self.lz * self.fz_rel
                def _getCarrierDensity(x, y, z):
                    return self.getCarrierDensity(z - self.fz_abs, absorb_depth, (x - self.fx_abs) ** 2 + (y - self.fy_abs) ** 2)
                self._getCarrierDensity = _getCarrierDensity
            if self.direction == "bottom":
                absorb_depth = self.lz * (1 - self.fz_rel)
                def _getCarrierDensity(x, y, z):
                    return self.getCarrierDensity(self.lz - z + self.fz_abs, absorb_depth, (x - self.fx_abs) ** 2 + (y - self.fy_abs) ** 2)
                self._getCarrierDensity = _getCarrierDensity

        elif self.direction == "edge":
            self.x_step = self.h_step
            self.x_char = self.h_char
            self.y_step = self.z_step = self.r_step
            self.y_char = self.z_char = self.r_char

            absorb_depth = self.lx * self.fx_rel
            def _getCarrierDensity(x, y, z):
                return self.getCarrierDensity(x - self.fx_abs, absorb_depth, (y - self.fy_abs) ** 2 + (z -self.fz_abs) ** 2)
            self._getCarrierDensity = _getCarrierDensity
        else:
            raise NameError(self.direction)

    def window(self,inner_min,inner_max,outer_min,outer_max):
        inner_length = inner_max - inner_min
        if outer_max - outer_min <= inner_length:
            return outer_min, outer_max # range shrunk
        else:
            if inner_min >= outer_min and inner_max <= outer_max:
                return inner_min, inner_max
            elif inner_min <= outer_min:
                return outer_min, outer_min + inner_length
            elif inner_max >= outer_max:
                return outer_max - inner_length, outer_max

    def getCarrierDensity(self, h, depth, r2):
        #return the carrier density of a given point in a given time period
        #referring to the vertical and horizontal distance from the focus 
        w_0 = self.spacial_FWHM / (2 * np.log(2))**0.5
        wSquared = (w_0 ** 2) * (1 + (h / self.l_Rayleigh) ** 2)
        intensity = ((self.pulse_energy))\
                    * (4 / (np.pi * wSquared * 1e-12))\
                    * np.exp((-2 * r2 / wSquared)) # time distribution decoupled
        
        h_Planck = 6.626*1e-34
        speedofLight = 2.998*1e8
        if self.tech == "SPA":
            # I = I_0 * exp(-αz)
            # dE_deposit = (αdz)dE_flux = (αdz)I*dSdt = (αI)*dVdt
            # dN_ehpair = dE_deposit / Energy_for_each_ionized_ehpair
            e0 = 1.60217733e-19
            return self.alpha * self.wavelength * 1e-6 * intensity * np.exp(-self.alpha * (h + depth) * 1e-6) / (h_Planck * speedofLight)
        elif self.tech == "TPA":
            return self.beta_2 * self.wavelength * 1e-6 * intensity ** 2 / (2 * h_Planck * speedofLight)
        
    def timePulse(self, t):
        # to reduce run time, convolute the time pulse function with the signal after the signal is calculated
        return np.exp(-4 * np.log(2) * t ** 2 / self.temporal_FWHM ** 2) / ((2*np.pi)**(1/2) * self.temporal_FWHM / (2 * (2*np.log(2))**(1/2)))
    

def draw_nocarrier3D(self,path):
    ROOT.gStyle.SetOptStat(0)
    c1 = ROOT.TCanvas("c1","canvas2",200,10,1000,1000)
    h = ROOT.TH3D("h","",\
        int((self.x_right_most - self.x_left_most) / self.x_step), self.x_left_most, self.x_right_most,\
        int((self.y_right_most - self.y_left_most) / self.y_step), self.y_left_most, self.y_right_most,\
        int((self.z_right_most - self.z_left_most) / self.z_step), self.z_left_most, self.z_right_most)
    for i in range(len(self.track_position)):
        h.Fill(self.track_position[i][0], self.track_position[i][1], self.track_position[i][2], self.ionized_pairs[i])
    h.Draw()
    h.GetXaxis().SetTitle("Depth [\mu m]")#[μm]
    h.GetXaxis().SetTitleSize(0.05)
    h.GetXaxis().SetLabelSize(0.05)
    h.GetYaxis().SetTitle("Width [\mu m]")
    h.GetYaxis().SetTitleSize(0.05)
    h.GetYaxis().SetLabelSize(0.05)
    h.GetZaxis().SetTitle("Thick [\mu m]")
    h.GetZaxis().SetTitleSize(0.05)
    h.GetZaxis().SetLabelSize(0.05)
    h.GetXaxis().SetTitleOffset(1.8)
    h.GetYaxis().SetTitleOffset(2.2)
    h.GetZaxis().SetTitleOffset(1.4)
    c1.SetLeftMargin(0.15)
    c1.SaveAs(path+"nocarrier_"\
        +str(round(self.fx_rel,5))+"_"\
        +str(round(self.fy_rel,5))+"_"\
        +str(round(self.fz_rel,5))+".pdf")  

def draw_nocarrier2D(self, path):
    ROOT.gStyle.SetOptStat(0)
    c1 = ROOT.TCanvas("c1","canvas2",200,10,1000,1000)
    h = ROOT.TH2D("h","",\
        int((self.x_right_most - self.x_left_most) / self.x_step), self.x_left_most, self.x_right_most,\
        int((self.z_right_most - self.z_left_most) / self.z_step), self.z_left_most, self.z_right_most)
    for i in range(len(self.track_position)):
        h.Fill(self.track_position[i][0], self.track_position[i][2], self.ionized_pairs[i])
    h.Draw("COLZ")
    h.GetXaxis().SetTitle("Depth [\mu m]")#[μm]
    h.GetXaxis().SetTitleSize(0.05)
    h.GetXaxis().SetLabelSize(0.05)
    h.GetYaxis().SetTitle("Thick [\mu m]")
    h.GetYaxis().SetTitleSize(0.05)
    h.GetYaxis().SetLabelSize(0.05)
    h.GetZaxis().SetLabelSize(0.05)
    c1.SetRightMargin(0.15)
    c1.SetLeftMargin(0.12)
    c1.SaveAs(path+"nocarrier2D_"\
        +str(round(self.fx_rel,5))+"_"\
        +str(round(self.fy_rel,5))+"_"\
        +str(round(self.fz_rel,5))+".pdf")  
