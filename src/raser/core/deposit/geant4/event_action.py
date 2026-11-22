'''
Description:  event_action.py
@Date       : 2025
@Author     : Yuhang Tan, Chenxi Fu (Original: Geant4)
@version    : 2.0
'''

from raser.core.deposit.geant4.g4ppyy_runtime import g4b

from ..recording import event_recorded

g4b.include("G4UserEventAction.hh")
g4b.include("G4RunManager.hh")

class GeneralEventAction(g4b.G4UserEventAction):
    "My Event Action"
    def __init__(self, runAction, records, windows, tree, coincidence_window_ns, recorded_events=None):
        super().__init__()
        # the run stops when this many events are recorded; None: it does not
        self.recorded_events = recorded_events
        self.recorded = 0
        self.ended = 0
        # the first this many recorded events are kept for the picture of the run
        self.drawn = 0
        self.fRunAction = runAction
        # records: the RecordedSteps the recorded events are put into
        self.records = records
        self.slots = records.slots
        # whether an event is recorded: the energy windows [MeV] of the
        # slots, the parsed logic expression over them and its window in time [ns]
        self.windows = windows
        self.tree = tree
        self.coincidence_window_ns = coincidence_window_ns

    def BeginOfEventAction(self, event):
        self.p_step: dict[str, list] = {slot: [] for slot in self.slots}
        self.start_step: dict[str, list] = {slot: [] for slot in self.slots}
        self.energy_step: dict[str, list] = {slot: [] for slot in self.slots}
        self.time_step: dict[str, list] = {slot: [] for slot in self.slots}

    def EndOfEventAction(self, event):
        eventID = event.GetEventID()
        self.ended += 1
        if not self.in_condition():
            return
        self.save_geant4_events(eventID)
        self.recorded += 1
        if self.recorded <= self.drawn:
            g4b.G4EventManager.GetEventManager().KeepTheCurrentEvent()
        if self.recorded == self.recorded_events:
            g4b.G4RunManager.GetRunManager().AbortRun(True)

    def in_condition(self):
        """Whether the event is recorded: the energy [MeV] a slot got lies in
        its window, and the slots hit satisfy the logic expression in the
        window in time. The time of a slot is that of its earliest step that
        deposited energy. An event that left nothing in the slots is not
        kept: a source that seldom hits the device would otherwise hold a
        record of every miss until the end of the run."""
        energies, first_times = {}, {}
        for slot in self.slots:
            energies[slot] = sum(self.energy_step[slot])
            deposited = [
                time for time, energy in zip(self.time_step[slot], self.energy_step[slot])
                if energy > 0
            ]
            if deposited:
                first_times[slot] = min(deposited)
        return event_recorded(
            self.tree, self.slots, self.windows, energies, first_times,
            self.coincidence_window_ns,
        )

    def RecordDevice(self, slot, edep, point_in, point_out, time):
        # the energy of a step is put at its middle [um]: its ends lie on the
        # surfaces of the device, where rounding can leave them outside it
        self.p_step[slot].append([(point_in.getX()+point_out.getX())*500,
                                  (point_in.getY()+point_out.getY())*500,
                                  (point_in.getZ()+point_out.getZ())*500])
        self.start_step[slot].append([point_in.getX()*1000, point_in.getY()*1000, point_in.getZ()*1000])
        self.energy_step[slot].append(edep)
        self.time_step[slot].append(time/g4b.s)

    def save_geant4_events(self, eventID):
        # every slot keeps its steps in a recorded event, also one that was not hit
        self.records.events.append(eventID)
        for slot in self.slots:
            self.records.positions[slot].append(self.p_step[slot])
            self.records.starts[slot].append(self.start_step[slot])
            self.records.energies[slot].append(self.energy_step[slot])
            self.records.times[slot].append(self.time_step[slot])
