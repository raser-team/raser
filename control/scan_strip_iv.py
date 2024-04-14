import raser.control.kei_2400b_control as kei2400
import visa
import time
import pylab
import csv
import numpy as np

def csv_writer(data,path):
    with open(path,"w") as csv_file:
        writer=csv.writer(csv_file,lineterminator='\n')
        writer.writerow(['Bias Voltage[V]','Measure Voltage [V]','Meaure Current [A]'])
        for val in data:
            writer.writerows([val])


biasSupply=kei2400.keithley2400B()

vols=[]
mvols=[]
current=[]

iStart=int(0*1e3)
iEnd=int(105.0*1e3)
iStep=int(2.5*1e3)
for iBias in range(iStart,iEnd,iStep):
    biasSupply.output_on()
    biasvol=iBias/1000
    if biasvol>105:
        print("Much high")
        break
    vols.append(biasvol)
    mvols.append(biasSupply.set_voltage(biasvol))
    current.append(biasSupply.display_current())

biasSupply.set_voltage(0*1e3)

print("Bias Vols: "+str(vols))
print("Measure vols: "+str(mvols))
print("Current: "+str(current))

data=[vols,mvols,current]
dataarray=np.array(data)

filename="striptest.csv"
csv_writer(dataarray.T,filename)
