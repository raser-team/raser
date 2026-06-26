import os
import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
from matplotlib.patches import Rectangle
from raser.supports.output import output

def main():

    output_folder_1 = output(__file__, "N0_3_4")
    output_folder_2 = output(__file__, "N0_0_34")

    patternI = r'(\d+)_I\.txt'
    patternII = r'(\d+)_II\.txt'

    global z_list, y_list
    z_list = list(range(2))
    y_list = list(range(-3, 3))

    Amp_1 = []
    for i in range(804):
        event_folder = os.path.join(output_folder_1, f"event_{i}")
        print(i)
        for filename in os.listdir(event_folder):
            match_I = re.match(patternI, filename)
            match_II = re.match(patternII, filename)
            if match_I:
                with open(os.path.join(event_folder, filename), 'r') as I_file:
                    lines = I_file.readlines()
                    for y in y_list:
                        for z in z_list:
                            for ln, line in enumerate(lines): 
                                if f'detector_I_{y}_{z}:\n' == line:  
                                    amp_tmp_I = []
                                    ln_prep = ln+1
                                    ln_post = ln+1001
                                    for ele in range(ln_prep, ln_post):
                                        columns = lines[ele].strip().split()  
                                        sc = float(columns[1])
                                        amp_tmp_I.append(sc)
                                    amp_tmp_I.append(0.0)  
                                    Amp_value_I = float(max(amp_tmp_I))*1e6
                                    Amp_1.append(Amp_value_I)
            elif match_II:
                with open(os.path.join(event_folder, filename), 'r') as I_file:
                    lines = I_file.readlines()
                    for y in y_list:
                        for z in z_list:
                            for ln, line in enumerate(lines): 
                                if f'detector_II_{y}_{z}:\n' == line:  
                                    amp_tmp_II = []
                                    ln_prep = ln+1
                                    ln_post = ln+1001
                                    for ele in range(ln_prep, ln_post):
                                        columns = lines[ele].strip().split()  
                                        sc = float(columns[1])
                                        amp_tmp_II.append(sc)
                                    amp_tmp_II.append(0.0)  
                                    Amp_value_II = float(max(amp_tmp_II))*1e6
                                    Amp_1.append(Amp_value_II)

    Amp_2 = []
    for i in range(804):
        event_folder = os.path.join(output_folder_2, f"event_{i}")
        print(i)
        for filename in os.listdir(event_folder):
            match_I = re.match(patternI, filename)
            match_II = re.match(patternII, filename)
            if match_I:
                with open(os.path.join(event_folder, filename), 'r') as I_file:
                    lines = I_file.readlines()
                    for y in y_list:
                        for z in z_list:
                            for ln, line in enumerate(lines): 
                                if f'detector_I_{y}_{z}:\n' == line:  
                                    amp_tmp_I = []
                                    ln_prep = ln+1
                                    ln_post = ln+1001
                                    for ele in range(ln_prep, ln_post):
                                        columns = lines[ele].strip().split()   
                                        sc = float(columns[1])
                                        amp_tmp_I.append(sc)
                                    amp_tmp_I.append(0.0)  
                                    Amp_value_I = float(max(amp_tmp_I))*1e6
                                    Amp_2.append(Amp_value_I) 
            elif match_II:
                with open(os.path.join(event_folder, filename), 'r') as I_file:
                    lines = I_file.readlines()
                    for y in y_list:
                        for z in z_list:
                            for ln, line in enumerate(lines): 
                                if f'detector_II_{y}_{z}:\n' == line:  
                                    amp_tmp_II = []
                                    ln_prep = ln+1
                                    ln_post = ln+1001
                                    for ele in range(ln_prep, ln_post):
                                        columns = lines[ele].strip().split()  
                                        sc = float(columns[1])
                                        amp_tmp_II.append(sc)
                                    amp_tmp_II.append(0.0)  
                                    Amp_value_II = float(max(amp_tmp_II))*1e6
                                    Amp_2.append(Amp_value_II)   

    n_event_1 = len(Amp_1)
    mean_1 = np.mean(Amp_1)
    n_event_2 = len(Amp_2)
    mean_2 = np.mean(Amp_2)

    bins = np.linspace(-10, 80, 90) 
    bin_centers = (bins[:-1] + bins[1:]) / 2 
    bin_width = bins[1] - bins[0]

    hist1, _ = np.histogram(Amp_1, bins=bins)
    hist2, _ = np.histogram(Amp_2, bins=bins)

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.bar(bin_centers, hist1, width=bin_width*0.9,
        color='none', edgecolor='red', hatch='//////', alpha=0.7, label=r'$\mathcal{L}_{0}$')
    ax.bar(bin_centers, hist2, width=bin_width*0.9,
        color='none', edgecolor='blue', hatch='\\\\\\', alpha=0.7, label=r'10% $\mathcal{L}_{0}$')

    ax.set_xlabel("Amplitude (uA)", fontsize=14)
    ax.set_ylabel("Events / 1 uA", fontsize=14)
    ax.tick_params(axis='both', which='major', labelsize=10, direction='in', length=6)
    ax.tick_params(axis='both', which='minor', direction='in', length=3)
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    ax.set_xlim(-10, 80)

    legend_handles = [
        Rectangle((0,0), 1, 1, 
                edgecolor='red', facecolor='white', 
                hatch='//////', linewidth=1.5),      
        Rectangle((0,0), 1, 1, 
                edgecolor='blue', facecolor='white', 
                hatch='\\\\\\', linewidth=1.5)
    ]    
    
    ax.legend(
        handles=legend_handles,
        labels=[r'$\mathcal{L}_{0}$', r'10% $\mathcal{L}_{0}$'],
        loc='best',
        fontsize=12,
    )

    text_x = 20
    text_y = max(hist1.max(), hist2.max()) * 0.8
    text_content = [
        fr'$\mathcal{{L}}_{0}$ total events: {n_event_1}',
        fr'$\mathcal{{L}}_{0}$ mean amplitude: {mean_1:.2f} uA',
        fr'10%$\mathcal{{L}}_{0}$ total events: {n_event_2}',
        fr'10%$\mathcal{{L}}_{0}$ mean amplitude: {mean_2:.2f} uA'
    ]
    for i, text in enumerate(text_content):
        ax.text(text_x, text_y - i*0.08*text_y, text, fontsize=12, va='top')

    plt.savefig('src/raser/apps/lumi/figs/Amplitude_dis.pdf')
