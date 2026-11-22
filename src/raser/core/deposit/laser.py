'''
Description:  laser.py
@Date       : 2023
@Author     : Yu Zhao, Chenxi Fu
@version    : 2.0
'''

import math

import ROOT
ROOT.gROOT.SetBatch(True)
import numpy as np

from raser.core.device.build_device import Detector
from raser.core.deposit.deposits import Deposits
from raser.core.deposit.deposits import EventDeposits
from raser.core.deposit.ionization import PAIR_ENERGY_EV
from raser.supports.paths import optional_component_path


# P. Grivickas et al., J. Appl. Phys. 101 (2007) 123521, Table I (E perp c) and Eq. (5); the 1/ħω of their Eq. (3) is left out, which matches their Fig. 4
SIC_PHONON_ENERGIES_EV = (0.0324, 0.0457, 0.0508, 0.0678, 0.0763, 0.0958, 0.1062)
SIC_PHONON_STRENGTHS = (0.5, 4.0, 7.0, 3.5, 23.0, 23.0, 40.5)  # eV^-1/2 cm^-1
SIC_EXCITON_RATIO = 60.0  # eV^-3/2, continuum to exciton ground state
SIC_EXCITON_BINDING_EV = 0.020
SIC_GAP_0K_EV = 3.267
SIC_GAP_SLOPE_EV_PER_K = 3e-4
SIC_GAP_THETA_K = 450.0
SIC_GAP_EXPONENT = 2.9
SIC_HIGHEST_PHOTON_EV = 3.8

PLANCK_J_S = 6.62607015e-34
LIGHT_SPEED_M_S = 2.99792458e8
ELEMENTARY_CHARGE_C = 1.602176634e-19
BOLTZMANN_EV_PER_K = 8.617333262e-5


def sic_absorption(wavelength: float, temperature: float) -> float:
    """Band-to-band absorption coefficient [1/m] of 4H-SiC for light of this
    wavelength [um] at this temperature [K]: phonon-assisted indirect
    transitions into the continuum and into the exciton, each phonon emitted
    or absorbed, Eqs. (7a) and (7b) of the deposit page."""
    photon = PLANCK_J_S * LIGHT_SPEED_M_S / (ELEMENTARY_CHARGE_C * wavelength * 1e-6)  # eV
    if photon > SIC_HIGHEST_PHOTON_EV:
        raise ValueError(
            f"the 4H-SiC absorption model reaches 3.8 eV (326 nm), the laser has "
            f"{wavelength * 1e3:.0f} nm: give alpha [1/m] in the laser file"
        )
    theta = SIC_GAP_THETA_K
    q = SIC_GAP_EXPONENT
    gap = SIC_GAP_0K_EV - SIC_GAP_SLOPE_EV_PER_K * theta / 2 * (
        (1 + (2 * temperature / theta) ** q) ** (1 / q) - 1
    )
    per_cm = 0.0
    for phonon, strength in zip(SIC_PHONON_ENERGIES_EV, SIC_PHONON_STRENGTHS):
        occupation = 1 / (math.exp(phonon / (BOLTZMANN_EV_PER_K * temperature)) - 1)
        for weight, threshold in ((occupation + 1, gap + phonon), (occupation, gap - phonon)):
            excess = photon - threshold
            per_cm += weight * (
                strength * math.sqrt(max(excess, 0.0))
                + SIC_EXCITON_RATIO * strength * max(excess - SIC_EXCITON_BINDING_EV, 0.0) ** 2
            )
    return 100.0 * per_cm


def absorption_coefficient(material: str, wavelength: float, temperature: float | None = None) -> float:
    """Band-to-band absorption coefficient [1/m] of light of this wavelength
    [um]. For "SiC" it is sic_absorption at the temperature [K] of the device;
    for the other materials it is that at 300 K from the table
    components/laser/absorption/<material>.txt, and the temperature is not used.

    Between the rows the logarithm of the coefficient is interpolated. Light of
    a longer wavelength than the table reaches is not absorbed band to band.
    """
    if material == "SiC":
        if temperature is None:
            raise ValueError(
                "the absorption of SiC depends on the temperature: give the temperature [K] of the device"
            )
        return sic_absorption(wavelength, temperature)
    path = optional_component_path("laser", "absorption", material + ".txt")
    if path is None:
        raise ValueError(
            f"no absorption table of {material}: give alpha [1/m] in the laser file"
        )
    nm, per_cm = np.loadtxt(path, unpack=True)
    if wavelength * 1e3 < nm[0]:
        raise ValueError(
            f"the absorption table of {material} starts at {nm[0]:.0f} nm, "
            f"the laser has {wavelength * 1e3:.0f} nm: give alpha [1/m] in the laser file"
        )
    if wavelength * 1e3 > nm[-1]:
        return 0.0
    return 100.0 * float(np.exp(np.interp(wavelength * 1e3, nm, np.log(per_cm))))

