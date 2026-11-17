# -*- encoding: utf-8 -*-

'''
Description:  
    Simulate e-h pairs drifting and calculate induced current
@Date       : 2025/11/11
@Author     : Yuhang Tan, Chenxi Fu, Dai Zhong
@version    : 3.0
'''

import math
import os
import csv
import logging
import numpy as np
import ROOT
ROOT.gROOT.SetBatch(True)

from ..model.material import Material
from .drift import Cluster, Drifted, advance, induced_charges, surviving
from . import draw
from .draw_drift_path import draw_drift_path
from .currents import EventCurrents, append_currents

from ..deposit.carrier_list import CarrierListFromG4P
from ..deposit.deposits import EventDeposits, read_deposits
from raser.supports.output import output

t_bin = {
    1: 5e-12,
    2: 50e-12,
    3: 50e-12  # resolution of oscilloscope
}

t_end = {
    1: 5e-9,
    2: 50e-9,
    3: 50e-9
}

t_start = {
    dimension: -0.25 * end_time for dimension, end_time in t_end.items()
}

delta_t = {
    1: 2e-12,  # simulation time step
    2: 20e-12,
    3: 20e-12
}

logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger.setLevel(logging.INFO)


def spread_over_bins(bins, value, t_from, t_to, t_first, bin_width):
    """Add what one drift step induces to the output bins its time covers.

    `bins` holds the underflow bin, the bins that start at `t_first`, and the
    overflow bin. Each bin receives the share of `value` that the step, lasting
    from `t_from` to `t_to`, spends inside it.
    """
    first = math.floor((t_from - t_first) / bin_width)
    last = math.floor((t_to - t_first) / bin_width)
    for index in range(first, last + 1):
        start = max(t_from, t_first + index * bin_width)
        end = min(t_to, t_first + (index + 1) * bin_width)
        share = max(end - start, 0.0) / (t_to - t_from)
        bins[min(max(index + 1, 0), len(bins) - 1)] += value * share


def fill_histogram(histogram, bins):
    """Copy binned values, underflow and overflow included, into a TH1F.

    Histograms remain for the callers that still read them.
    """
    for index, value in enumerate(bins):
        histogram.SetBinContent(index, float(value))


def electrode_names(read_out_contact, read_ele_num):
    """Names of the readout electrodes, in the order of the currents.

    A device that lists every electrode gives their names. One that lists a
    single electrode repeated over strips or pixels gives that name with
    the number of the electrode, counted from 1 like the listed ones.
    """
    if len(read_out_contact) == read_ele_num:
        return [contact["name"] for contact in read_out_contact]
    if len(read_out_contact) == 1:
        return [
            "{}{}".format(read_out_contact[0]["name"], number + 1)
            for number in range(read_ele_num)
        ]
    raise ValueError(
        "{} readout contacts cannot name {} electrodes".format(
            len(read_out_contact), read_ele_num
        )
    )


def gain_algorithm(my_f):
    """How the gain is calculated in a field.

    A field of one dimension is that of a planar device, whose gain is the
    planar integral; in fields of more dimensions carriers multiply along
    their drift paths.
    """
    return "planar_integral" if len(my_f.axes) == 1 else "local_path"


