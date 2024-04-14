import pyvisa as visa
import time
import warnings

class keysighte4980a:
    def __init__(self,resource_name):
        instlist=visa.ResourceManager()
        print(instlist.list_resources())
        self.lcr=instlist.open_resource(resource_name)
        self.lcr.write(":function:impedance:type CPRP") 
        self.lcr.write(":format:ascii:long on")
        self.lcr.write(":aperture medium") 

    def testIO(self):
        message=self.lcr.query('*IDN?')
        print(message)

    def set_voltage_level(self, vol): 
        self.lcr.write(":voltage:level "+str(vol))

    def set_frequency(self, freq): 
        self.lcr.write(":frequency "+freq)

    def set_trigger_remote(self):
        self.lcr.write("trigger:source bus")

    def set_trigger_internal(self):
        self.lcr.write("trigger:source internal")

    def get_capacitance(self):
        res=self.lcr.write("trigger:immediate")
        res=self.lcr.query("fetch?")
        reslist=res.split(",")
        cap=reslist[0]
        print("capacitance [F]: " + cap)
        return float(cap)

if __name__=="__main__":
    lcr=keysighte4980a("USB0::0x2A8D::0x2F01::MY46516486::INSTR")
    lcr.testIO()
    lcr.set_trigger_internal()
