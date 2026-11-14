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

from .model import Material
from .carrier import END_REASONS, VectorizedCarrierSystem
from . import draw

from ..interaction.carrier_list import CarrierListFromG4P
from ..interaction.toy_mip import ToyMIPLineSource
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

t_tol = 1e-20


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


def gain_algorithm(my_d):
    """How the gain of a device is calculated.

    The device file may name it; otherwise carriers multiply along their
    drift paths in three dimensions and by the planar integral elsewhere.
    """
    default = "local_path" if my_d.dimension == 3 else "planar_integral"
    algorithm = getattr(my_d, "gain_algorithm", default)
    if algorithm not in ("planar_integral", "local_path"):
        raise ValueError("Unsupported gain_algorithm: {}".format(algorithm))
    return algorithm


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
        electrons, holes : VectorizedCarrierSystem[]
            the generated carriers, able to calculate their movement
    Modify:
        2024/11/09
    """
    def __init__(self, my_d, my_f, ionized_pairs, track_position, keep_drift_paths=True, diffusion=True):
        self.keep_drift_paths = bool(keep_drift_paths)
        self.diffusion = bool(diffusion)
        if my_d.has_avalanche and gain_algorithm(my_d) == "local_path":
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
        # the drift, the time axis and the trapping decay share one time step
        self.delta_t = getattr(my_d, "vector_delta_t", self.delta_t)
        creation_times = [float(position[3]) for position in track_position]
        first_creation = min(creation_times, default=0.0)
        last_creation = max(creation_times, default=0.0)
        self.t_start = first_creation + relative_start
        self.t_end = last_creation + relative_end
        self.n_bin = int((self.t_end + t_tol - self.t_start) / self.t_bin)

        self.read_ele_num = my_d.read_ele_num
        if hasattr(my_d, "x_ele_num") and hasattr(my_d, "y_ele_num"):
            self.x_ele_num = my_d.x_ele_num
            self.y_ele_num = my_d.y_ele_num
        self.read_out_contact = my_d.read_out_contact
        self.electrodes = electrode_names(self.read_out_contact, self.read_ele_num)
        
        self.electron_system = None
        self.hole_system = None

        # the carriers to drift
        electron_positions = []
        electron_charges = []
        electron_times = []
        electron_signals = []
        
        hole_positions = []
        hole_charges = []
        hole_times = []
        hole_signals = []

        for i in range(len(track_position)):
            x, y, z, t = track_position[i]
            t_num = int(t / self.delta_t + t_tol)
            charge = ionized_pairs[i]
                
            # leave out the carriers created outside the detector
            if self._is_in_sensor(x, y, z, my_d) and self._is_in_field_range(x, y, my_d, my_d.x_ele_num, my_d.y_ele_num):
                # electron
                electron_positions.append([x, y, z])
                electron_charges.append(-charge)  # electrons are negative
                electron_times.append(t_num)
                electron_signals.append([])  # its signals, none yet
                    
                # hole
                hole_positions.append([x, y, z])
                hole_charges.append(charge)  # holes are positive
                hole_times.append(t_num)
                hole_signals.append([])

        logger.info(f"carriers inside the detector: {len(electron_positions)} electrons, {len(hole_positions)} holes")

        # the carrier systems
        if electron_positions:
            self.electron_system = VectorizedCarrierSystem(
                electron_positions, electron_charges, electron_times, electron_signals,
                my_d.material, "electron", self.read_out_contact, my_d,
                keep_drift_paths=self.keep_drift_paths,
                diffusion=self.diffusion,
            )
            
        if hole_positions:
            self.hole_system = VectorizedCarrierSystem(
                hole_positions, hole_charges, hole_times, hole_signals,
                my_d.material, "hole", self.read_out_contact, my_d,
                keep_drift_paths=self.keep_drift_paths,
                diffusion=self.diffusion,
            )

        logger.info("carrier systems ready")
        
        # drift and calculate the signals
        self.drifting_loop(my_d, my_f)

        # number of carriers that stopped for each reason; those of the gain are added with the gain current
        self.ends = self.count_ends()

        # the currents: arrays (read_ele_num, n_bin + 2) in A; the first and last columns hold the parts before and after the time window
        hole_bins, electron_bins = self.get_current(my_d.x_ele_num, my_d.y_ele_num, self.read_out_contact)
        sum_bins = hole_bins + electron_bins

        self.det_model = my_d.det_model
        if my_d.has_avalanche:
            self.gain_current = CalCurrentGain(my_d, my_f, self)
            sum_bins += self.gain_current.hole_bins + self.gain_current.electron_bins
            for reason, count in self.gain_current.count_ends().items():
                self.ends[reason] += count

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

    def _is_in_sensor(self, x, y, z, my_d):
        """Whether the position is inside the detector."""
        return (0 <= x <= my_d.l_x and 
                0 <= y <= my_d.l_y and 
                0 <= z <= my_d.l_z)

    def _is_in_field_range(self, x, y, my_d, n_x, n_y):
        """Whether the position is over one of the electrodes."""
        # the number of the electrode
        try:
            x_num = int((x - my_d.l_x/2) // getattr(my_d, 'p_x', my_d.l_x) + n_x/2.0)
            y_num = int((y - my_d.l_y/2) // getattr(my_d, 'p_y', my_d.l_y) + n_y/2.0)
            return (0 <= x_num < n_x and 0 <= y_num < n_y)
        except:
            return True  # taken as inside when the number cannot be calculated

    def drifting_loop(self, my_d, my_f):
        """Drift the carrier systems and calculate their signals."""
        logger.info(f"drift: electron system={self.electron_system is not None}, hole system={self.hole_system is not None}")
        delta_t_sim = self.delta_t
        
        try:            
            # electrons
            if self.electron_system:
                logger.info(f"electrons: {len(self.electron_system.positions)}")
                self.electron_system.drift_batch(my_d, my_f, delta_t=delta_t_sim)
                logger.info("electrons drifted, calculating their signals...")
                self.electron_system.get_signal_batch(my_d, my_f, delta_t=delta_t_sim)
            
            # holes
            if self.hole_system:
                logger.info(f"holes: {len(self.hole_system.positions)}")
                self.hole_system.drift_batch(my_d, my_f, delta_t=delta_t_sim)
                logger.info("holes drifted, calculating their signals...")
                self.hole_system.get_signal_batch(my_d, my_f, delta_t=delta_t_sim)
                            
            cache_stats = my_f.get_cache_stats()
            logger.info(
                "field cache: hits=%d, misses=%d, errors=%d, fallbacks=%d, hit rate=%.2f%%",
                cache_stats['hits'], cache_stats['misses'], cache_stats['errors'],
                cache_stats['fallbacks'], cache_stats['hit_rate'] * 100.0
            )
                            
        except Exception as e:
            logger.exception("drift failed: %s", e)
            raise
    
        logger.info("drift and signals done")

    def count_ends(self):
        """How many carriers stopped for each of END_REASONS."""
        ends = dict.fromkeys(END_REASONS.values(), 0)
        for carrier_system in (self.electron_system, self.hole_system):
            if carrier_system is not None:
                for code, reason in END_REASONS.items():
                    ends[reason] += int(np.sum(carrier_system.end_conditions == code))
        return ends

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
            
    def get_current(self, n_x, n_y, read_out_contact):
        """Binned currents of the holes and of the electrons.

        Each is an array (read_ele_num, n_bin + 2) in A: per electrode the
        part before t_start, the n_bin bins of the time window, and the part
        after t_end.
        """
        logger.info("binning the currents...")
        binned = []
        for carrier_system in (self.hole_system, self.electron_system):
            bins = np.zeros((self.read_ele_num, self.n_bin + 2), dtype=np.float64)
            if carrier_system is not None:
                if len(read_out_contact) == 1:
                    self._process_system_current(
                        carrier_system, bins, n_x, n_y,
                        read_out_contact[0]['x_span'], read_out_contact[0]['y_span'],
                    )
                else:
                    self._process_system_current_direct(carrier_system, bins)
            binned.append(bins)
        hole_bins, electron_bins = binned

        for i in range(self.read_ele_num):
            hole_integral = hole_bins[i, 1:-1].sum() * self.t_bin
            electron_integral = electron_bins[i, 1:-1].sum() * self.t_bin
            logger.info(f"electrode {i}: hole charge={hole_integral:.2e}C, electron charge={electron_integral:.2e}C")
        return hole_bins, electron_bins

    def _process_system_current(self, carrier_system, bins, n_x, n_y, x_span, y_span):
        """One listed electrode: add what each step of a carrier system induces to bins."""
        total_electrodes = (2 * x_span + 1) * (2 * y_span + 1)
        bin_width = (self.t_end - self.t_start) / self.n_bin

        for carrier_idx in range(len(carrier_system.positions)):
            # carriers without signals are skipped
            if (carrier_idx >= len(carrier_system.signals) or 
                not carrier_system.signals[carrier_idx]):
                continue
            
            carrier_signals = carrier_system.signals[carrier_idx]
            path_reduced = carrier_system.paths_reduced[carrier_idx]
            
            # every electrode around the carrier
            for electrode_idx in range(total_electrodes):
                if electrode_idx >= len(carrier_signals):
                    continue
                
                electrode_signals = carrier_signals[electrode_idx]
                if not electrode_signals:
                    continue
                
                # j, k of the electrode
                j = electrode_idx // (2 * y_span + 1)
                k = electrode_idx % (2 * y_span + 1)
                
                # the signal of every step of the path
                for step_idx in range(len(path_reduced)-1):                    
                    signal_value = electrode_signals[step_idx]

                    # the numbers of the electrode at this point of the path
                    x_num = path_reduced[step_idx][4] + (j - x_span)
                    y_num = path_reduced[step_idx][5] + (k - y_span)
                    
                    # electrodes outside the device are skipped
                    if 0 <= x_num < n_x and 0 <= y_num < n_y:
                        target_electrode = x_num * n_y + y_num
                        if target_electrode < self.read_ele_num:
                            spread_over_bins(
                                bins[target_electrode],
                                signal_value / self.t_bin,
                                path_reduced[step_idx][3] * self.delta_t,
                                path_reduced[step_idx + 1][3] * self.delta_t,
                                self.t_start,
                                bin_width,
                            )

    def _process_system_current_direct(self, carrier_system, bins):
        """Every electrode listed: add what each step of a carrier system induces to bins."""
        bin_width = (self.t_end - self.t_start) / self.n_bin

        for carrier_idx, carrier_signals in enumerate(carrier_system.signals):
            if not carrier_signals:
                continue
            path = carrier_system.paths_reduced[carrier_idx]
            for electrode_idx, electrode_signals in enumerate(
                carrier_signals[:len(self.read_out_contact)]
            ):
                for step_idx, signal_value in enumerate(
                    electrode_signals[: max(0, len(path) - 1)]
                ):
                    spread_over_bins(
                        bins[electrode_idx],
                        signal_value / self.t_bin,
                        path[step_idx][3] * self.delta_t,
                        path[step_idx + 1][3] * self.delta_t,
                        self.t_start,
                        bin_width,
                    )

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

        # the systems of the gain carriers
        self.electron_system = None
        self.hole_system = None
        
        # the gain carriers
        gain_positions = []
        gain_electron_charges = []
        gain_hole_charges = []
        gain_times = []
        gain_signals = []

        if gain_algorithm(my_d) == "local_path":
            self._build_local_gain_carriers(
                my_d, my_f, my_current,
                gain_positions, gain_electron_charges, gain_hole_charges, gain_times, gain_signals,
            )
        else:
            self._build_planar_gain_carriers(
                my_d, my_f, my_current,
                gain_positions, gain_electron_charges, gain_hole_charges, gain_times, gain_signals,
            )

        logger.info("gain carriers generated: %d", len(gain_positions))

        # the systems of the gain carriers
        if gain_electron_charges:
            self.electron_system = VectorizedCarrierSystem(
                gain_positions, gain_electron_charges, gain_times, gain_signals,
                my_d.material, "electron_gain", self.read_out_contact, my_d,
                keep_drift_paths=getattr(my_current, "keep_drift_paths", True),
                diffusion=self.diffusion,
            )
        else:
            logger.info("No gain electrons generated.")
        
        if gain_hole_charges:
            self.hole_system = VectorizedCarrierSystem(
                gain_positions, gain_hole_charges, gain_times, gain_signals,
                my_d.material, "hole_gain", self.read_out_contact, my_d,
                keep_drift_paths=getattr(my_current, "keep_drift_paths", True),
                diffusion=self.diffusion,
            )
        else:
            logger.info("No gain holes generated.")

        # drift
        self.drifting_loop(my_d, my_f)

        # the currents
        self.hole_bins, self.electron_bins = self.get_current(
            my_d.x_ele_num, my_d.y_ele_num, self.read_out_contact
        )

        # fill the histograms for the callers that still read them
        self.current_define(self.read_ele_num)
        for i in range(self.read_ele_num):
            fill_histogram(self.positive_cu[i], self.hole_bins[i])
            fill_histogram(self.negative_cu[i], self.electron_bins[i])

    def _build_planar_gain_carriers(self, my_d, my_f, my_current, gain_positions,
                                    gain_electron_charges, gain_hole_charges,
                                    gain_times, gain_signals):
        if my_d.avalanche_bond is None:
            raise ValueError("planar_integral gain algorithm requires `avalanche_bond` in detector settings")
        gain_rate = my_f.planar_gain(my_d)
        logger.info("gain_rate=%s", gain_rate)

        if my_d.voltage < 0:  # p layer at d=0: holes multiply into electrons
            source_system = my_current.hole_system
            electron_sign = -1
            hole_sign = 1
        else:  # n layer at d=0: electrons multiply into holes
            source_system = my_current.electron_system
            electron_sign = 1
            hole_sign = -1

        if source_system is None:
            logger.warning("No carrier system found for planar gain calculation.")
            return

        for i in range(len(source_system.positions)):
            charge = source_system.charges[i] * gain_rate
            last_pos = source_system.positions[i]
            gain_positions.append([last_pos[0], last_pos[1], my_d.avalanche_bond])
            gain_electron_charges.append(electron_sign * charge)
            gain_hole_charges.append(hole_sign * charge)
            gain_times.append(int(source_system.times[i]))
            gain_signals.append([])

    def _build_local_gain_carriers(self, my_d, my_f, my_current, gain_positions,
                                   gain_electron_charges, gain_hole_charges,
                                   gain_times, gain_signals):
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
                    gain_pairs = active_pairs * math.expm1(exponent)
                    if gain_pairs <= 0:
                        continue
                    active_pairs += gain_pairs
                    pending_pairs += gain_pairs
                    if pending_pairs < min_pairs:
                        continue

                    slices = emit_slices
                    if max_carriers > 0:
                        capacity = max_carriers - len(gain_positions)
                        if capacity <= 0:
                            if gain_positions:
                                gain_electron_charges[-1] -= pending_pairs
                                gain_hole_charges[-1] += pending_pairs
                            logger.warning("Gain carrier generation reached configured limit (%d).", max_carriers)
                            return
                        slices = min(slices, capacity)
                    for slice_idx in range(slices):
                        fraction = (slice_idx + 0.5) / slices
                        gain_positions.append([x0 + fraction * dx, y0 + fraction * dy, z0 + fraction * dz])
                        gain_electron_charges.append(-pending_pairs / slices)
                        gain_hole_charges.append(pending_pairs / slices)
                        gain_times.append(int(round(t0 + fraction * (t1 - t0))))
                        gain_signals.append([])
                    pending_pairs = 0.0
                    emitted_segments += 1

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


class CalCurrentToyMIP(CalCurrent):
    def __init__(self, my_d, my_f, source: ToyMIPLineSource, keep_drift_paths=True):
        self.generated_pairs = sum(source.ionized_pairs)
        super().__init__(
            my_d,
            my_f,
            source.ionized_pairs,
            source.track_position,
            keep_drift_paths=keep_drift_paths,
        )


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
        bins = np.arange(self.n_bin)
        pulse = my_l.timePulse((bins[:, None] - bins[None, :]) * bin_width) * bin_width
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