class CalCurrent:
    """
    Description:
        Calculate sum of the generated current by carriers drifting
    Parameters:
        my_d : Detector
        my_f : FieldCache
        ionized_pairs : float[]
            the generated carrier amount from ionizing radiation or laser
        track_position : float[]
            position of the generated carriers
    Attributes:
        electron_system, hole_system : Drifted
            the generated carriers after their drift
    Modify:
        2024/11/09
    """
    def __init__(self, my_d, my_f, ionized_pairs, track_position, keep_drift_paths=True, diffusion=True):
        self.keep_drift_paths = bool(keep_drift_paths)
        self.diffusion = bool(diffusion)
        self.pairs = float(sum(ionized_pairs))  # electron-hole pairs given, before gain
        if my_d.has_avalanche and gain_algorithm(my_f) == "local_path":
            self.keep_drift_paths = True
        self._run_current_calculation(my_d, my_f, ionized_pairs, track_position)

    def _run_current_calculation(self, my_d, my_f, ionized_pairs, track_position):
        logger.info("current calculation start...")
        self.t_bin = t_bin[my_d.dimension]
        relative_end = t_end[my_d.dimension]
        relative_start = t_start[my_d.dimension]
        if my_d.is_plugin():
            self.t_bin = t_bin[1]
            relative_end = t_end[1]
            relative_start = t_start[1]
        self.delta_t = delta_t[1] if my_d.is_plugin() else delta_t[my_d.dimension]
        creation_times = [float(position[3]) for position in track_position]
        first_creation = min(creation_times, default=0.0)
        last_creation = max(creation_times, default=0.0)
        self.t_start = first_creation + relative_start
        # whole bins of t_bin, as many as reach last_creation + relative_end
        self.n_bin = math.ceil((last_creation + relative_end - self.t_start) / self.t_bin - 1e-6)
        self.t_end = self.t_start + self.n_bin * self.t_bin

        self.read_ele_num = my_d.read_ele_num
        if hasattr(my_d, "x_ele_num") and hasattr(my_d, "y_ele_num"):
            self.x_ele_num = my_d.x_ele_num
            self.y_ele_num = my_d.y_ele_num
        self.read_out_contact = my_d.read_out_contact
        self.electrodes = electrode_names(self.read_out_contact, self.read_ele_num)
        
        # the carriers to drift: those created inside the detector, over an electrode
        starts = []
        pairs = []
        for position, n_pairs in zip(track_position, ionized_pairs):
            x, y, z, t = position
            if self._is_in_sensor(x, y, z, my_d) and self._is_in_field_range(x, y, my_d):
                starts.append((x, y, z, t))
                pairs.append(n_pairs)

        logger.info(f"carriers inside the detector: {len(starts)} electrons, {len(starts)} holes")
        self.electron_system = self.drift_all(my_d, my_f, starts, [-n_pairs for n_pairs in pairs])
        self.hole_system = self.drift_all(my_d, my_f, starts, pairs)

        # number of carriers that stopped for each reason; those of the gain are added with the gain current
        self.ends = self.count_ends()

        # the currents: arrays (read_ele_num, n_bin + 2) in A; the first and last columns hold the parts before and after the time window
        hole_bins = self.binned(my_d, my_f, self.hole_system)
        electron_bins = self.binned(my_d, my_f, self.electron_system)
        sum_bins = hole_bins + electron_bins

        self.det_model = my_d.det_model
        if my_d.has_avalanche:
            self.gain_current = CalCurrentGain(my_d, my_f, self)
            sum_bins += self.gain_current.hole_bins + self.gain_current.electron_bins
            for reason, count in self.gain_current.count_ends().items():
                self.ends[reason] = self.ends.get(reason, 0) + count

        # current of each electrode inside the time window, (read_ele_num, n_bin), in A
        self.hole_current = hole_bins[:, 1:-1]
        self.electron_current = electron_bins[:, 1:-1]
        self.current = sum_bins[:, 1:-1]
        # signed net charge of each electrode in C: all the induced charge, the part outside the time window included
        self.charge = sum_bins.sum(axis=1) * self.t_bin

        # fill the histograms for the callers that still read them
        self.current_define(self.read_ele_num)
        for i in range(self.read_ele_num):
            fill_histogram(self.positive_cu[i], hole_bins[i])
            fill_histogram(self.negative_cu[i], electron_bins[i])
            fill_histogram(self.sum_cu[i], sum_bins[i])

        if not self.keep_drift_paths:
            gain = getattr(self, "gain_current", self)
            for carrier_system in (
                self.electron_system, self.hole_system, gain.electron_system, gain.hole_system
            ):
                if carrier_system is not None:
                    carrier_system.paths = []

    def _is_in_sensor(self, x, y, z, my_d):
        """Whether the position is inside the detector."""
        return (0 <= x <= my_d.l_x and 
                0 <= y <= my_d.l_y and 
                0 <= z <= my_d.l_z)

    def _is_in_field_range(self, x, y, my_d):
        """Whether the position is over one of the electrodes."""
        x_num, y_num = self.electrode_under(x, y, my_d)
        return 0 <= x_num < my_d.x_ele_num and 0 <= y_num < my_d.y_ele_num

    @staticmethod
    def electrode_under(x, y, my_d):
        """Numbers along x and y of the electrode a position is under.

        The electrodes, x_ele_num by y_ele_num at pitches p_x and p_y, are
        centred on the device.
        """
        numbers = []
        for here, length, pitch, count in (
            (x, my_d.l_x, my_d.p_x, my_d.x_ele_num), (y, my_d.l_y, my_d.p_y, my_d.y_ele_num)
        ):
            first_edge = (length - count * pitch) / 2
            number = math.floor((here - first_edge) / pitch)
            # the far edge of the last electrode belongs to it
            numbers.append(count - 1 if here == first_edge + count * pitch else number)
        return numbers

    def drift_all(self, my_d, my_f, starts, charges):
        """Drift a cluster from each of `starts` (x, y, z [um], t [s]); None without any."""
        if not starts:
            return None
        mobility = Material(my_d.material).cal_mobility
        clusters = [Cluster.starting(x, y, z, t, charge) for (x, y, z, t), charge in zip(starts, charges)]
        # one cluster after another, each to its end: the order of the random draws
        for cluster in clusters:
            while cluster.reason is None:
                advance(cluster, my_d, my_f, mobility, self.delta_t, self.diffusion)
        return Drifted(
            list(charges),
            [np.array(cluster.path) for cluster in clusters],
            [cluster.reason for cluster in clusters],
        )

    def count_ends(self):
        """How many clusters stopped for each reason."""
        ends = {}
        for carrier_system in (self.electron_system, self.hole_system):
            if carrier_system is not None:
                for reason in carrier_system.reasons:
                    ends[reason] = ends.get(reason, 0) + 1
        return ends

    def electrodes_near(self, x, y, my_d, my_f):
        """The electrodes a cluster starting at x, y may induce charge on.

        For each: its number among the currents, its number in the field,
        and the offset `induced_charges` takes. A device that lists every
        electrode gives them all. Where one listed electrode repeats, its
        weighting potential is the same for every electrode: the field holds
        it once, on a row of cells that starts at 0 with the electrode in
        the middle one, and the offset moves an electrode onto that cell.
        The electrodes of the cells the potential is on are given, counted
        from the one above the start: further away it is left out as nothing.
        """
        if len(self.read_out_contact) != 1:
            return [(number, number, (0.0, 0.0)) for number in range(len(self.read_out_contact))]
        x_num, y_num = self.electrode_under(x, y, my_d)
        x_span = my_f.cells_either_side
        y_span = self.read_out_contact[0].get('y_span', 0)
        x_first = (my_d.l_x - my_d.x_ele_num * my_d.p_x) / 2
        y_first = (my_d.l_y - my_d.y_ele_num * my_d.p_y) / 2
        near = []
        for i in range(max(x_num - x_span, 0), min(x_num + x_span, my_d.x_ele_num - 1) + 1):
            for j in range(max(y_num - y_span, 0), min(y_num + y_span, my_d.y_ele_num - 1) + 1):
                offset = (x_first + (i - x_span) * my_d.p_x, y_first + (j - y_span) * my_d.p_y)
                near.append((i * my_d.y_ele_num + j, 0, offset))
        return near

    def binned(self, my_d, my_f, carrier_system):
        """Binned current of the clusters of one sign.

        An array (read_ele_num, n_bin + 2) in A: per electrode the part
        before t_start, the n_bin bins of the time window, and the part
        after t_end.
        """
        bins = np.zeros((self.read_ele_num, self.n_bin + 2), dtype=np.float64)
        if carrier_system is None:
            return bins
        bin_width = (self.t_end - self.t_start) / self.n_bin
        for charge, path in zip(carrier_system.charges, carrier_system.paths):
            if len(path) < 2:
                continue
            if my_d.irradiation_model is not None:
                charge = surviving(path, charge, my_f)
            for number, in_field, offset in self.electrodes_near(path[0][0], path[0][1], my_d, my_f):
                induced = induced_charges(path, charge, my_f, in_field, offset)
                for value, t_from, t_to in zip(induced, path[:-1, 3], path[1:, 3]):
                    spread_over_bins(
                        bins[number], value / self.t_bin, t_from, t_to, self.t_start, bin_width
                    )
        return bins

    def current_define(self, read_ele_num):
        """Create the current histograms."""
        self.positive_cu = []
        self.negative_cu = []
        self.sum_cu = []

        for i in range(read_ele_num):
            self.positive_cu.append(ROOT.TH1F("charge+"+str(i+1), " No."+str(i+1)+"Positive Current",
                                        self.n_bin, self.t_start, self.t_end))
            self.negative_cu.append(ROOT.TH1F("charge-"+str(i+1), " No."+str(i+1)+"Negative Current",
                                        self.n_bin, self.t_start, self.t_end))
            self.sum_cu.append(ROOT.TH1F("charge"+str(i+1),"Total Current"+" No."+str(i+1)+"electrode",
                                    self.n_bin, self.t_start, self.t_end))
            
    def draw_currents(self, path, tag=""):
        gain = getattr(self, "gain_current", None)
        draw.draw_currents(
            path, self.t_start, (self.t_end - self.t_start) / self.n_bin,
            self.current, self.hole_current, self.electron_current,
            None if gain is None else gain.hole_bins[:, 1:-1],
            None if gain is None else gain.electron_bins[:, 1:-1],
            tag=tag,
        )

    def charge_collection_strip(self, path):
        draw.charge_collection_strip(path, self.charge)

    def charge_collection_pixel(self, path):
        draw.charge_collection_pixel(path, self.charge, self.x_ele_num, self.y_ele_num)

