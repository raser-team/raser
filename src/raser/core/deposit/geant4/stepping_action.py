from raser.core.deposit.geant4.g4ppyy_runtime import g4b

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
        volume = point_pre.GetTouchable().GetVolume().GetLogicalVolume()
        self.volume_name = str(volume.GetName())

        # a step belongs to the slot its front point lies in
        if self.volume_name in self.fEventAction.slots: # important, no if => no signal
            self.fEventAction.RecordDevice(
                self.volume_name, edep, point_in, point_out, point_pre.GetGlobalTime()
            )
