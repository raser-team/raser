import sys
import os
import ROOT
import csv

def convert_csv_to_root(input_dir, output_dir, label):
    com_name = []
    for file in os.listdir(input_dir):
        if file.endswith('.csv'):
            com_name.append(file)
    for name in com_name:
        if label == 'sicar1.1.8' and not name.startswith('sicar1.1.8'):
            continue
        elif label == 'sicar1.1.8-1' and not name.startswith('sicar1.1.8-1_'):
            continue
        elif label == 'sicar1.1.8-2' and not name.startswith('sicar1.1.8-2_'):
            continue

        name = name.split('.csv')[0]
        input_file = os.path.join(input_dir, name + '.csv')
        output_file = os.path.join(output_dir, name + '.root')

        if name.endswith('iv'):
            if label=="itk_atlas18_data_v1":
                df = ROOT.RDF.MakeCsvDataFrame(input_file, True, '\t')
            elif label =="njupin_iv_v1":
                df = ROOT.RDF.MakeCsvDataFrame(input_file, True, ',')
            else:
                df = ROOT.RDF.MakeCsvDataFrame(input_file, True, ',')
            if label in ["itk_md8_data_v1","itk_atlas18_data_v1"]:
                df.Snapshot("myTree", output_file, {"Voltage_V", "Current_nA"})
            elif label in ['itk_atlas18_sim_v1','itk_md8_sim_v1']:
                df.Snapshot("myTree", output_file, {"Voltage", "Current"})
            elif label =="njupin_iv_v1":
                df.Snapshot("myTree", output_file, {"Current","Voltage"})
            
            else:
                df.Snapshot("myTree", output_file, {"Value","Reading"})

        if name.endswith('cv'):
            df = ROOT.RDF.MakeCsvDataFrame(input_file, True, ',')
            if label=="itk_md8_sim_v1":
                df.Snapshot("myTree", output_file, {"Voltage", "Capacitance"})
            elif label =="njupin_cv_v1":
                df.Snapshot("myTree", output_file, {"Voltage", "Capacitance"})
            else:
                df.Snapshot("myTree", output_file, {"Voltage", "Capacitance", "Capacitance^-2"})

        if name.endswith('Wfm'):
            df = ROOT.RDF.MakeCsvDataFrame(input_file, True, ',')
            df.Snapshot("myTree", output_file, {"Time", "Volt"})

        
        sys.stdout.write('Saved as {}\n'.format(output_file))


def main(kwargs):
    label = kwargs['label']

    if label == 'sicar1.1.8':
        input_dir = '/scratchfs/bes/wangkeqi/wangkeqi/data/SICAR1.1.8'
        output_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/wangkeqi/sicar1.1.8/iv_cv'
    elif label == 'sicar1.1.8-1':
        input_dir = '/scratchfs/bes/wangkeqi/wangkeqi/data/SICAR1.1.8'
        output_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/wangkeqi/sicar1.1.8/iv_cv'
    elif label == 'sicar1.1.8-2':
        input_dir = '/scratchfs/bes/wangkeqi/wangkeqi/data/SICAR1.1.8'
        output_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/wangkeqi/sicar1.1.8/iv_cv'
    elif label == 'itk_md8_data_v1':
        input_dir = '/afs/ihep.ac.cn/users/l/lizhan/disk/scrathfs/sensorsimanddata/itkmd8/itkmd8data'
        output_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/lizhan/itkmd8/itkmd8data'
    elif label == 'itk_md8_sim_v1':
        input_dir = '/afs/ihep.ac.cn/users/l/lizhan/disk/scrathfs/sensorsimanddata/itkmd8/itkmd8sim'
        output_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/lizhan/itkmd8/itkmd8sim'
    elif label == 'itk_atlas18_sim_v1':
        input_dir = '/afs/ihep.ac.cn/users/l/lizhan/disk/scrathfs/sensorsimanddata/itkatlas18/sim'
        output_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/lizhan/atlas18/sim'
    elif label == 'itk_atlas18_data_v1':
        input_dir = '/afs/ihep.ac.cn/users/l/lizhan/disk/scrathfs/sensorsimanddata/itkatlas18/data'
        output_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/lizhan/atlas18/data'
    elif label == 'njupin_iv_v1':
        input_dir = "/afs/ihep.ac.cn/users/s/senzhao/njupin"
        output_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/zhaosen/njupin_iv'
    elif label == 'njupin_cv_v1':
        input_dir = "/afs/ihep.ac.cn/users/s/senzhao/njupin/cv"
        output_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/zhaosen/njupin_cv'
    elif label == 'sicar1.1.8_alpha_v1':
        input_dir = '/scratchfs/bes/wangkeqi/wangkeqi/data/SICAR1.1.8/CCE_1.1.8-8-1/400v'
        output_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/wangkeqi/sicar1.1.8/alpha/1/400V'
    elif label == 'sicar1.1.8_beta':
        input_dir = '/scratchfs/bes/wangkeqi/wangkeqi/data/SICAR1.1.8/time_1.1.8-8/20231116/si/beta_'
        output_dir = '/publicfs/atlas/atlasnew/silicondet/itk/raser/wangkeqi/sicar1.1.8/beta'
    else:
        raise NameError(label)

    convert_csv_to_root(input_dir, output_dir, label)