class CalCurrentGain(CalCurrent):
    '''Calculation of gain carriers and gain current, simplified version'''
    def __init__(self, my_d, my_f, my_current):
        self.keep_drift_paths = getattr(my_current, "keep_drift_paths", True)
        self.diffusion = my_current.diffusion
        self.t_bin = my_current.t_bin
        self.t_end = my_current.t_end
        self.t_start = my_current.t_start
        self.delta_t = my_current.delta_t
        self.n_bin = my_current.n_bin

        self.read_ele_num = my_current.read_ele_num
        self.read_out_contact = my_current.read_out_contact

        # the gain carriers: where and when they start, and how many pairs
        gain_starts = []
        gain_pairs = []
        if gain_algorithm(my_f) == "local_path":
            self._build_local_gain_carriers(my_d, my_f, my_current, gain_starts, gain_pairs)
        else:
            self._build_planar_gain_carriers(my_d, my_f, my_current, gain_starts, gain_pairs)

        logger.info("gain carriers generated: %d", len(gain_starts))

        self.electron_system = self.drift_all(my_d, my_f, gain_starts, [-pairs for pairs in gain_pairs])
        self.hole_system = self.drift_all(my_d, my_f, gain_starts, gain_pairs)

        # the currents
        self.hole_bins = self.binned(my_d, my_f, self.hole_system)
        self.electron_bins = self.binned(my_d, my_f, self.electron_system)

        # fill the histograms for the callers that still read them
        self.current_define(self.read_ele_num)
        for i in range(self.read_ele_num):
            fill_histogram(self.positive_cu[i], self.hole_bins[i])
            fill_histogram(self.negative_cu[i], self.electron_bins[i])

    def _build_planar_gain_carriers(self, my_d, my_f, my_current, gain_starts, gain_pairs):
        logger.info("gain_rate=%s", my_f.planar_gain(my_d))

        # the carriers that drift from the bulk into the gain layer
        if my_f.planar_gain_carrier(my_d) > 0:
            source_system = my_current.hole_system
        else:
            source_system = my_current.electron_system

        if source_system is None:
            logger.warning("No carrier system found for planar gain calculation.")
            return

        # each cluster multiplies where it stops: its pairs start at the gain
        # layer at that time, as many as the depth it was made at gives
        gain_depth = my_f.planar_gain_depth(my_d)
        for charge, path in zip(source_system.charges, source_system.paths):
            x, y, _, t = path[-1]
            gain_starts.append((x, y, gain_depth, t))
            gain_pairs.append(abs(charge) * my_f.planar_gain_at(my_d, path[0][2]))

    def _build_local_gain_carriers(self, my_d, my_f, my_current, gain_starts, gain_pairs):
        cal_coefficient = Material(my_d.material, avalanche_model=my_d.avalanche_model).cal_coefficient
        min_pairs = max(float(getattr(my_d, "gain_pair_threshold", 0.05)), 0.0)
        max_carriers = int(getattr(my_d, "gain_max_carriers", 50000))
        emit_slices = max(1, int(getattr(my_d, "local_gain_emit_slices", 1)))
        samples = max(1, int(getattr(my_d, "local_gain_integration_steps", 3)))
        emitted_segments = 0
        field_failures = 0

        for carrier_system in (my_current.electron_system, my_current.hole_system):
            if carrier_system is None:
                continue
            for carrier_idx, path in enumerate(carrier_system.paths):
                if len(path) < 2:
                    continue

                active_pairs = abs(carrier_system.charges[carrier_idx])
                pending_pairs = 0.0
                if active_pairs <= 0:
                    continue
                charge_sign = -1 if carrier_system.charges[carrier_idx] < 0 else 1
                for point0, point1 in zip(path[:-1], path[1:]):
                    x0, y0, z0, t0 = point0
                    x1, y1, z1, t1 = point1
                    dx = x1 - x0
                    dy = y1 - y0
                    dz = z1 - z0
                    if dx == 0 and dy == 0 and dz == 0:
                        continue

                    exponent = 0.0
                    for sample_idx in range(samples):
                        fraction = (sample_idx + 0.5) / samples
                        x = x0 + fraction * (x1 - x0)
                        y = y0 + fraction * (y1 - y0)
                        z = z0 + fraction * (z1 - z0)
                        try:
                            field_vector = my_f.get_e_field_cached(x, y, z)
                            field = math.hypot(*field_vector)
                        except Exception:
                            field_failures += 1
                            continue
                        if field <= 0:
                            continue
                        direction = 1.0 if charge_sign > 0 else -1.0
                        drift_length_um = direction * (
                            dx * field_vector[0] + dy * field_vector[1] + dz * field_vector[2]
                        ) / field
                        if drift_length_um <= 0:
                            continue
                        alpha = cal_coefficient(field, charge_sign, my_d.temperature)
                        if not math.isfinite(alpha):
                            alpha = 0.0
                        alpha = max(alpha, 0.0)
                        exponent += alpha * (drift_length_um / samples) * 1e-4

                    if not math.isfinite(exponent):
                        continue
                    exponent = min(exponent, 50.0)
                    new_pairs = active_pairs * math.expm1(exponent)
                    if new_pairs <= 0:
                        continue
                    active_pairs += new_pairs
                    pending_pairs += new_pairs
                    last_growth = (x0, y0, z0, t0, x1, y1, z1, t1)
                    if pending_pairs < min_pairs:
                        continue

                    slices = emit_slices
                    if max_carriers > 0:
                        capacity = max_carriers - len(gain_starts)
                        if capacity <= 0:
                            raise ValueError(
                                "the gain of {} makes more than gain_max_carriers = {} clusters "
                                "of carriers: raise it in the device file".format(my_d.det_name, max_carriers)
                            )
                        slices = min(slices, capacity)
                    for slice_idx in range(slices):
                        fraction = (slice_idx + 0.5) / slices
                        gain_starts.append((
                            x0 + fraction * dx, y0 + fraction * dy, z0 + fraction * dz,
                            t0 + fraction * (t1 - t0),
                        ))
                        gain_pairs.append(pending_pairs / slices)
                    pending_pairs = 0.0
                    emitted_segments += 1

                # pairs too few to emit by the end of the path start at the
                # middle of the last segment they grew on
                if pending_pairs > 0:
                    if max_carriers > 0 and len(gain_starts) >= max_carriers:
                        raise ValueError(
                            "the gain of {} makes more than gain_max_carriers = {} clusters "
                            "of carriers: raise it in the device file".format(my_d.det_name, max_carriers)
                        )
                    x0, y0, z0, t0, x1, y1, z1, t1 = last_growth
                    gain_starts.append(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2, (t0 + t1) / 2))
                    gain_pairs.append(pending_pairs)

        logger.info("local gain emitted segments: %d", emitted_segments)
        if field_failures:
            logger.warning("local gain skipped %d field samples because field lookup failed.", field_failures)

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
            self.negative_cu.append(ROOT.TH1F("gain_charge_tmp-"+str(i+1)," No."+str(i+1)+"Gain Negative Current",
                                        self.n_bin, self.t_start, self.t_end))

