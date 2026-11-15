"""One event: from the waveforms of its electrodes to its quantities."""

import numpy as np

CFD = 0.5 # partition
CFD_LABEL = "CFD50"
#TODO: get threshold and CFD from electronics setting

class InputWaveform:
    """
    ToA : time of arrival
    ToT : time over threshold
    amplitude : peak amplitude for charge sensitive preamp
    charge : total charge for current sensitive preamp
    CFD50 : time at 50% constant-fraction discriminator crossing

    voltage : (electrodes, bins), the value of each electrode at the centre
        of each time bin; the thresholds are in its unit
    t0 : left edge of the first time bin [s]
    dt : width of a time bin [s]
    original_x : x of the track, in the unit of pitch_x
    """
    def __init__(self, voltage, t0, dt, original_x, threshold, amplitude_threshold, pitch_x, pitch_y, CFD=CFD,):
        read_ele_num = len(voltage)
        times = t0 + (np.arange(len(voltage[0])) + 0.5) * dt
        self.times = times # centres of the time bins
        self.waveforms = [None for _ in range(read_ele_num)]
        self.read_ele_num = read_ele_num
        self.pitch_x = pitch_x
        self.pitch_y = pitch_y
        self.CFD = CFD
        self.peak_time = [0 for i in range(read_ele_num)]
        self.ToA = [0 for i in range(read_ele_num)]
        self.ToT = [0 for i in range(read_ele_num)]
        self.amplitude = [0 for i in range(read_ele_num)] # for charge sensitive pre amp
        self.charge = [0 for i in range(read_ele_num)] # for current sensitive pre amp
        self.CFD50 = [0 for i in range(read_ele_num)]
        self.threshold = threshold
        self.amplitude_threshold = amplitude_threshold

        self.original_x = original_x

        for i in range(read_ele_num):
            # only available for strip detector
            self.waveforms[i] = voltage[i]
            self.amplitude[i], self.peak_time[i] = get_amplitude(self.waveforms[i])
            if self.amplitude[i] < self.threshold:
                self.amplitude[i] = 0
                self.ToA[i] = None
                self.ToT[i] = 0
                self.charge[i] = 0
                self.CFD50[i] = None
            else:
                self.ToA[i] = get_ToA(times, self.waveforms[i], self.threshold, self.peak_time[i])
                self.ToT[i] = get_ToT(times, self.waveforms[i], self.threshold, self.peak_time[i])
                self.charge[i] = get_charge(self.waveforms[i])
                self.CFD50[i] = get_CFD50(times, self.waveforms[i], CFD, self.peak_time[i])

        self.get_total_data()

    def get_total_data(self):
        self.data = {}
        if max(self.amplitude) < self.amplitude_threshold:
            self.data["ToA"] = None
            self.data["ToT"] = None
            self.data["amplitude"] = None
            self.data["charge"] = None
            self.data[CFD_LABEL] = None
            self.data["gravity_center_ToT"] = None
            self.data["gravity_center_amplitude"] = None
            self.data["gravity_center_charge"] = None
            self.data["cluster_size_ToT"] = 0
            self.data["cluster_size_amplitude"] = 0
            self.data["cluster_charge"] = 0
            self.data["gravity_center_ToT_error"] = None
            self.data["gravity_center_amplitude_error"] = None
            self.data["gravity_center_charge_error"] = None
        elif self.read_ele_num == 1:
            self.data["ToA"] = self.ToA[0]
            self.data["ToT"] = self.ToT[0]
            self.data["amplitude"] = self.amplitude[0]
            self.data["charge"] = self.charge[0]
            self.data[CFD_LABEL] = self.CFD50[0]
            self.data["gravity_center_ToT"] = 0 # No spacial resolution
            self.data["gravity_center_amplitude"] = 0
            self.data["gravity_center_charge"] = 0
            self.data["cluster_size_ToT"] = 1
            self.data["cluster_size_amplitude"] = 1
            self.data["cluster_charge"] = 1
            self.data["gravity_center_ToT_error"] = 0
            self.data["gravity_center_amplitude_error"] = 0
            self.data["gravity_center_charge_error"] = 0
        else:
            # assume strip, one dimensional spacial resolution
            self.data["ToA"] = get_conjoined_time(self.ToA, self.amplitude) # TODO: conjoint measurement
            self.data["ToT"] = get_total_amp(self.ToT, 10e-9)
            self.data["amplitude"] = get_total_amp(self.amplitude, self.amplitude_threshold)
            self.data["charge"] = get_total_amp(self.charge, 0.0)
            self.data[CFD_LABEL] = get_conjoined_time(self.CFD50, self.amplitude) # TODO: conjoint measurement
            self.data["gravity_center_ToT"], self.data["cluster_size_ToT"] = ( get_gravity_center_and_cluster_size(self.ToT, 10e-9)
            )  # TODO: assign a proper value for all DAQ systems
            ( # TODO: assign a proper value for all DAQ systems
            self.data["gravity_center_amplitude"], self.data["cluster_size_amplitude"],
            ) = get_gravity_center_and_cluster_size(self.amplitude, self.amplitude_threshold)
            self.data["gravity_center_charge"], self.data["cluster_charge"] = ( get_gravity_center_and_cluster_size(self.charge, 0.0)) # TODO: assign a proper value for all DAQ systems

            if self.data["gravity_center_ToT"] != None:
                self.data["gravity_center_ToT_error"] = ( self.data["gravity_center_ToT"] - self.original_x/self.pitch_x
                )
            else:
                self.data["gravity_center_ToT_error"] = None
            if self.data["gravity_center_amplitude"] != None:
                self.data["gravity_center_amplitude_error"] = ( self.data["gravity_center_amplitude"] - self.original_x/self.pitch_x
                )
            else:
                self.data["gravity_center_amplitude_error"] = None
            if self.data["gravity_center_charge"] != None:
                self.data["gravity_center_charge_error"] = ( self.data["gravity_center_charge"] - self.original_x/self.pitch_x
                )
            else:
                self.data["gravity_center_charge_error"] = None

        self.data["original_x"] = self.original_x

