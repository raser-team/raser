import pyvisa as visa
import time
import warnings

class Keithley2470:
    def __init__(self, resource_name):
        instlist = visa.ResourceManager()
        print(instlist.list_resources())
        self.kei2470 = instlist.open_resource(resource_name)
        self.kei2470.timeout = 25000
        self.cmpl = '105E-6'
    def testIO(self):
        message = self.kei2470.query('*IDN?')
        print(message)

    def set_current_protection(self, current):
        self.cmpl = str(current)
        self.kei2470.write(":SENSe:CURRent:RANGe " + str(current))
       

    def set_voltage_protection(self, vol):
        self.kei2470.write(":SOURce:VOLTage:RANGe " + str(vol))
        

    def set_voltage(self, vol, speed=0.2):
        self.kei2470.write(":SENSe:CURRent:RANGe " + self.cmpl)
        self.kei2470.write(":SOURce:FUNCtion VOLTage")
       
        if(abs(vol)>=1):
            if(vol>0):vols = vol - 1
            else: vols = vol + 1
        else: vols = self.show_voltage()
        print("vols="+str(vols))
        self.sweep(vols, vol, 0.25, speed)
        
        vols = vol
        return vols

    def show_voltage(self):
        
       
        self.kei2470.write(":SOURce:FUNCtion VOLTage")
        self.kei2470.write(":DISPlay:READing:FORMat PREFix")
        voltage = self.kei2470.query(":READ?")
       
        print("voltage [V]:  " + str(voltage))
        return float(str(voltage))

    def sweep(self, vols, vole, step, speed):
        if vols < vole:
            self.sweep_forward(vols,vole,step,speed)
        else:
            self.sweep_backward(vols,vole,step,speed)

    def sweep_forward(self, vols, vole, step,speed):
       
        mvols=vols*1000
        mvole=vole*1000+1
        mstep=step*1000
        for mvol in range(int(mvols),int(mvole),int(mstep)):
            vol=mvol/1000 
            self.kei2470.write(":SOURce:VOLTage:LEVel "+str(vol))
            time.sleep(0.1/speed)

    def sweep_backward(self, vols, vole, step,speed):
       
        mvols=vols*1000
        mvole=vole*1000-1
        mstep=step*1000

        for mvol in range(int(mvols),int(mvole), -int(mstep)):
            vol=mvol/1000 
            self.kei2470.write(":SOURce:VOLTage:LEVel "+str(vol))
            time.sleep(0.1/speed)

    def display_current(self):
        self.kei2470.write(":SENSe:FUNCtion 'CURRent'")
        
       
        self.kei2470.write(":SENS:CURR:RANG:AUTO ON")
        
        self.kei2470.write(":DISPlay:READing:FORMat PREFix")
        
        current=self.kei2470.query(":READ?")
       
        print("current [A]:  " + str(current))
        return float(str(current))

    def hit_compliance(self):
        tripped=int(str(self.kei2470.query("SOUR:CURR:VLIM:TRIP?")))
       
        if tripped:
            print("Hit the compliance "+self.cmpl+"A.")
        return tripped

    def output_on(self):
        self.kei2470.write(":OUTPut:STATe ON")
      
        print("On")

    def output_off(self):
        self.kei2470.write(":OUTPut:STATe OFF")
        print("Off")

    def beep(self, freq=1046.50, duration=0.3):
        self.kei2470.write(":SYSTem:BEEPer "+str(freq)+", "+str(duration))
      
        time.sleep(duration)

    def filter_on(self, count=20, mode="REPeat"):
       
        self.kei2470.write(":SENSe:CURRent:AVERage:COUNt "+str(count))
      
        self.kei2470.write(":SENSe:CURRent:AVERage:TCONtrol "+mode)
       
        self.kei2470.write(":SENSe:CURRent:AVERage:STATe ON")

    def filter_off(self):
       
        self.kei2400c.write("[:SENSe[1]]:CURRent[:DC]:AVERage:STATe OFF")

    def __del__(self):
        self.kei2470.close()


if __name__ == "__main__":
    kei2470 = Keithley2470("USB0::0x05E6::0x2470::04554700::INSTR")
    kei2470.testIO()
