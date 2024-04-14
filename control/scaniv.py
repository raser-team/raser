#import Kei2400CControl as kei2400
import keithley2470ccontrol_hyj as kei2470
# import visa
import pyvisa as visa
import time
import pylab
import csv
import numpy as np
import platform
import sys

def csv_writer(data,path):
    with open(path,"w") as csv_file:
        writer=csv.writer(csv_file,lineterminator='\n')
        writer.writerow(['Bias Voltage[V]','Measured Voltage[V]','Measured Current[A]'])
        for val in data:
            writer.writerows([val])


if platform.python_version().startswith('2'):
   print('You are running with',platform.python_version(),'.')
   print('Please run with python3.')
   print('Exit.')
   sys.exit()
biasSupply=kei2470.Keithley2470("USB0::0x05E6::0x2470::04554700::INSTR")


biasSupply.set_current_protection(105E-6) 
biasSupply.set_voltage_protection(800) 
positiveHV=True 
HVrange=700*1e3  
biasSupply.filter_on()

time_start=time.time()
vols=[]
mvols=[]
current=[]

if positiveHV:
    sign=1
else:
    sign=-1
iStart=int(0*1e3)
iEnd=int(sign*HVrange+sign*1)
iStep=int(sign*10.0*1e3) 
for iBias in range(iStart,iEnd,iStep):
    biasSupply.output_on()
    biasvol=iBias/1000 
    vols.append(biasvol)
    mvols.append(biasSupply.set_voltage(biasvol))
    time.sleep(5.0) 

    tmp_current = 0.
    for i in range(2):
        print("display_current",i,":",biasSupply.display_current())
        tmp_current += biasSupply.display_current()
        time.sleep(0.2)

    my_current = tmp_current/3.0
    current.append(my_current)
    if biasSupply.hit_compliance():
        break

print("Bias Vols: "+str(vols))
print("Measured vols: "+str(mvols))
print("Current: "+str(current))

data=[vols,mvols,current]
dataarray=np.array(data)

filename="test_IV.csv"
csv_writer(dataarray.T,filename)
time_top=time.time()
print("Ramping up takes %3.0f s." % (time_top-time_start))

print("Now ramping down...")

biasSupply.sweep(HVrange*sign*1e-3,0,1 ,5)
biasSupply.output_off()
biasSupply.beep()
time_end=time.time()

print("Ramping up time:\t%3.0f s" % (time_top-time_start))
print("Ramping down time:\t%3.0f s" % (time_end-time_top))
print("Total time:\t\t%3.0f m %2.0f s" % ((time_end-time_start)//60, (time_end-time_start)%60))