def get_ToA(times, samples, threshold, peak):
    """Centre of the first bin below the threshold, going back from the bin `peak`."""
    for i in range(peak, -1, -1):
        if abs(samples[i]) < threshold:
            return times[i]
    return None

def get_ToT(times, samples, threshold, peak):
    """From the first bin below the threshold before the bin `peak` to the first after it."""
    start = None
    for i in range(peak, -1, -1):
        if abs(samples[i]) < threshold:
            start = times[i]
            break
    if start is None:
        return 0.0
    end = None
    for i in range(peak, len(samples)):
        if abs(samples[i]) < threshold:
            end = times[i]
            break
    if end is None:
        return 0.0
    return end - start

def get_amplitude(samples):
    """Largest absolute value and the bin it is in."""
    peak = int(np.argmax(np.abs(samples)))
    return abs(samples[peak]), peak

def get_charge(samples):
    return np.sum(np.abs(samples))

def get_CFD50(times, samples, CFD, peak):
    """Where the rising edge crosses the fraction CFD of the value in the bin
    `peak`, on the line between the two bin centres around it."""
    amplitude = abs(samples[peak])
    target = amplitude * CFD
    if amplitude <= 0:
        return None
    for i in range(peak, 0, -1):
        previous_content = abs(samples[i - 1])
        content = abs(samples[i])
        if previous_content <= target <= content:
            if content == previous_content:
                return times[i - 1]
            fraction = (target - previous_content) / (content - previous_content)
            return times[i - 1] + fraction * (times[i] - times[i - 1])
    return None

def get_CoG(times, samples, threshold, peak):
    """Centre of gravity in time of the pulse: the centres of the bins above
    the threshold around the bin `peak`, weighted by their absolute values."""
    first = peak
    while first > 0 and abs(samples[first - 1]) >= threshold:
        first -= 1
    last = peak
    while last < len(samples) - 1 and abs(samples[last + 1]) >= threshold:
        last += 1
    weights = np.abs(samples[first:last + 1])
    return np.sum(times[first:last + 1] * weights) / np.sum(weights)

def get_conjoined_time(time_list, amplitude_list=None):
    # TODO: conjoint measurement
    if amplitude_list is None:
        new_list = remove_none(time_list)
        if len(new_list) == 0:
            return None
        return min(new_list)
    valid_indices = [
        index
        for index, value in enumerate(time_list)
        if value is not None and amplitude_list[index] > 0
    ]
    if not valid_indices:
        return None
    selected = max(valid_indices, key=lambda index: amplitude_list[index])
    return time_list[selected]

def get_total_amp(amp_list, amp_thres):
    max_amp = max(amp_list)
    i_max = amp_list.index(max_amp)
    if max_amp == 0:
        return None
    seeds = set()
    for i in range(len(amp_list)):
        if amp_list[i] > amp_thres:
            seeds.add(i)
    if len(seeds) == 0:
        return None
    new_seeds = set()
    for i in seeds:
        new_seeds.add(i)
        if i > 0 and amp_list[i-1] > 0:
            new_seeds.add(i-1)
        if i < len(amp_list) - 1 and amp_list[i+1] > 0:
            new_seeds.add(i+1)
    return sum([amp_list[i] for i in new_seeds])

def get_gravity_center_and_cluster_size(amp_list, amp_thres):
    max_amp = max(amp_list)
    i_max = amp_list.index(max_amp)
    if max_amp == 0:
        return None, 0
    seeds = set()
    for i in range(len(amp_list)):
        if amp_list[i] > amp_thres:
            seeds.add(i)
    if len(seeds) == 0:
        return None, 0
    new_seeds = set()
    for i in seeds:
        new_seeds.add(i)
        if i > 0 and amp_list[i-1] > 0:
            new_seeds.add(i-1)
        if i < len(amp_list) - 1 and amp_list[i+1] > 0:
            new_seeds.add(i+1)
    return sum([i * amp_list[i] for i in new_seeds]) / sum(amp_list[i] for i in new_seeds), len(new_seeds)

def remove_none(list):
    new_list = []
    for i in list:
        if i == None:
            continue
        new_list.append(i)
    return new_list