def laser_deposits(my_d, laser_dic: dict) -> Deposits:
    """The pulse of the laser as the deposits of one event, 0, in the device:
    a deposit for every group of pairs, at its place (x, y, z) [um], with its
    pairs (the mean number, not drawn), its energy [MeV] (the pairs times the
    pair energy of the material), made around central_time over the group's
    time_FWHM. A group is a point: its step starts where it lies."""
    laser = LaserInjection(my_d, laser_dic)
    places = np.array(laser.track_position, dtype=float).reshape(-1, 4)
    pairs = [float(n) for n in laser.ionized_pairs]
    count = len(pairs)
    x, y, z, t = (places[:, axis].tolist() for axis in range(4))
    event = EventDeposits(
        0,
        ["Device"] * count,
        x,
        y,
        z,
        t,
        [n * PAIR_ENERGY_EV[my_d.material] * 1e-6 for n in pairs],
        pairs=pairs,
        x_start=list(x),
        y_start=list(y),
        z_start=list(z),
        t_fwhm=[float(w) for w in laser.time_FWHM],
    )
    return Deposits(1, None, None, [event] if count else [])


class LaserInjection:
    """
    Description:
        Transfer Carrier Distribution from Laser Coordinate System
        to Detector Coordinate System
    Parameters:
    ---------
    my_d : R3dDetector
        the Detector
    laser_dic : dict
        the Parameter List of Your Laser
    x_rel,y_rel,z_rel:
        the Normalized Coordinate for Laser Focus
        in Detector Coordinate System
    @Modify:
    ---------
        2021/09/13
    """
    def __init__(self, my_d: Detector, laser_dic: dict):
        #technique used
        self.tech = laser_dic["tech"]
        self.direction = laser_dic["direction"]
        #material parameters to certain wavelength of the beam
        self.refractionIndex = laser_dic["refractionIndex"]
        if self.tech == "TPA":
            self.beta_2 = laser_dic["beta_2"]
        #laser parameters
        self.wavelength = laser_dic["wavelength"]*1e-3 #um
        # m^-1; the laser file may give the one of its sample. A two-photon
        # laser has it too: below the gap it is what the defects absorb.
        if "alpha" in laser_dic:
            self.alpha = laser_dic["alpha"]
        else:
            self.alpha = absorption_coefficient(my_d.material, self.wavelength, getattr(my_d, "temperature", None))
        self.temporal_FWHM = laser_dic["temporal_FWHM"]
        self.pulse_energy = laser_dic["pulse_energy"]
        # TODO: Rename spacial_FWHM to spatial_FWHM.
        self.spacial_FWHM = laser_dic["spacial_FWHM"]#um
        self.central_time = laser_dic["central_time"]
        if "l_Rayleigh" not in laser_dic:
            w_0 = self.spacial_FWHM / (2 * np.log(2))**0.5
            self.l_Rayleigh = np.pi*w_0**2*self.refractionIndex/self.wavelength
        else:
            self.l_Rayleigh = laser_dic["l_Rayleigh"]#um
        #the size of the detector
        self.l_x = my_d.l_x#um
        self.l_y = my_d.l_y
        self.l_z = my_d.l_z
        #relative and absolute position of the focus
        self.fx_rel = laser_dic["fx_rel"]
        self.fy_rel = laser_dic["fy_rel"]
        self.fz_rel = laser_dic["fz_rel"]
        self.fx_abs = self.fx_rel * self.l_x
        self.fy_abs = self.fy_rel * self.l_y
        self.fz_abs = self.fz_rel * self.l_z
        #accuracy parameters: no group of carriers holds more pairs than this,
        #and each kind of absorption has at least so many groups
        self.pairs_per_group = laser_dic["pairs_per_group"]
        self.groups = laser_dic["groups"]

        self.track_position = []
        self.ionized_pairs = []
        # FWHM [s] of the times at which the pairs of each group are made,
        # around central_time: one photon follows the pulse I(t), two photons
        # follow I(t)², a Gaussian narrower by sqrt(2)
        self.time_FWHM = []
        photon_energy = 6.626e-34 * 2.998e8 / (self.wavelength * 1e-6) # J
        photons = self.pulse_energy / photon_energy
        if self.alpha != 0:
            # one pair per absorbed photon: α * photons * exp(-α s) per metre
            self._add_groups(
                lambda s, w2: self.alpha * photons * np.exp(-self.alpha * s * 1e-6),
                2,
                self.temporal_FWHM,
            )
        if self.tech == "TPA":
            # β_2 * ∫I(t)² dt / (2 hν) over the cross section of the beam is
            # β_2 * E² * exp(-2 α s) / (2 hν π w²) per metre for a Gaussian pulse,
            # whose square integrates to sqrt(2 ln2) / (sqrt(π) * temporal_FWHM)
            pulse_squared = (2 * np.log(2))**0.5 / (np.pi**0.5 * self.temporal_FWHM)
            self._add_groups(
                lambda s, w2: self.beta_2 * pulse_squared * self.pulse_energy ** 2
                * np.exp(-2 * self.alpha * s * 1e-6) / (2 * photon_energy * np.pi * w2 * 1e-12),
                4,
                self.temporal_FWHM / 2**0.5,
            )
        elif self.tech != "SPA":
            raise NameError(self.tech)

        print(len(self.ionized_pairs),"pairs of carrier models to drift")
        print(sum(self.ionized_pairs),"total pairs of carriers")

    def _beam_frame(self):
        """The beam in the detector: the length of its path [um], the path to
        the focus, the centre and the limits of the two transverse coordinates,
        and the place (x, y, z) of a point given by path and transverse offsets."""
        if self.direction == "top":
            return (self.l_z, self.fz_abs, (self.fx_abs, self.fy_abs), (self.l_x, self.l_y),
                    lambda s, u, v: (u, v, s))
        if self.direction == "bottom":
            return (self.l_z, self.l_z - self.fz_abs, (self.fx_abs, self.fy_abs), (self.l_x, self.l_y),
                    lambda s, u, v: (u, v, self.l_z - s))
        if self.direction == "edge":
            return (self.l_x, self.fx_abs, (self.fy_abs, self.fz_abs), (self.l_y, self.l_z),
                    lambda s, u, v: (s, u, v))
        raise NameError(self.direction)

    def _add_groups(self, pairs_per_metre, radial_exponent, time_FWHM):
        """Groups of carriers that hold the same number of pairs each.

        pairs_per_metre(s, w²) is the number of pairs made per metre of path at
        the path s [um], where the beam has the radius w [um], summed over the
        cross section. Across the beam the pairs follow exp(-k r² / w²) with
        k = radial_exponent: 2 for one photon, 4 for two. The pairs of every
        group are made over time_FWHM [s] around central_time.

        The path is cut where the pairs made so far reach equal shares, the
        cross section into rings and sectors of equal shares, and a group sits
        at the middle share of its cell. Groups outside the detector are left
        out: that light does not pass through it.
        """
        length, focus, centre, limits, place = self._beam_frame()
        w_0 = self.spacial_FWHM / (2 * np.log(2))**0.5

        def w_squared(s):
            return w_0 ** 2 * (1 + ((s - focus) / self.l_Rayleigh) ** 2)

        finest = min(length, self.l_Rayleigh, 1e6 / self.alpha if self.alpha != 0 else length)
        path = np.linspace(0, length, int(np.ceil(50 * length / finest)) + 1)
        per_metre = pairs_per_metre(path, w_squared(path))
        made = np.concatenate(([0.0], np.cumsum(
            (per_metre[1:] + per_metre[:-1]) / 2 * np.diff(path) * 1e-6
        )))
        total = made[-1]

        rings, sectors = 4, 8
        slabs = int(np.ceil(max(total / self.pairs_per_group, self.groups) / (rings * sectors)))
        s = np.interp((np.arange(slabs) + 0.5) / slabs * total, made, path)
        rho = np.sqrt(-np.log(1 - (np.arange(rings) + 0.5) / rings) / radial_exponent)
        phi = (np.arange(sectors) + 0.5) / sectors * 2 * np.pi
        S, RHO, PHI = (grid.ravel() for grid in np.meshgrid(s, rho, phi, indexing="ij"))
        r = RHO * np.sqrt(w_squared(S))
        u = centre[0] + r * np.cos(PHI)
        v = centre[1] + r * np.sin(PHI)
        inside = (u >= 0) & (u <= limits[0]) & (v >= 0) & (v <= limits[1])
        x, y, z = place(S[inside], u[inside], v[inside])
        for position in np.transpose([x, y, z, np.full(len(x), self.central_time)]):
            self.track_position.append(position)
            self.ionized_pairs.append(total / (slabs * rings * sectors))
            self.time_FWHM.append(time_FWHM)

    def timePulse(self, t):
        # to reduce run time, convolute the time pulse function with the signal after the signal is calculated
        return np.exp(-4 * np.log(2) * t ** 2 / self.temporal_FWHM ** 2) / ((2*np.pi)**(1/2) * self.temporal_FWHM / (2 * (2*np.log(2))**(1/2)))
    
    def _extent(self):
        # the box around the groups, for the pictures
        places = np.array(self.track_position)[:, :3]
        low, high = places.min(axis=0), places.max(axis=0)
        return low, np.where(high > low, high, low + 1.0)

    def draw_nocarrier3D(self,path):
        ROOT.gStyle.SetOptStat(0)
        c1 = ROOT.TCanvas("c1","canvas2",200,10,1000,1000)
        low, high = self._extent()
        h = ROOT.TH3D("h","",\
            50, low[0], high[0],\
            50, low[1], high[1],\
            50, low[2], high[2],)
        for i in range(len(self.track_position)):
            h.Fill(self.track_position[i][0], self.track_position[i][1], self.track_position[i][2], self.ionized_pairs[i],)
        h.Draw()
        h.GetXaxis().SetTitle("Depth [\mum]")#[μm]
        h.GetXaxis().SetTitleSize(0.08)
        h.GetXaxis().SetLabelSize(0.08)
        h.GetXaxis().SetNdivisions(5)
        h.GetYaxis().SetTitle("Width [\mum]")
        h.GetYaxis().SetTitleSize(0.08)
        h.GetYaxis().SetLabelSize(0.08)
        h.GetYaxis().SetNdivisions(5)
        h.GetZaxis().SetTitle("Thick [\mum]")
        h.GetZaxis().SetTitleSize(0.08)
        h.GetZaxis().SetLabelSize(0.08)
        h.GetZaxis().SetNdivisions(5)
        h.GetXaxis().SetTitleOffset(1.8)
        h.GetYaxis().SetTitleOffset(2.2)
        h.GetZaxis().SetTitleOffset(1.4)
        c1.SetLeftMargin(0.15)
        c1.Update()
        c1.SaveAs(path+"/nocarrier_"\
            +str(round(self.fx_rel,5))+"_"\
            +str(round(self.fy_rel,5))+"_"\
            +str(round(self.fz_rel,5))+".pdf")  

    def draw_nocarrier2D(self, path):
        ROOT.gStyle.SetOptStat(0)
        c1 = ROOT.TCanvas("c1","canvas2",200,10,1400,1000)
        low, high = self._extent()
        h = ROOT.TH2D("h","",\
            50, low[0], high[0],\
            50, low[2], high[2],)
        for i in range(len(self.track_position)):
            h.Fill(self.track_position[i][0], self.track_position[i][2], self.ionized_pairs[i],)
        h.Draw("COLZ")
        h.GetXaxis().SetTitle("x axis [\mum]")#[μm]
        h.GetXaxis().SetTitleSize(0.08)
        h.GetXaxis().SetLabelSize(0.08)
        h.GetYaxis().SetTitle("z axis [\mum]")
        h.GetYaxis().SetTitleSize(0.08)
        h.GetYaxis().SetLabelSize(0.08)
        h.GetYaxis().SetTitleOffset(0.9)
        h.GetZaxis().SetTitle("Carriers")
        h.GetZaxis().SetTitleSize(0.08)
        h.GetZaxis().SetLabelSize(0.08)
        h.GetZaxis().SetTitleOffset(1.2)
        h.GetXaxis().SetNdivisions(5)
        h.GetYaxis().SetNdivisions(5)
        h.GetZaxis().SetNdivisions(5)
        c1.SetRightMargin(0.25)
        c1.SetLeftMargin(0.2)
        c1.SetBottomMargin(0.2)
        c1.Update()
        c1.SaveAs(path+"/nocarrier2D_"\
            +str(round(self.fx_rel,5))+"_"\
            +str(round(self.fy_rel,5))+"_"\
            +str(round(self.fz_rel,5))+".pdf")  
