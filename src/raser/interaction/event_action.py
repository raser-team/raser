'''
Description:  event_action.py
@Date       : 2025
@Author     : Yuhang Tan, Chenxi Fu (Original: Geant4)
@version    : 2.0
'''

import g4ppyy as g4b

g4b.include("G4UserEventAction.hh")
import numpy as np

class GeneralEventAction(g4b.G4UserEventAction):
    "My Event Action"
    def __init__(self, runAction, point_in, point_out, eventIDs, edep_devices, p_steps, energy_steps, events_angles):
        super().__init__()
        self.fRunAction = runAction
        self.point_in = point_in
        self.point_out = point_out

        self.eventIDs = eventIDs
        self.edep_devices = edep_devices
        self.p_steps = p_steps
        self.energy_steps = energy_steps
        self.events_angles = events_angles

    def BeginOfEventAction(self, event):
        self.edep_device=0.
        self.event_angle = 0.
        self.p_step = []
        self.energy_step = []

    def EndOfEventAction(self, event):
        eventID = event.GetEventID()
        #print("eventID:%s"%eventID)
        if len(self.p_step):
            point_a = [ b-a for a,b in zip(self.point_in,self.point_out)]
            point_b = [ c-a for a,c in zip(self.point_in,self.p_step[-1])]
            self.event_angle = self.cal_angle(point_a,point_b)
        else:
            self.event_angle = None
        self.save_geant4_events(eventID)

        #print("Detector: total energy:", g4b.G4BestUnit(self.edep_device, "Energy"), end="")

    def RecordDevice(self, edep,point_in, point_out):
        self.edep_device += edep
        self.p_step.append([point_in.getX()*1000,
                           point_in.getY()*1000,point_in.getZ()*1000])
        self.energy_step.append(edep)

    def save_geant4_events(self,eventID):
        if(len(self.p_step)>0):
            self.eventIDs.append(eventID)
            self.edep_devices.append(self.edep_device)
            self.p_steps.append(self.p_step)
            self.energy_steps.append(self.energy_step)
            self.events_angles.append(self.event_angle)
        else:
            self.eventIDs.append(eventID)
            self.edep_devices.append(self.edep_device)
            self.p_steps.append([[0,0,0]])
            self.energy_steps.append([0])
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