class CalCurrentG4P(CalCurrent):
    def __init__(self, my_d, my_f, my_g4, batch, keep_drift_paths=True):
        G4P_carrier_list = CarrierListFromG4P(
            my_d.material,
            my_g4,
            batch,
            fano_sampling=getattr(my_d, "fano_sampling", False),
            fano_factor=getattr(my_d, "fano_factor", 0.0),
        )
        self.generated_pairs = sum(G4P_carrier_list.ionized_pairs)
        super().__init__(
            my_d,
            my_f,
            G4P_carrier_list.ionized_pairs,
            G4P_carrier_list.track_position,
            keep_drift_paths=keep_drift_paths,
        )


def pulse_in_bins(time_pulse, fwhm, n_bin, bin_width):
    """Share of a laser pulse in a time bin, for each offset of the bin.

    `time_pulse(t)` [1/s] is the pulse shape, of integral 1, at the time t
    [s] from its middle, and `fwhm` [s] its full width at half maximum.
    Returns the integral of `time_pulse` over the bin of `bin_width` [s]
    centred k bins from the middle, for k from -(n_bin - 1) to n_bin - 1.
    The integral takes samples a twentieth of the width apart or closer, so
    a pulse much shorter than a bin gives a share of 1 to the bin it lies in.
    """
    samples = max(1, math.ceil(20 * bin_width / fwhm))
    offsets = np.arange(-(n_bin - 1), n_bin)
    shares = np.zeros(len(offsets))
    for sample in range(samples):
        shares += time_pulse((offsets + (sample + 0.5) / samples - 0.5) * bin_width)
    return shares * bin_width / samples


