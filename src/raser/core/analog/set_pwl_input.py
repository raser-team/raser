"""
Description:
    Set PWL input for NGSpice simulation

@Date       : 2023
@Author     : Ye He, Kaibo Xie, Yanpeng Li
@version    : 2.0
"""

import shutil
import os

def set_pwl_input(pwl_file, cir_file, voltage_file, output_folder):
  
    string_list=[]
    shutil.copy(cir_file, output_folder)
    
    cir_base=os.path.basename(cir_file)
    tmp_cir_base=cir_base.split('.')[0]+'_tmp'+'.cir'

    os.rename(os.path.join(output_folder,cir_base), os.path.join(output_folder,tmp_cir_base))
    print('Temporary circuit file has been created:', tmp_cir_base)

    tmp_cir_file=os.path.join(output_folder, tmp_cir_base)
    
    with open(pwl_file, 'r') as f:
        print('Reading pwl file........')
        lines = f.readlines()
        for i in range(len(lines)):
            if i == len(lines) - 1:  # 如果是最后一行
                lines[i] = lines[i].strip().replace(' ', ',')
                string_list.append(lines[i])
            else:
                lines[i] = lines[i].strip().replace(' ', ',') + ','
                string_list.append(lines[i])

        with open(tmp_cir_file, 'r') as f:
         replacement_line_I1 = 'I1 2 0 PWL(' + ''.join(string_list) + ')'
         output_lines = f.readlines()
         for i in range(len(output_lines)):
             if 'I1' in output_lines[i]:
                 output_lines[i] = replacement_line_I1 + '\n'
             if 'wrdata' in output_lines[i]:
                 output_lines[i] = f"wrdata {voltage_file} v(out)" + '\n'
                 
    with open(tmp_cir_file, 'w') as f:
         f.writelines(output_lines)
    
    print('Temporary circuit file has been modified')
