#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import ROOT
import os
import numpy as np
import sys
args = sys.argv[1:]
pardic={}
for par in args:
    name,_,value=par.rpartition('=')
    pardic[name]=value
L = int(pardic['number'])
tolcurrent = int(pardic['current'])
number = int(pardic['number'])
maxV=[]

if number>=1:
    for i in range(number*1000,(number+1)*1000):
        path = os.path.join('output', 'pin3D',"NJU-PIN-Beam-monitor", )
        myFile = ROOT.TFile("/scratchfs/atlas/xingchenli/raser/output/pin3D/NJU-PIN-Beam-monitor/"+"beam-monitor-current"+str(i)+".root")
        myt = myFile.tree
        current=[]
        time=[]
        for entry in myt:
            current.append(entry.current0)
            time.append(entry.time)

        input_c=[]
        if abs(min(current))>max(current): #set input signal
            c_max=min(current)
            for i in range(0, len(current)):
                if current[i] < c_max * 0.01:
                    input_c.append(str(0))
                    input_c.append(str(0))
                    input_c.append(str(time[i]))
                    input_c.append(str(0))
                    break
                else:
                    current[i]=0
            for j in range(i, len(current)):
                input_c.append(str(time[j]))
                input_c.append(str(current[j]))
                if current[j] > c_max * 0.01:
                    break
            input_c.append(str(time[j]))
            input_c.append(str(0))
            input_c.append(str(time[len(time)-1]))
            input_c.append(str(0))
            for k in range(j, len(current)):
                current[i]=0
        else:
            c_max=max(current)
            for i in range(0, len(current)):
                current[i]=0
                if current[i] > c_max * 0.01:
                    input_c.append(str(0))
                    input_c.append(str(0))
                    input_c.append(str(time[i]))
                    input_c.append(str(0))
                    break
            for j in range(i, len(current)):
                input_c.append(str(time[j]))
                input_c.append(str(current[j]))
                if current[j] < c_max * 0.01:
                    break
            input_c.append(str(time[j]))
            input_c.append(str(0))
            input_c.append(str(time[len(time)-1]))
            input_c.append(str(0))

        input_p=','.join(input_c)
        with open('/scratchfs/atlas/xingchenli/raser/paras/T1.cir', 'r') as f:
            lines = f.readlines()
            lines[113] = 'I1 2 0 PWL('+str(input_p)+') \n'
            lines[140] = 'tran 0.1p ' + str((input_c[len(input_c) - 2])) + '\n'
            lines[141] = 'wrdata output/'+str(L)+'t1.txt v(out)\n'
            f.close()
        with open('/scratchfs/atlas/xingchenli/raser/output/T1_tmp.cir', 'w') as f:
            f.writelines(lines)
            f.close()

        os.system("ngspice -b -r t1.txt output/T1_tmp.cir")

        t1=np.loadtxt('/scratchfs/atlas/xingchenli/raser/output/'+str(L)+'t1.txt',dtype=float)
        volt=[]
        for i in t1:
            volt.append(i[1])
        maxV.append(min(volt))
else:
    for i in range((number+1)*1000):
        path = os.path.join('output', 'pin3D',"NJU-PIN-Beam-monitor", )
        myFile = ROOT.TFile("/scratchfs/atlas/xingchenli/raser/output/pin3D/NJU-PIN-Beam-monitor/"+"beam-monitor-current"+str(i)+".root")
        myt = myFile.tree
        current=[]
        time=[]
        for entry in myt:
            current.append(entry.current0)
            time.append(entry.time)

        input_c=[]
        if abs(min(current))>max(current): #set input signal
            c_max=min(current)
            for i in range(0, len(current)):
                if current[i] < c_max * 0.01:
                    input_c.append(str(0))
                    input_c.append(str(0))
                    input_c.append(str(time[i]))
                    input_c.append(str(0))
                    break
                else:
                    current[i]=0
            for j in range(i, len(current)):
                input_c.append(str(time[j]))
                input_c.append(str(current[j]))
                if current[j] > c_max * 0.01:
                    break
            input_c.append(str(time[j]))
            input_c.append(str(0))
            input_c.append(str(time[len(time)-1]))
            input_c.append(str(0))
            for k in range(j, len(current)):
                current[i]=0
        else:
            c_max=max(current)
            for i in range(0, len(current)):
                current[i]=0
                if current[i] > c_max * 0.01:
                    input_c.append(str(0))
                    input_c.append(str(0))
                    input_c.append(str(time[i]))
                    input_c.append(str(0))
                    break
            for j in range(i, len(current)):
                input_c.append(str(time[j]))
                input_c.append(str(current[j]))
                if current[j] < c_max * 0.01:
                    break
            input_c.append(str(time[j]))
            input_c.append(str(0))
            input_c.append(str(time[len(time)-1]))
            input_c.append(str(0))

        input_p=','.join(input_c)
        with open('/scratchfs/atlas/xingchenli/raser/paras/T1.cir', 'r') as f:
            lines = f.readlines()
            lines[113] = 'I1 2 0 PWL('+str(input_p)+') \n'
            lines[140] = 'tran 0.1p ' + str((input_c[len(input_c) - 2])) + '\n'
            lines[141] = 'wrdata output/'+str(L)+'t1.txt v(out)\n'
            f.close()
        with open('/scratchfs/atlas/xingchenli/raser/output/T1_tmp.cir', 'w') as f:
            f.writelines(lines)
            f.close()

        os.system("ngspice -b -r t1.txt output/T1_tmp.cir")

        t1=np.loadtxt('/scratchfs/atlas/xingchenli/raser/output/'+str(L)+'t1.txt',dtype=float)
        volt=[]
        for i in t1:
            volt.append(i[1])
        maxV.append(min(volt))

print(max(volt))
print(min(volt))
print(maxV)

np.savetxt('/scratchfs/atlas/xingchenli/raser/output/V/'+str(L)+'maxV.txt', maxV)