class CalCurrentLaser(CalCurrent):
    def __init__(self, my_d, my_f, my_l, keep_drift_paths=True, diffusion=True):
        super().__init__(
            my_d,
            my_f,
            my_l.ionized_pairs,
            my_l.track_position,
            keep_drift_paths=keep_drift_paths,
            diffusion=diffusion,
        )
        
        # convolute the currents with the laser pulse shape in time
        bin_width = (self.t_end - self.t_start) / self.n_bin
        shares = pulse_in_bins(my_l.timePulse, my_l.temporal_FWHM, self.n_bin, bin_width)
        bins = np.arange(self.n_bin)
        pulse = shares[bins[:, None] - bins[None, :] + self.n_bin - 1]
        convolved = [
            (self.hole_current, self.positive_cu),
            (self.electron_current, self.negative_cu),
            (self.current, self.sum_cu),
        ]
        if hasattr(self, "gain_current"):
            convolved.append((self.gain_current.hole_bins[:, 1:-1], self.gain_current.positive_cu))
            convolved.append((self.gain_current.electron_bins[:, 1:-1], self.gain_current.negative_cu))
        for currents, histograms in convolved:
            currents[:] = currents @ pulse
            for i in range(self.read_ele_num):
                fill_histogram(histograms[i], np.pad(currents[i], 1))


