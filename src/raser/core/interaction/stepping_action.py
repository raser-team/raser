import g4ppyy as g4b

g4b.include("G4UserSteppingAction.hh")

class GeneralSteppingAction(g4b.G4UserSteppingAction):
    "My Stepping Action"
    def __init__(self, eventAction):
        super().__init__()
        self.fEventAction = eventAction

    def UserSteppingAction(self, step):
        edep = step.GetTotalEnergyDeposit()
        point_pre  = step.GetPreStepPoint()
        point_post = step.GetPostStepPoint() 
        point_in   = point_pre.GetPosition()
        point_out  = point_post.GetPosition()
        volume = step.GetPreStepPoint().GetTouchable().GetVolume().GetLogicalVolume()
        self.volume_name = volume.GetName()

        if self.volume_name == "Device": # important, no if => no signal
            self.fEventAction.RecordDevice(edep,point_in,point_out)
