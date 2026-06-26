"""
Description:
    Simulate induced current through NGSpice

@Date       : 2023
@Author     : Ye He, Kaibo Xie, Yanpeng Li
@version    : 2.0
"""

import re

import ROOT

from raser.supports.output import output

def set_ngspice_input(currents: list[ROOT.TH1F]):
    # TODO: check the cuts and refine the code
    input_current_strs = []
    for th1fcu in currents:
        current = []
        time = []
        for j in range(th1fcu.GetNbinsX()):
            current.append(th1fcu.GetBinContent(j))
            time.append(j*th1fcu.GetBinWidth(0))
        input_c = []
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
            for k in range(j, len(current)):
                current[i]=0

        input_current_strs.append(','.join(input_c))
    return input_current_strs

def set_tmp_cir(read_ele_num, path, input_current_strs, ele_cir, label=None):
    if label is None:
        label = ''
    tmp_cirs = []
    raws = []
    with open(ele_cir, 'r') as f_in:
        lines = f_in.readlines()
        for j in range(read_ele_num):
            new_lines = lines.copy()
            input_c = input_current_strs[j]
            if read_ele_num==1:
                tmp_cir = "{}/{}_tmp.cir".format(path, label)
                raw = "{}/{}.raw".format(path, label)
            else:
                tmp_cir = '{}/{}{}_tmp.cir'.format(path, label, "No."+str(j))
                raw = '{}/{}{}.raw'.format(path, label, "No."+str(j))

            tmp_cirs.append(tmp_cir)
            raws.append(raw)

            for i in range(len(new_lines)):
                if new_lines[i].startswith('I1'):
                    # replace pulse by PWL
                    new_lines[i] = re.sub(r"pulse" + r".*", 'PWL('+str(input_c)+') \n', new_lines[i], flags=re.IGNORECASE,)
                if new_lines[i].startswith('wrdata'):
                    # replace output file name & path
                    new_lines[i] = re.sub(r".*" + r".raw", "wrdata"+" "+raw, new_lines[i], flags=re.IGNORECASE,)
                if ( new_lines[i].startswith('noise') or new_lines[i].startswith('setplot') or new_lines[i].endswith('onoise_spectrum\n')):
                    # skip noise spectrum calculation
                    new_lines[i] = '* skipped: ' + new_lines[i]
            with open(tmp_cir, 'w+') as f_out:
                f_out.writelines(new_lines)
                f_out.close()
        f_in.close()

    return tmp_cirs, raws