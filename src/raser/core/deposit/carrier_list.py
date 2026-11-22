"""
Description:  carrier_list.py
@Date       : 2025
@Author     : Yuhang Tan, Chenxi Fu
@version    : 2.0
"""

import ROOT

from .energy_loss import sample_fano_pairs

ROOT.gROOT.SetBatch(True)


class PixelCarrierListFromG4P:
    def __init__(
        self,
        my_d,
        my_g4,
        *,
        fano_sampling=False,
        fano_factor=0.0,
        rng=None,
    ):
        """
        Description:
            Events position and energy depositon
        Parameters:
            material : string
                deciding the energy loss of MIP
            my_g4 : G4Interaction
            batch : int
                batch = 0: Single event, select particle with long enough track
                batch != 0: Multi event, assign particle with batch number
        Modify:
            2022/10/25
        """
        batch = len(my_g4.localpositions)
        layer = len(my_g4.ltz)
        material = my_d.material
        self.pixelsize_x = my_d.p_x
        self.pixelsize_y = my_d.p_y
        self.pixelsize_z = my_d.l_z

        if material == "SiC":
            self.energy_loss = 8.4  # ev
        elif material == "Si":
            self.energy_loss = 3.6  # ev
        self.fano_sampling = bool(fano_sampling)
        self.fano_factor = float(fano_factor or 0.0)
        self.rng = rng

        self.track_position, self.ionized_pairs = [], []
        self.layer = layer
        for j in range(batch):
            self.single_event(my_g4, j)

    def single_event(self, my_g4, j):
        s_track_position, s_energy = [], []
        for i in range(self.layer):
            position = []
            energy = []
            name = "Layer_" + str(i)
            # print(name)
            for k in range(len(my_g4.devicenames[j])):
                px, py, pz = self.split_name(my_g4.devicenames[j][k])
                if name in my_g4.devicenames[j][k]:
                    tp = [0 for i in range(3)]
                    tp[0] = (
                        my_g4.localpositions[j][k][0] + (px - 0.5) * self.pixelsize_x
                    )
                    tp[1] = (
                        my_g4.localpositions[j][k][1] + (py - 0.5) * self.pixelsize_y
                    )
                    tp[2] = my_g4.localpositions[j][k][2] + self.pixelsize_z / 2
                    position.append(tp)
                    energy.append(my_g4.energy_steps[j][k])
            s_track_position.append(position)
            pairs = [self._pairs_from_energy(step) for step in energy]
            s_energy.append(pairs)
            del position, energy
        self.track_position.append(s_track_position)
        self.ionized_pairs.append(s_energy)

    def _pairs_from_energy(self, energy_mev):
        mean_pairs = energy_mev * 1e6 / self.energy_loss
        if not self.fano_sampling:
            return mean_pairs
        return sample_fano_pairs(mean_pairs, self.fano_factor, self.rng)

    def split_name(self, volume_name):
        parts = volume_name.split("_")
        return int(parts[1]), int(parts[2]), int(parts[4])
