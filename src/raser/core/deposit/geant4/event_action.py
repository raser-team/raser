'''
Description:  event_action.py
@Date       : 2025
@Author     : Yuhang Tan, Chenxi Fu (Original: Geant4)
@version    : 2.0
'''

from raser.core.deposit.geant4.g4ppyy_runtime import g4b

g4b.include("G4UserEventAction.hh")
import numpy as np

class GeneralEventAction(g4b.G4UserEventAction):
    "My Event Action"
    def __init__(self, runAction, point_in, point_out, eventIDs, edep_devices, p_steps, energy_steps, time_steps, events_angles, edep_window,):
        super().__init__()
        self.fRunAction = runAction
        self.point_in = point_in
        self.point_out = point_out

        self.eventIDs = eventIDs
        self.edep_devices = edep_devices
        self.p_steps = p_steps
        self.energy_steps = energy_steps
        self.time_steps = time_steps
        self.events_angles = events_angles
        self.edep_window = edep_window

    def BeginOfEventAction(self, event):
        self.edep_device= 0.0
        self.event_angle = 0.0
        self.p_step = []
        self.energy_step = []
        self.time_step = []

    def EndOfEventAction(self, event):
        eventID = event.GetEventID()
        #print("eventID:%s"%eventID)
        if len(self.p_step):
            point_a = [ b-a for a,b in zip(self.point_in,self.point_out)]
            point_b = [ c-a for a,c in zip(self.point_in,self.p_step[-1])]
            self.event_angle = self.cal_angle(point_a,point_b)
        else:
            self.event_angle = None
        if self.in_edep_window():
            self.save_geant4_events(eventID)

        #print("Detector: total energy:", g4b.G4BestUnit(self.edep_device, "Energy"), end="")

    def in_edep_window(self):
        "Whether the energy deposited in the device [MeV] lies in the window"
        edep_min, edep_max = self.edep_window
        if edep_min is not None and self.edep_device < edep_min:
            return False
        if edep_max is not None and self.edep_device > edep_max:
            return False
        return True

    def RecordDevice(self, edep,point_in, point_out, time):
        self.edep_device += edep
        # the energy of a step is put at its middle [um]: its ends lie on the
        # surfaces of the device, where rounding can leave them outside it
        self.p_step.append([(point_in.getX()+point_out.getX())*500,
                            (point_in.getY()+point_out.getY())*500,
                            (point_in.getZ()+point_out.getZ())*500])
        self.energy_step.append(edep)
        self.time_step.append(time/g4b.s)

    def save_geant4_events(self,eventID):
        if len(self.p_step)>0:
            self.eventIDs.append(eventID)
            self.edep_devices.append(self.edep_device)
            self.p_steps.append(self.p_step)
            self.energy_steps.append(self.energy_step)
            self.time_steps.append(self.time_step)
            self.events_angles.append(self.event_angle)
        else:
            self.eventIDs.append(eventID)
            self.edep_devices.append(self.edep_device)
            self.p_steps.append([[0,0,0]])
            self.energy_steps.append([0])
            self.time_steps.append([0])
            self.events_angles.append(self.event_angle)
        
    def cal_angle(self,point_a,point_b):
        "Calculate the angle between point a and b"
        x=np.array(point_a)
        y=np.array(point_b)
        l_x=np.sqrt(x.dot(x))
        l_y=np.sqrt(y.dot(y))
        dot_product=x.dot(y)
        if l_x*l_y > 0:
            cos_angle_d=dot_product/(l_x*l_y)
            angle_d=np.arccos(cos_angle_d)*180/np.pi
        else:
            angle_d=9999
        return angle_d