def deposits_in(record, detector):
    """The deposits of an event that lie in the detector of this name."""
    kept = [k for k, name in enumerate(record.detector) if name == detector]
    return EventDeposits(
        record.event,
        *([column[k] for k in kept] for column in (record.detector, record.x, record.y, record.z, record.t, record.e)),
        pairs=None if record.pairs is None else [record.pairs[k] for k in kept],
    )


def write_induced_currents(deposits_path, currents_path, my_d, my_f, plots=0, plot_path=None, detector=None):
    """Drift the pairs of every event of the deposits file in the field and
    write the currents they induce to the currents file, event by event.

    With `detector`, only the deposits that lie in the detector of that name
    are drifted, and an event without any of them writes no row.

    A currents file an earlier start left there is replaced. The first `plots`
    events are also drawn, each in plot_path/event_<number>: the drift paths
    with the deposits, and the currents.
    """
    deposits = read_deposits(deposits_path)
    if not deposits.events:
        raise ValueError(f"{deposits_path} holds no event: there is no current to write")
    events = deposits.events
    if detector is not None:
        events = [record for record in (deposits_in(record, detector) for record in events) if record.detector]
        if not events:
            raise ValueError(
                f"{deposits_path} holds no deposit in the detector {detector}: there is no current to write"
            )
    if os.path.exists(currents_path):
        os.remove(currents_path)
    for count, record in enumerate(events):
        drawn = count < plots
        positions = [list(point) for point in zip(record.x, record.y, record.z, record.t)]
        my_current = CalCurrent(my_d, my_f, record.pairs, positions, keep_drift_paths=drawn)
        append_currents(
            currents_path,
            my_current.electrodes,
            my_current.t_bin,
            EventCurrents(
                record.event,
                my_current.t_start,
                my_current.current,
                my_current.charge,
                my_current.pairs,
            ),
        )
        if drawn:
            path = os.path.join(plot_path, "event_%s" % (record.event))
            os.makedirs(path, exist_ok=True)
            draw_drift_path(my_d, list(zip(record.x, record.y, record.z)), my_f, my_current, path)
            my_current.draw_currents(path)
            if my_d.is_strip:
                my_current.charge_collection_strip(path)
            if my_d.is_pixel:
                my_current.charge_collection_pixel(path)


def write_laser_currents(currents_path, my_d, my_f, my_l, plot_path=None):
    """Drift the pairs of one laser pulse in the field, without diffusion, and
    write the currents they induce to the currents file as its event 0.

    A currents file an earlier start left there is replaced. With plot_path
    the currents are also drawn there.
    """
    if os.path.exists(currents_path):
        os.remove(currents_path)
    my_current = CalCurrentLaser(my_d, my_f, my_l, diffusion=False)
    append_currents(
        currents_path,
        my_current.electrodes,
        my_current.t_bin,
        EventCurrents(
            0, my_current.t_start, my_current.current, my_current.charge, my_current.pairs
        ),
    )
    if plot_path is not None:
        os.makedirs(plot_path, exist_ok=True)
        my_current.draw_currents(plot_path)
