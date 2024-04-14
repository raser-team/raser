import keye4980acontrol  
import keithley2470ccontrol_hyj as kei2470 
import csv
import numpy as np 
import platform  
import sys
import warnings
import time


def csv_writer(data,path): 
    with open(path,"w") as csv_file: 
        writer=csv.writer(csv_file,lineterminator='\n') 
        writer.writerow(['Bias Voltage[V]','Measured Voltage[V]','Measured Capacitance[pF]','Capacitance^{-2}[pF]^{-2}','Monitoring Current[A]'])
        for val in data: 
            writer.writerows([val])

# prevent from running with python2
if platform.python_version().startswith('2'): 
   print('You are running with',platform.python_version(),'.')
   print('Please run with python3.')
   print('Exit.')
   sys.exit()


lcr=keye4980acontrol.keysighte4980a("USB0::0x2A8D::0x2F01::MY46516486::INSTR") 

lcr.set_frequency("1kHz")  
lcr.set_voltage_level(0.1) 
timedelay=3.0 



biasSupply=kei2470.Keithley2470("USB0::0x05E6::0x2470::04554700::INSTR")
biasSupply.set_current_protection(100E-6)
biasSupply.set_voltage_protection(400) 
positiveHV=True 
HVrange=150.0*1e3  


time_start=time.time()
vols=[]
mvols=[]
pcap=[]

invpcap2=[]
current=[]

if positiveHV:
    sign=1
else:
    sign=-1

iStart=int(0*1e3)
iEnd=int(sign*HVrange+sign*1)
iStep=int(sign*1.0*1e3)
lcr.set_trigger_remote()
biasSupply.output_on()
for iBias in range(iStart,iEnd,iStep):
    biasvol=iBias/1000 
    if biasvol>400:
        warnings.warn("Warning! Exceed the maximum voltage of the bias adapter!")
        break
    vols.append(biasvol)
    mvols.append(biasSupply.set_voltage(biasvol))
    time.sleep(timedelay)
    current.append(biasSupply.display_current())
    
    tmp_ipcap = 0.
    for i in range(5):
        print("display_capacitance",i,":",lcr.get_capacitance()/1e-12)
        tmp_ipcap += lcr.get_capacitance()/1e-12
        time.sleep(0.2)
    ipcap = tmp_ipcap/5.0
   
    pcap.append(ipcap)
    
    invpcap2.append(1.0/(ipcap*ipcap))
    if biasSupply.hit_compliance():
        break

print("Bias Vols: "+str(vols))
print("Measured vols: "+str(mvols))
print("Capacitance: "+str(pcap))

print("Current: "+str(current))

data=[vols,mvols,pcap,invpcap2,current]

dataarray=np.array(data)

filename="test_CV.csv"
csv_writer(dataarray.T,filename)
time_top=time.time()
print("Ramping up takes %3.0f s." % (time_top-time_start))

print("Now ramping down...")
lcr.set_trigger_internal()

biasSupply.sweep(HVrange*sign*1e-3,0,1,5)
biasSupply.output_off()
biasSupply.beep()
time_end=time.time()

print("Ramping up time:\t%3.0f s" % (time_top-time_start))
print("Ramping down time:\t%3.0f s" % (time_end-time_top))
print("Total time:\t\t%3.0f m %2.0f s" % ((time_end-time_start)//60, (time_end-time_start)%60))
