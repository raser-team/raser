import visa
import time
import warnings 

class keithley2026:
    def __init__(self):
        instlist=visa.ResourceManager()
        print(instlist.list_resources())
        self.kei026=instlist.open_resource("GPIB1::4::INSTR")
        self.timedelay=1

    def testIO(self):
        message=self.kei026.ask('*IDN?')
        print(message)
        
    def set_voltage(self,vol):
        if vol > 5.0:
            warnings.warn("Warning High Voltage!!!!")
        self.kei026.write("smua.source.limiti=5E-7")
        self.kei026.write("smua.source.func=smua.OUTPUT_DCVOLTS")
        vols=self.show_voltage()
        self.sweep(vols,vol,0.1)
        vols=self.show_voltage()
        return vols

    def show_voltage(self):
        self.kei026.write("voltagea=smua.measure.v()")
        voltage=self.kei026.ask("printnumber(voltagea)")
        print("voltage [V]:  " + str(voltage))
        return float(str(voltage))

    def sweep(self, vols, vole, step):
        if vols < vole:
            self.sweep_forward(vols,vole,step)
        else:
            self.sweep_backward(vols,vole,step)    

    def sweep_forward(self, vols, vole, step):
        # Conveter from V to mV
        mvols=vols*1000
        mvole=vole*1000
        mstep=step*1000
        
        for mvol in range(int(mvols),int(mvole),int(mstep)):
            vol=mvol/1000 # mV -> V
            self.kei026.write("smua.source.levelv="+str(vol))
            self.kei026.write("smua.source.limiti=5E-7")
            self.show_voltage()
            time.sleep(self.timedelay)
        self.kei026.write("smua.source.levelv="+str(vole))
        self.show_voltage()

    def sweep_backward(self, vols, vole, step):
        # Conveter from V to mV
        mvols=vols*1000
        mvole=vole*1000
        mstep=step*1000
        
        for mvol in range(int(mvols),int(mvole), -int(mstep)):
            vol=mvol/1000 # mV -> V
            self.kei026.write("smua.source.levelv="+str(vol))
            self.kei026.write("smua.source.limiti=5E-7")
            self.show_voltage()
            time.sleep(self.timedelay)
        self.kei026.write("smua.source.levelv="+str(vole))
        self.show_voltage()
        
    def display_current(self):
        self.kei026.write("display.smua.measure.func=display.MEASURE_DCAMPS")
        self.kei026.write("smua.measure.rangei=1E-6")
        self.kei026.write("smua.measure.rel.enablei=1")
        self.kei026.write("currenta=smua.measure.i()")
        current=self.kei026.ask("printnumber(currenta)")
        print("current [A]:  " + str(current))
        
        time.sleep(self.timedelay)
        self.kei026.write("currenta=smua.measure.i()")
        current=self.kei026.ask("printnumber(currenta)")
        return float(str(current))

    def output_on(self):
        self.kei026.write("smua.source.output=smua.OUTPUT_ON")
        print("On")

    def output_off(self):
        self.kei026.write("smua.source.output=smua.OUTPUT_OFF")
        print("Off")


if __name__=="__main__":
    kei026=keithley2026()
    kei026.output_on()
    kei026.set_voltage(0.1)
    current=kei026.display_current()
    print(current)
    #kei026.output_off()

