import g4ppyy as g4b

g4b.include("G4UserRunAction.hh")
g4b.include("G4Run.hh")

class GeneralRunAction(g4b.G4UserRunAction):
    def __init__(self):
        super().__init__()
      
    def BeginOfRunAction(self, run):
        g4b.G4RunManager.GetRunManager().SetRandomNumberStore(False)
   
    def EndOfRunAction(self, run):
        nofEvents = run.GetNumberOfEvent()
        if nofEvents == 0:
            print("nofEvents=0")
            return
