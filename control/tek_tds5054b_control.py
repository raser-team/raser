import visa
import numpy as np
from struct import unpack
import pylab

class TDS5054B:
    def __init__(self):
        instlist=visa.ResourceManager()
        print(instlist.list_resources())
        self.scope=instlist.open_resource("GPIB0::1::INSTR")

    def testIO(self):
        message=self.scope.ask('*IDN?')
        print(message)
		
    def readSet(self,ch):
        self.scope.write("DATA:SOU "+str(ch))
        self.scope.write('DATA:WIDTH 1')
        self.scope.write('DATA:ENC RPB')
		
    def readOffset(self):
        ymult = float(self.scope.ask('WFMPRE:YMULT?'))
        yzero = float(self.scope.ask('WFMPRE:YZERO?'))
        yoff = float(self.scope.ask('WFMPRE:YOFF?'))
        xincr = float(self.scope.ask('WFMPRE:XINCR?'))
        return ymult,yzero,yoff,xincr

    def readWave(self):
        ymult,yzero,yoff,xincr=self.readOffset()

        self.scope.write("CURVE?")
        data=self.scope.read_raw()
        headerlen=2+int(data[1])
        header=data[:headerlen]
        ADC_wave=data[headerlen:-1]
        ADC_wave = np.array(unpack('%sB' % len(ADC_wave),ADC_wave))
        Volts = (ADC_wave - yoff) * ymult  + yzero
        Time = np.arange(0, xincr * len(Volts), xincr)
        Time=Time*1e9 #ns
        Volts=Volts*1e3 #mV

        return Time, Volts

    def plotWave(self, Time, Volts):
        pylab.plot(Time, Volts)
        pylab.show()

  
if __name__=="__main__":
    scope=TDS5054B()
    scope.testIO()
    scope.readSet(3)
    
    Time,Volts = scope.readWave()
    scope.plotWave(Time, Volts)
    print(max(Volts)-min(Volts))
