'''
Description:  
   Carrier system using vectorization
@Date       : 2025/11/11
@Author     : Dai Zhong, Chenxi Fu
@version    : 1.0
'''

import math
import logging
import time
from raser.core.seeding import stream

import numpy as np

from .model import Material
from raser.core.field.simple import AnalyticStripPixelField

tolerance_default = 1e-6

min_intensity = 1 # V/cm

# why a carrier stopped; the keys are the numbers in end_conditions
END_REASONS = {
    0: "still_drifting",  # not stopped when the drift steps ran out
    1: "left_device",     # left the device
    2: "no_field",        # the field could not be read
    3: "low_field",       # field not above min_field_strength
    4: "step_limit",      # reached the step limit of a carrier
    5: "collected",       # reached the readout electrode, or entered a region taken as metal
}

# where resistivity and field are both low is taken as metal: a carrier there is collected
metal_resistivity = 10 # ohm cm; below it the resistivity is low
thermal_length = 1e-4 # cm; the field is low when its potential drop over this length is below the thermal voltage

logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger.setLevel(logging.INFO)

class VectorizedCarrierSystem:
    """The carriers of one kind of an event, drifted together; replaces CarrierCluster."""
    
    def __init__(self, all_positions, all_charges, all_times, all_signals, material, carrier_type="electron", 
                read_out_contact=None, my_d=None, keep_drift_paths=True, diffusion=True):
        # check the input
        self._validate_inputs(all_positions, all_charges, all_times)
            
        # the arrays
        self.positions = np.array(all_positions, dtype=np.float64)
        self.charges = np.array(all_charges, dtype=np.float64)
        self.times = np.array(all_times, dtype=np.int32)
        self.active = np.ones(len(all_charges), dtype=bool)
        self.end_conditions = np.zeros(len(all_charges), dtype=np.int8)
        self.steps_drifted = np.zeros(len(all_charges), dtype=np.int32)
        self.carrier_type = carrier_type
        self.read_out_contact = read_out_contact
        self.my_d = my_d
        self.keep_drift_paths = bool(keep_drift_paths)
        self.diffusion = bool(diffusion)
        
        # parameters and paths
        self._params = self._initialize_params(my_d)
        self._initialize_other_attributes(all_positions)
        self._boundary_log_count = 0
        
        # physical constants
        self.kboltz = 8.617385e-5
        self.e0 = 1.60217733e-19
        self.mobility = Material(my_d.material).cal_mobility
        self._mobility_cache = {}

        # statistics of the run
        self.performance_stats = {
            'total_steps': 0,
            'field_calculations': 0,
            'boundary_checks': 0,
            'carriers_terminated': 0,
            'low_field_terminations': 0,
            'boundary_terminations': 0,
            'collection_terminations': 0
        }
        
        # the signals
        self.signals = self._initialize_signal_storage_per_carrier(len(all_charges), read_out_contact)
        self._signal_warning_logged = False
        
        logger.info(f"carrier system: {len(all_charges)} {carrier_type}")
        logger.info(f"detector size: {my_d.l_x:.1f} x {my_d.l_y:.1f} x {my_d.l_z:.1f} um")

    @staticmethod
    def _scalar_float(value, name):
        array_value = np.asarray(value)
        if array_value.size != 1:
            raise ValueError(f"{name} must be scalar, got shape {array_value.shape}")
        return float(array_value.reshape(-1)[0])

    def _initialize_params(self, my_d):
        params = {}
        try:
            if my_d is not None:
                params['temperature'] = self._get_param(my_d, 'temperature', 300.0)
                params['field_resolution'] = self._resolve_field_resolution(my_d)
                params['boundary_tolerance'] = self._resolve_boundary_tolerance(
                    my_d, params['field_resolution']
                )
                params['max_drift_time'] = 100e-9   # longest drift time
                params['min_field_strength'] = self._resolve_min_field_strength(my_d)
                params['max_vector_steps'] = self._get_param(my_d, 'vector_max_steps', 200000, param_type=int)
                params["collection_weighting_epsilon"] = (
                    self._resolve_collection_weighting_epsilon(my_d)
                )
                
                logger.info("parameters read from the detector")
                
        except Exception as e:
            logger.error(f"reading parameters from the detector failed: {e}")
            raise e
            
        return params
    
    def _get_param(self, my_d, param_name, default, param_type=float):
        """A parameter of the detector, or the default."""
        try:
            value = getattr(my_d, param_name, default)
            return param_type(value)
        except (TypeError, ValueError) as e:
            logger.warning(f"parameter {param_name} cannot be converted, using the default {default}: {e}")
            return default

    def _initialize_other_attributes(self, all_positions):
        """Start the reduced positions and the paths."""
        # reduced_positions
        self.reduced_positions = np.zeros((len(all_positions), 2), dtype=np.float64)
        
        # the paths
        self.paths = [[] for _ in range(len(all_positions))] if self.keep_drift_paths else []
        self.paths_reduced = [[] for _ in range(len(all_positions))]
        
        # the first point of the path of every carrier
        for i, pos in enumerate(all_positions):
            x, y, z = pos
            t = self.times[i]
            
            # full path
            if self.keep_drift_paths:
                self.paths[i].append([x, y, z, t])
            
            # path in reduced coordinates
            x_reduced, y_reduced = self._calculate_reduced_coords(x, y, self.my_d)
            x_num, y_num = self._calculate_electrode_numbers(x, y, self.my_d)
            self.paths_reduced[i].append([x_reduced, y_reduced, z, t, x_num, y_num])
            
            # the reduced coordinates
            self.reduced_positions[i] = [x_reduced, y_reduced]
    
    def _initialize_signal_storage_per_carrier(self, n_carriers, read_out_contact):
        """An empty list of signals for every carrier."""
        if read_out_contact and len(read_out_contact) == 1:
            try:
                x_span = read_out_contact[0].get('x_span', 0)
                y_span = read_out_contact[0].get('y_span', 0)
                # every carrier has signals on (2*x_span+1)*(2*y_span+1) electrodes
                n_electrodes = (2 * x_span + 1) * (2 * y_span + 1)
                # one entry per carrier: its signals on all electrodes (empty for now)
                return [[] for _ in range(n_carriers)]
            except:
                # by default every carrier has signals on one electrode
                return [[] for _ in range(n_carriers)]
        else:
            # every electrode listed: every carrier has signals on len(read_out_contact) electrodes
            n_electrodes = len(read_out_contact) if read_out_contact else 1
            return [[] for _ in range(n_carriers)]

    def _validate_inputs(self, positions, charges, times):
        """Check the input."""
        if len(positions) == 0:
            raise ValueError("the list of carrier positions is empty")
        if len(positions) != len(charges) or len(positions) != len(times):
            raise ValueError("positions, charges and times differ in length")
        
        # check the positions
        for i, pos in enumerate(positions):
            if len(pos) != 3:
                raise ValueError(f"position {i} is not [x, y, z]")
            x, y, z = pos
            if math.isnan(x) or math.isnan(y) or math.isnan(z):
                raise ValueError(f"position {i} contains NaN")
    
    def _resolve_field_resolution(self, my_d):
        """The field resolution used for the cache and the tolerance."""
        resolution = getattr(my_d, "vector_field_resolution", None)
        if resolution is None:
            resolution = getattr(my_d, "field_resolution", None)
        try:
            resolution = float(resolution)
        except (TypeError, ValueError):
            resolution = None
        if resolution is None or resolution <= 0:
            resolution = tolerance_default
        return resolution

    def _resolve_boundary_tolerance(self, my_d, field_res):
        """The boundary tolerance, from the detector or the field resolution."""
        custom_tol = getattr(my_d, "vector_boundary_tolerance", None)
        try:
            if custom_tol is not None:
                custom_tol = float(custom_tol)
        except (TypeError, ValueError):
            custom_tol = None
        if custom_tol is not None and custom_tol > 0:
            logger.info("boundary tolerance set by the user: %.2f um", custom_tol)
            return custom_tol

        tolerance = max(tolerance_default, field_res)
        logger.info(
            "boundary tolerance: %.2f um (field_res=%.2f)",
            tolerance, field_res
        )
        return tolerance

    def _resolve_min_field_strength(self, my_d):
        """The field at or below which a carrier stops."""
        custom_min_field = getattr(my_d, "vector_min_field_strength", None)
        try:
            if custom_min_field is not None:
                custom_min_field = float(custom_min_field)
        except (TypeError, ValueError):
            logger.warning(
                "parameter vector_min_field_strength cannot be converted, using the default 1.0 V/cm: %s",
                custom_min_field
            )
            custom_min_field = None
        if custom_min_field is not None and custom_min_field > 0:
            logger.info("minimum field set by the user: %.2f V/cm", custom_min_field)
            return custom_min_field
        return 1.0

    def _resolve_collection_weighting_epsilon(self, my_d):
        value = getattr(my_d, "vector_collection_weighting_epsilon", None)
        if value is None and hasattr(my_d, "device_dict"):
            value = my_d.device_dict.get("vector_collection_weighting_epsilon")
        if value is None:
            return 5e-3
        value = float(value)
        if not 0 < value < 0.5:
            raise ValueError(
                "vector_collection_weighting_epsilon must be between 0 and 0.5"
            )
        return value
    
    def _calculate_reduced_coords(self, x, y, my_d):
        """The reduced coordinates."""
        # reduced coordinates are not used for now: the field and the boundary take the global ones
        return x, y

    def _should_terminate_at_contact(self, my_f, x_reduced, y_reduced, z):
        if not self.read_out_contact or len(self.read_out_contact) != 1:
            return False
        potential = my_f.get_w_p_cached(x_reduced, y_reduced, z, 0)
        if potential is None:
            raise RuntimeError("Weighting potential is required for contact collection")
        return potential >= 1.0 - self._params["collection_weighting_epsilon"]
    
    def _drifts_toward_contact(self, my_f, my_d, x, y, x_reduced, y_reduced, z, delta_x, delta_y, delta_z):
        # one step leaves the device: near the readout electrode that can only be crossing its surface
        if not (
            0.0 <= x + delta_x <= my_d.l_x
            and 0.0 <= y + delta_y <= my_d.l_y
            and 0.0 <= z + delta_z <= my_d.l_z
        ):
            return True
        before = my_f.get_w_p_cached(x_reduced, y_reduced, z, 0)
        after = my_f.get_w_p_cached(
            x_reduced + delta_x, y_reduced + delta_y, z + delta_z, 0
        )
        if before is None or after is None:
            raise RuntimeError("Weighting potential is required for contact collection")
        return after > before
    
    def _calculate_electrode_numbers(self, x, y, my_d):
        """The numbers of the electrode over the position."""
        try:
            x_num = int((x - my_d.l_x/2 + (my_d.x_ele_num%2)*my_d.p_x/2.0) // my_d.p_x + my_d.x_ele_num/2)
            y_num = int((y - my_d.l_y/2 + (my_d.y_ele_num%2)*my_d.p_y/2.0) // my_d.p_y + my_d.y_ele_num/2)
            return x_num, y_num
        except Exception as e:
            logger.warning(f"the electrode number cannot be calculated, using the default: {e}")
            # the central electrode
            return my_d.x_ele_num//2, my_d.y_ele_num//2

    def _check_boundary_conditions(self, x, y, z, my_d):
        """Whether the position is outside the device."""
        l_x, l_y, l_z = my_d.l_x, my_d.l_y, my_d.l_z
        tolerance = self._params['boundary_tolerance']
        
        # the boundary with its tolerance
        out_of_bound = (x <= -tolerance or x >= l_x + tolerance or 
                       y <= -tolerance or y >= l_y + tolerance or 
                       z <= -tolerance or z >= l_z + tolerance)

        if out_of_bound and self._boundary_log_count < 10:
            self._boundary_log_count += 1
            logger.info(
                "%s left the device #%d: (x=%.3f, y=%.3f, z=%.3f) um, tolerance=%.2f, box=(%.2f, %.2f, %.2f)",
                self.carrier_type, self._boundary_log_count, x, y, z,
                tolerance, l_x, l_y, l_z
            )
        
        return out_of_bound

    def drift_batch(self, my_d, my_f, delta_t=1e-12, max_steps=None):
        """Drift all carriers until they stop."""
        params = self._params
        max_drift_time = params.get('max_drift_time', 0.0)
        if self.performance_stats['total_steps'] == 0:
            logger.debug(
                "drift parameters: boundary_tolerance=%.2f um, field_resolution=%.2f um",
                params.get('boundary_tolerance', -1.0),
                params.get('field_resolution', -1.0)
            )

        if delta_t <= 0:
            raise ValueError("delta_t must be positive for drift simulation")

        target_steps = int(math.ceil(max_drift_time / delta_t)) if max_drift_time > 0 else 0
        planned_steps = max(target_steps, 1)
        if max_steps is not None and max_steps > 0:
            planned_steps = max(planned_steps, int(max_steps))

        max_vector_steps = int(params.get('max_vector_steps', 200000))
        if planned_steps > max_vector_steps:
            logger.debug(
                "drift steps reduced: asked=%s, limit=%s (max_vector_steps)",
                planned_steps, max_vector_steps
            )
            planned_steps = max_vector_steps

        logger.info(
            f"drifting {self.carrier_type}: time step {delta_t}s, planned steps {planned_steps} "
            f"(max_drift_time={max_drift_time:.2e}s)"
        )
        
        start_time = time.time()
        
        total_carriers = len(self.active)
        initial_active = np.sum(self.active)
        
        logger.info(f"at the start: {initial_active}/{total_carriers} carriers active")
        
        active_indices = np.arange(total_carriers)

        for step in range(planned_steps):
            if step % 100 == 0:
                self._log_progress_drift(step, total_carriers)
            
            n_terminated = self.drift_step_batch(my_d, my_f, delta_t, step, active_indices)
            self.performance_stats['total_steps'] += 1
            active_indices = active_indices[self.active[active_indices]]
            
            if len(active_indices) == 0:
                logger.info("all carriers stopped")
                break
        else:
            remaining = int(np.sum(self.active))
            if remaining > 0:
                logger.warning(
                    "%s carriers had not stopped when the drift steps ran out; max_drift_time or max_vector_steps may be raised",
                    remaining
                )
        executed_steps = min(self.performance_stats['total_steps'], planned_steps)
        
        self._log_final_stats(start_time, executed_steps)
        return True

    def drift_step_batch(self, my_d, my_f, delta_t, step=0, active_indices=None):
        """Move every active carrier by one step."""
        if active_indices is None:
            active_indices = np.flatnonzero(self.active)
        if len(active_indices) == 0:
            return 0
            
        n_terminated = 0
        params = self._params
        
        for idx in active_indices:
            x, y, z = self.positions[idx]
            x_reduced, y_reduced = self.reduced_positions[idx]
            charge = self.charges[idx]
            
            # outside the device
            self.performance_stats['boundary_checks'] += 1
            if self._check_boundary_conditions(x, y, z, my_d):
                self.active[idx] = False
                self.end_conditions[idx] = 1
                n_terminated += 1
                self.performance_stats['boundary_terminations'] += 1
                continue
            
            # step limit
            #if self.times[idx] > params['max_drift_time']:
            if self.steps_drifted[idx] >= params['max_vector_steps']:
                self.active[idx] = False
                self.end_conditions[idx] = 4
                n_terminated += 1
                continue
            
            # the field
            e_field = self._get_e_field_reduced(my_f, x, y, z, idx, x_reduced, y_reduced)
            if e_field is None:
                continue
                
            Ex, Ey, Ez = e_field
            intensity = math.sqrt(Ex*Ex + Ey*Ey + Ez*Ez)
            
            # low field
            if intensity <= params['min_field_strength']:
                self.active[idx] = False
                self.end_conditions[idx] = 3
                n_terminated += 1
                self.performance_stats['low_field_terminations'] += 1
                continue
            
            # mobility
            try:
                doping = self._scalar_float(
                    my_f.get_doping_cached(x_reduced, y_reduced, z),
                    "doping",
                )
                intensity = self._scalar_float(intensity, "electric field intensity")
                mobility_key = (params['temperature'], doping, bool(charge > 0), intensity)
                if mobility_key in self._mobility_cache:
                    mu = self._mobility_cache[mobility_key]
                else:
                    mu = self.mobility(params['temperature'], doping, charge, intensity)
                    self._mobility_cache[mobility_key] = mu
                diffusion_constant = math.sqrt(2.0 * self.kboltz * params['temperature'] * mu * delta_t) * 1e4
            except Exception as e:
                raise RuntimeError(f"the mobility cannot be calculated: {e}")

            # resistivity and field both low: inside a region taken as metal, collected
            if (
                intensity < self.kboltz * params['temperature'] / thermal_length
                and self._resistivity(doping, params['temperature'], intensity) < metal_resistivity
            ):
                self.active[idx] = False
                self.end_conditions[idx] = 5
                n_terminated += 1
                self.performance_stats['collection_terminations'] += 1
                continue
            
            # drift displacement
            delta_x, delta_y, delta_z = self._calculate_displacement(charge, e_field, mu, delta_t)
            
            # diffusion displacement
            if self.diffusion:
                dif_x, dif_y, dif_z = self._calculate_diffusion(diffusion_constant)
            else:
                dif_x, dif_y, dif_z = 0.0, 0.0, 0.0
            
            # the new position
            self._update_carrier_position(idx, delta_x, delta_y, delta_z, dif_x, dif_y, dif_z)

            new_x_reduced, new_y_reduced = self.reduced_positions[idx]
            new_z = self.positions[idx][2]
            if self._check_boundary_conditions(
                self.positions[idx][0], self.positions[idx][1], new_z, my_d
            ):
                self._clamp_position_to_device(idx, my_d)
                new_x_reduced, new_y_reduced = self.reduced_positions[idx]
                new_z = self.positions[idx][2]
                if self._should_terminate_at_contact(
                    my_f, new_x_reduced, new_y_reduced, new_z
                ):
                    self.end_conditions[idx] = 5
                    self.performance_stats["collection_terminations"] += 1
                else:
                    self.end_conditions[idx] = 1
                    self.performance_stats["boundary_terminations"] += 1
                self.active[idx] = False
                n_terminated += 1
                continue
            # only carriers drifting toward the readout electrode are collected; those drifting away (holes created near it) go on
            if self._should_terminate_at_contact(
                my_f, new_x_reduced, new_y_reduced, new_z
            ) and self._drifts_toward_contact(
                my_f, my_d, x, y, x_reduced, y_reduced, z, delta_x, delta_y, delta_z
            ):
                self.active[idx] = False
                self.end_conditions[idx] = 5
                self.performance_stats["collection_terminations"] += 1
                n_terminated += 1
        
        self.performance_stats['carriers_terminated'] += n_terminated
        return n_terminated

    def _resistivity(self, doping, temperature, intensity):
        """Local resistivity [ohm cm]: 1 / (e |net doping| majority mobility); positive doping [cm^-3] is n type."""
        if doping == 0:
            return math.inf
        majority_charge = -1 if doping > 0 else 1
        mu = self.mobility(temperature, doping, majority_charge, intensity)
        return 1.0 / (self.e0 * abs(doping) * mu)

    def _clamp_position_to_device(self, idx, my_d):
        x, y, z = self.positions[idx]
        x = min(max(x, 0.0), my_d.l_x)
        y = min(max(y, 0.0), my_d.l_y)
        z = min(max(z, 0.0), my_d.l_z)
        self.positions[idx] = [x, y, z]
        self.reduced_positions[idx] = self._calculate_reduced_coords(x, y, my_d)
        if self.keep_drift_paths:
            self.paths[idx][-1] = [x, y, z, self.times[idx]]
        x_num, y_num = self._calculate_electrode_numbers(x, y, my_d)
        self.paths_reduced[idx][-1] = [
            self.reduced_positions[idx][0],
            self.reduced_positions[idx][1],
            z,
            self.times[idx],
            x_num,
            y_num,
        ]

    def _get_e_field_reduced(self, my_f, x, y, z, idx, field_x=None, field_y=None):
        """The field at the carrier; the carrier stops when it cannot be read."""
        fx = x if field_x is None else field_x
        fy = y if field_y is None else field_y
        try:
            self.performance_stats['field_calculations'] += 1
            e_field = my_f.get_e_field_cached(fx, fy, z)
            if e_field is None or len(e_field) != 3:
                raise ValueError("invalid field value")
            return e_field
        except Exception as e:
            logger.warning(f"carrier {idx}: the field cannot be read: {e}")
            self.active[idx] = False
            self.end_conditions[idx] = 2
            return None

    def _calculate_displacement(self, charge, e_field, mu, delta_t):
        """Drift displacement of one step [um]."""
        Ex, Ey, Ez = e_field
        if charge > 0:  # hole
            vx = Ex * mu
            vy = Ey * mu
            vz = Ez * mu
        else:  # electron
            vx = -Ex * mu
            vy = -Ey * mu
            vz = -Ez * mu
        
        return vx * delta_t * 1e4, vy * delta_t * 1e4, vz * delta_t * 1e4

    def _calculate_diffusion(self, diffusion_constant):
        """Diffusion displacement of one step [um]."""
        generator = stream("drift")
        return (generator.Gaus(0.0, diffusion_constant),
               generator.Gaus(0.0, diffusion_constant), 
               generator.Gaus(0.0, diffusion_constant))

    def _update_carrier_position(self, idx, delta_x, delta_y, delta_z, dif_x, dif_y, dif_z):
        """Move the carrier and extend its path."""
        x, y, z = self.positions[idx]
        
        new_x = x + delta_x + dif_x
        new_y = y + delta_y + dif_y
        new_z = z + delta_z + dif_z
        
        # the coordinates
        self.positions[idx] = [new_x, new_y, new_z]
        self.reduced_positions[idx] = self._calculate_reduced_coords(new_x, new_y, self.my_d)
        self.times[idx] += 1
        self.steps_drifted[idx] += 1
        
        # the path
        if self.keep_drift_paths:
            self.paths[idx].append([new_x, new_y, new_z, self.times[idx]])
        x_num, y_num = self._calculate_electrode_numbers(new_x, new_y, self.my_d)
        self.paths_reduced[idx].append([
            self.reduced_positions[idx][0], self.reduced_positions[idx][1], 
            new_z, self.times[idx], x_num, y_num
        ])

    def _log_progress_drift(self, step, total_carriers):
        """Log the progress."""
        active_count = np.sum(self.active)
        progress = (total_carriers - active_count) / total_carriers * 100
        logger.info(f"  step {step}: {active_count} carriers active ({progress:.1f}% done)")

    def _log_final_stats(self, start_time, max_steps):
        """Log the statistics of the drift."""
        end_time = time.time()
        total_time = end_time - start_time
        final_stats = self.get_statistics()
        perf_stats = self.get_performance_stats()
        
        logger.info(f"drift done: {self.performance_stats['total_steps']} steps in {total_time:.2f} s")
        logger.info(f"at the end: {final_stats['active_carriers']} active, {final_stats['average_steps']:.1f} steps on average")
        logger.info(f"statistics: {perf_stats}")

    def get_statistics(self):
        """Counts of carriers, steps and end conditions."""
        n_total = len(self.active)
        n_active = np.sum(self.active)
        
        if np.any(self.steps_drifted > 0):
            avg_steps = np.mean(self.steps_drifted[self.steps_drifted > 0])
            max_steps = np.max(self.steps_drifted)
        else:
            avg_steps = 0
            max_steps = 0
            
        # end conditions
        end_condition_counts = {
            'boundary': np.sum(self.end_conditions == 1),
            'field_error': np.sum(self.end_conditions == 2),
            'low_field': np.sum(self.end_conditions == 3),
            'timeout': np.sum(self.end_conditions == 4),
            'collection': np.sum(self.end_conditions == 5),
            'active': n_active
        }
        
        return {
            'total_carriers': n_total,
            'active_carriers': n_active,
            'inactive_carriers': n_total - n_active,
            'average_steps': avg_steps,
            'max_steps': max_steps,
            'carrier_type': self.carrier_type,
            'end_conditions': end_condition_counts
        }
    
    def get_performance_stats(self):
        """A copy of the statistics of the run."""
        return self.performance_stats.copy()
    
    def get_signal_batch(self, my_d, my_f, delta_t):
        """Calculate the signals of all carriers."""
        start_time = time.time()
        e0 = 1.60217733e-19
        has_irradiation = my_d.irradiation_model is not None
        
        # for debugging
        logger.info(f"=== signal calculation ===")
        logger.info(f"carrier type: {self.carrier_type}")
        logger.info(f"carriers: {len(self.positions)}")
        logger.info(f"active carriers: {np.sum(self.active)}")
        logger.info(f"readout contacts: {self.read_out_contact}")
        logger.info(f"irradiated: {has_irradiation}")
        
        # the paths
        valid_paths = 0
        for i, path in enumerate(self.paths_reduced):
            if len(path) > 1:
                valid_paths += 1
        
        logger.info(f"paths with steps: {valid_paths}/{len(self.paths_reduced)}")
        
        if valid_paths == 0:
            logger.warning("no carrier has a path with steps; no signal is calculated")
            return
        
        # all carriers
        all_indices = np.arange(len(self.positions))
        
        if len(self.read_out_contact) == 1:
            self._calculate_signal_single_contact(all_indices, my_f, e0, delta_t, has_irradiation, my_d)
        else:
            self._calculate_signal_multi_contact(all_indices, my_f, e0, delta_t, has_irradiation, my_d)
        
        # what was calculated
        total_carriers_with_signals = sum(1 for carrier_signals in self.signals if carrier_signals)
        total_signal_points = self._count_signal_points(self.signals)
        
        logger.info(f"signals done: {total_carriers_with_signals} carriers have signals, {total_signal_points} signal points")
        
        if total_signal_points == 0:
            logger.warning("no signal point was calculated")
        
        end_time = time.time()
        logger.info(f"signals calculated in {end_time - start_time:.2f} s")

    def _count_signal_points(self, values):
        if isinstance(values, (list, tuple)):
            return sum(self._count_signal_points(value) for value in values)
        return 1

    def _calculate_signal_single_contact(self, all_indices, my_f, e0, delta_t, has_irradiation, my_d):
        """Signals where the device lists one electrode."""
        x_span = self.read_out_contact[0]['x_span']
        y_span = self.read_out_contact[0]['y_span']
        p_x = my_d.p_x
        p_y = my_d.p_y
        
        total_electrodes = (2 * x_span + 1) * (2 * y_span + 1)
        logger.info(f"one listed electrode: x_span={x_span}, y_span={y_span}, electrodes={total_electrodes}")
        
        # all carriers
        processed_count = 0
        for carrier_idx in all_indices:
            if self._process_carrier_signal_single(carrier_idx, my_f, e0, delta_t, has_irradiation, 
                                                x_span, y_span, p_x, p_y, total_electrodes):
                processed_count += 1

            if carrier_idx % 10 == 0:
                self._log_progress_signal(carrier_idx, len(all_indices))
        
        # what was calculated
        total_carriers_with_signals = sum(1 for carrier_signals in self.signals if carrier_signals)
        logger.info(f"signals of one listed electrode done: {processed_count} carriers processed, {total_carriers_with_signals} have signals")

    def _process_carrier_signal_single(self, carrier_idx, my_f, e0, delta_t, has_irradiation, 
                                    x_span, y_span, p_x, p_y, total_electrodes):
        """Signals of one carrier where the device lists one electrode."""
        charge = self.charges[carrier_idx]
        path_reduced = self.paths_reduced[carrier_idx]
        
        # a path without steps gives no signal
        if len(path_reduced) <= 1:
            return False
        
        try:
            n_points = len(path_reduced) - 1
            
            # the signals of this carrier on every electrode
            carrier_electrode_signals = [[] for _ in range(total_electrodes)]
            
            # coordinates and times
            x_coords = [point[0] for point in path_reduced[:-1]]
            y_coords = [point[1] for point in path_reduced[:-1]]  
            z_coords = [point[2] for point in path_reduced[:-1]]

            delta_n_x = [path_reduced[i+1][4] - path_reduced[i][4] for i in range(len(path_reduced)-1)]
            delta_n_y = [path_reduced[i+1][5] - path_reduced[i][5] for i in range(len(path_reduced)-1)]
            
            # time differences
            d_times = [path_reduced[i+1][3] - path_reduced[i][3] for i in range(len(path_reduced)-1)]
            
            # every electrode around the carrier
            success_count = 0
            use_local_analytic = isinstance(my_f, AnalyticStripPixelField)
            x_coords_end = [point[0] for point in path_reduced[1:]]
            y_coords_end = [point[1] for point in path_reduced[1:]]
            z_coords_end = [point[2] for point in path_reduced[1:]]
            
            for j in range(2 * x_span + 1):
                x_shift = (j - x_span) * p_x
                for k in range(2 * y_span + 1):
                    y_shift = (k - y_span) * p_y
                    electrode_idx = j * (2 * y_span + 1) + k
                    if use_local_analytic:
                        start_x = [x - x_shift for x in x_coords]
                        start_y = [y - y_shift for y in y_coords]
                        end_x = [x - x_shift for x in x_coords_end]
                        end_y = [y - y_shift for y in y_coords_end]
                    else:
                        start_x = [
                            x - x_shift + dn_x * p_x
                            for x, dn_x in zip(x_coords, delta_n_x)
                        ]
                        start_y = [
                            y - y_shift + dn_y * p_y
                            for y, dn_y in zip(y_coords, delta_n_y)
                        ]
                        end_x = [
                            x - x_shift + dn_x * p_x
                            for x, dn_x in zip(x_coords_end, delta_n_x)
                        ]
                        end_y = [
                            y - y_shift + dn_y * p_y
                            for y, dn_y in zip(y_coords_end, delta_n_y)
                        ]
                    
                    try:
                        # weighting potentials at the starts of the steps
                        U_w_1 = self._get_weighting_potentials_batch(
                            my_f, start_x, start_y, z_coords, 0
                        )
                        
                        # weighting potentials at the ends of the steps
                        U_w_2 = self._get_weighting_potentials_batch(
                            my_f, end_x, end_y, z_coords_end, 0
                        )
                        
                        # potential differences
                        dU_w = [u2 - u1 for u1, u2 in zip(U_w_1, U_w_2)]
                        
                        # trapping
                        if has_irradiation:
                            charges = self._calculate_trapped_charges(
                                charge, x_coords, y_coords, z_coords, d_times, delta_t, my_f
                            )
                        else:
                            charges = [charge] * n_points
                        
                        # the signals
                        signals = [q * e0 * du for q, du in zip(charges, dU_w)]
                        
                        # kept under the electrode of this carrier
                        carrier_electrode_signals[electrode_idx] = signals
                        success_count += 1
                        
                    except Exception as e:
                        if not self._signal_warning_logged:
                            carrier_type = "hole" if charge > 0 else "electron"
                            logger.warning("%s carrier %d electrode %d: the signal cannot be calculated: %s", carrier_type, carrier_idx, electrode_idx, e)
                            self._signal_warning_logged = True
                        raise
            
            # the signals of this carrier on all electrodes
            if success_count > 0:
                self.signals[carrier_idx] = carrier_electrode_signals
            
            return success_count > 0
            
        except Exception as e:
            raise RuntimeError(f"signals of carrier {carrier_idx} failed: {e}") from e
     
    def _calculate_signal_multi_contact(self, all_indices, my_f, e0, delta_t, has_irradiation, my_d):
        """Signals where the device lists every electrode."""
        n_electrodes = len(self.read_out_contact)
        
        logger.info(f"signals on {n_electrodes} listed electrodes")
        
        # all carriers
        processed_count = 0
        for carrier_idx in all_indices:
            if self._process_carrier_signal_multi(carrier_idx, my_f, e0, delta_t, has_irradiation, n_electrodes):
                processed_count += 1

            if carrier_idx % 10 == 0:
                self._log_progress_signal(carrier_idx, len(all_indices))
        
        # what was calculated
        total_signal_points = self._count_signal_points(self.signals)
        non_empty_carriers = sum(1 for carrier_signals in self.signals if carrier_signals)
        
        logger.info(f"signals of listed electrodes done: {processed_count} carriers processed, {n_electrodes} electrodes")
        logger.info(f"carriers with signals: {non_empty_carriers}/{len(self.positions)}, {total_signal_points} signal points")

    def _process_carrier_signal_multi(self, carrier_idx, my_f, e0, delta_t, has_irradiation, n_electrodes):
        """Signals of one carrier where the device lists every electrode; whether any was calculated."""
        charge = self.charges[carrier_idx]
        path_reduced = self.paths_reduced[carrier_idx]
        
        if len(path_reduced) <= 1:
            return False
        
        try:
            n_points = len(path_reduced) - 1
            
            # for debugging
            if carrier_idx < 5:  # only the first carriers
                logger.debug(f"carrier {carrier_idx}: charge={charge}, path points={len(path_reduced)}")
            
            # coordinates and times
            x_coords = [point[0] for point in path_reduced[:-1]]
            y_coords = [point[1] for point in path_reduced[:-1]]
            z_coords = [point[2] for point in path_reduced[:-1]]
            times = [point[3] for point in path_reduced[:-1]]
            d_times = [path_reduced[i+1][3] - path_reduced[i][3] for i in range(len(path_reduced)-1)]
            
            # the signals on every electrode
            success_count = 0
            electrode_signals = []  # signals by electrode
            
            for j in range(n_electrodes):
                try:
                    # weighting potentials at the starts of the steps
                    U_w_1 = self._get_weighting_potentials_batch(
                        my_f, x_coords, y_coords, z_coords, j
                    )
                    
                    # weighting potentials at the ends of the steps
                    x_coords_end = [point[0] for point in path_reduced[1:]]
                    y_coords_end = [point[1] for point in path_reduced[1:]]
                    z_coords_end = [point[2] for point in path_reduced[1:]]
                    
                    U_w_2 = self._get_weighting_potentials_batch(
                        my_f, x_coords_end, y_coords_end, z_coords_end, j
                    )
                    
                    # potential differences
                    dU_w = [u2 - u1 for u1, u2 in zip(U_w_1, U_w_2)]
                    
                    # the weighting potentials, for debugging
                    if carrier_idx < 3 and j < 3:  # the first carriers and electrodes
                        logger.debug(f"electrode {j} weighting potential: U_w_1={U_w_1[:3]}, U_w_2={U_w_2[:3]}, dU_w={dU_w[:3]}")
                    
                    # trapping
                    if has_irradiation:
                        charges = self._calculate_trapped_charges(
                            charge, x_coords, y_coords, z_coords, d_times, delta_t, my_f
                        )
                    else:
                        charges = [charge] * n_points
                    
                    # the signals
                    signals = [q * e0 * du for q, du in zip(charges, dU_w)]
                    
                    # the signals, for debugging
                    if carrier_idx < 3 and j < 3 and any(s != 0 for s in signals[:3]):
                        logger.debug(f"electrode {j} signals: {signals[:3]}")
                    
                    # keep the signals
                    electrode_signals.append(signals)
                    
                    success_count += 1
                    
                except Exception as e:
                    if not getattr(self, '_signal_warning_logged', False):
                        carrier_type = "hole" if charge > 0 else "electron"
                        logger.warning("%s carrier %d electrode %d: the signal cannot be calculated: %s", carrier_type, carrier_idx, j, e)
                        self._signal_warning_logged = True
                    raise
            
            # counts of the signals of this carrier
            if electrode_signals and carrier_idx < 3:
                total_signals = sum(len(sigs) for sigs in electrode_signals)
                non_zero_total = sum(1 for sigs in electrode_signals for s in sigs )
                logger.debug(f"carrier {carrier_idx}: signals={total_signals}, non-zero signals={non_zero_total}")

            if success_count > 0:
                self.signals[carrier_idx] = electrode_signals
            
            return success_count > 0
            
        except Exception as e:
            raise RuntimeError(
                f"signals of carrier {carrier_idx} on the listed electrodes failed: {e}"
            ) from e
    
    def _get_weighting_potentials_batch(self, my_f, x_coords, y_coords, z_coords, electrode_idx):
        """Weighting potentials at the points of a path."""
        potentials = []
        
        for i in range(len(x_coords)):
            try:
                potential = my_f.get_w_p_cached(x_coords[i], y_coords[i], z_coords[i], electrode_idx)
            except Exception as e:
                raise RuntimeError(
                    f"no weighting potential at ({x_coords[i]}, {y_coords[i]}, {z_coords[i]}), electrode {electrode_idx}: {e}"
                ) from e
            if potential is None:
                raise RuntimeError(
                    f"no weighting potential at ({x_coords[i]}, {y_coords[i]}, {z_coords[i]}), "
                    f"electrode {electrode_idx}: returned None"
                )

            potentials.append(potential)
            
            if i < 3 and len(potentials) < 10:
                logger.debug(f"weighting potential[{i}]: ({x_coords[i]:.1f}, {y_coords[i]:.1f}, {z_coords[i]:.1f}) -> {potential:.6f}")
        return potentials

    def _calculate_trapped_charges(self, initial_charge, x_coords, y_coords, z_coords, d_times, delta_t, my_f):
        """Charge left after trapping at every step of a path."""
        n_points = len(x_coords)
        
        # trapping rates
        trapping_rates = []
        for i in range(n_points):
            if initial_charge >= 0:  # hole
                trapping_rate = my_f.get_trap_h_cached(x_coords[i], y_coords[i], z_coords[i])
            else:  # electron
                trapping_rate = my_f.get_trap_e_cached(x_coords[i], y_coords[i], z_coords[i])
            trapping_rates.append(trapping_rate)
        
        # accumulated decay
        decay_factors = []
        cumulative_factor = 0.0
        for i in range(n_points):
            cumulative_factor += trapping_rates[i] * d_times[i] * delta_t
            decay_factors.append(math.exp(-cumulative_factor))
        
        return [initial_charge * factor for factor in decay_factors]
    
    def _log_progress_signal(self, carrier_idx, len_all_indices):
        """Log the progress."""
        progress = carrier_idx / len_all_indices * 100
        logger.info(f"signals of carrier {carrier_idx} calculated ({progress:.1f}% done)")
