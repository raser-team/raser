import visa
import time
import warnings

class keithley2400B:
    def __init__(self):
        instlist=visa.ResourceManager()
        print(instlist.list_resources())
        self.kei2400b=instlist.open_resource("GPIB0::24::INSTR")
        self.timedelay=5

    def testIO(self):
        message=self.kei2400b.ask('*IDN?')
        print(message)

    def set_voltage(self,vol):
        if vol > 105:
            warnings.warn("Warning High Voltage!!!!")

        self.kei2400b.write(":sense:current:protection 1.05E-4")
        self.kei2400b.write(":source:function voltage")
        self.kei2400b.write(":source:voltage:mode fixed")
        vols=self.show_voltage()
        self.sweep(vols,vol,1)
        vols=self.show_voltage()
        return vols

    def show_voltage(self):
        self.kei2400b.write(":source:voltage:mode fixed")
        self.kei2400b.write(":form:elem voltage")
        voltage=self.kei2400b.ask(":read?")
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
            self.kei2400b.write(":source:voltage:level "+str(vol))
            self.kei2400b.write(":sense:current:protection 1.05E-4")
            self.show_voltage()
            time.sleep(self.timedelay)

        self.kei2400b.write(":source:voltage:level "+str(vole))
        self.show_voltage()

    def sweep_backward(self, vols, vole, step):
        # Conveter from V to mV
        mvols=vols*1000
        mvole=vole*1000
        mstep=step*1000

        for mvol in range(int(mvols),int(mvole), -int(mstep)):
            vol=mvol/1000 # mV -> V
            self.kei2400b.write(":source:voltage:level "+str(vol))
            self.kei2400b.write(":sense:current:protection 1.05E-4")
            self.show_voltage()
            time.sleep(self.timedelay)

        self.kei2400b.write(":source:voltage:level "+str(vole))
        self.show_voltage()

    def display_current(self):
        self.kei2400b.write(":sense:function 'current'")
        self.kei2400b.write(":sense:current:range 1.05E-4")
        self.kei2400b.write(":display:enable on")
        self.kei2400b.write(":display:digits 7")
        self.kei2400b.write(":form:elem current")
        current=self.kei2400b.ask(":read?")
        print("instant current [A]:  " + str(current))

        time.sleep(self.timedelay)
        self.kei2400b.write(":form:elem current")
        current=self.kei2400b.ask(":read?")
        print("long current [A]:  " + str(current))
        return float(str(current))

    def output_on(self):
        self.kei2400b.write(":output on")
        print("On")

    def output_off(self):
        self.kei2400b.write(":output off")
        print("Off")


if __name__=="__main__":
    kei2400b=keithley2400b()
    kei2400b.output_on()
    kei2400b.set_voltage(1)
    current=kei2400b.display_current()
    print(current)
    kei2400b.output_off()

