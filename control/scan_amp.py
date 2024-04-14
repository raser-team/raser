import raser.control.kei_2026_bias_control as kei2026
import raser.control.tek_tds5054b_control as tds5054b
import visa
import time
import pylab
import csv
import numpy as np

def csv_writer(data,path):
    with open(path,"w") as csv_file:
        writer=csv.writer(csv_file,lineterminator='\n')
        writer.writerow(['Bias Voltage[V]','Measure Voltage [V]','Meaure Current [A]','Max Amp [mV]'])
        for val in data:
            writer.writerows([val])


biasSupply=kei2026.keithley2026()
scope=tds5054b.TDS5054B()

scope.testIO()
scope.readSet(3)

vols=[]
mvols=[]
maxAmp=[]
current=[]

iStart=int(0*1e3)
iEnd=int(1*1e3)
iStep=int(0.1*1e3)
for iBias in range(iStart,iEnd,iStep):
    biasSupply.output_on()
    biasvol=iBias/1000
    if biasvol>5:
        break
    vols.append(biasvol)
    mvols.append(biasSupply.set_voltage(biasvol))
    current.append(biasSupply.display_current())

    Time,Volts = scope.readWave()
    maxAmp.append(max(Volts)-min(Volts))

print("Bias Vols: "+str(vols))
print("Measure vols: "+str(mvols))
print("Current: "+str(current))
print("MaxAmp: "+str(maxAmp))

data=[vols,mvols,current,maxAmp]
dataarray=np.array(data)

filename="test.csv"
csv_writer(dataarray.T,filename)
