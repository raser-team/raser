import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import math

def main():
    
    lumi_ratio = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    tsc = np.array([22.59, 39.35, 63.78, 79.59, 125.25, 130.03, 161.64, 180.96, 211.85, 259.72])
    bn = np.array([187, 313, 400, 482, 560, 622, 655, 698, 713, 738])

    precision = []
    for i in range(len(lumi_ratio)):
        lambda_val = lumi_ratio[i] * 3.4
        denominator = (lambda_val * bn[i]) / (1 - math.exp(-lambda_val))
        p_tmp = 1 / math.sqrt(denominator) * 100  
        precision.append(p_tmp)
    precision = np.array(precision)

    fig, ax1 = plt.subplots(figsize=(8, 6))
    
    color_tsc = 'tab:blue'
    ax1.set_xlabel(r'$\mathcal{L}/\mathcal{L}_{0}$', fontsize=14)
    ax1.set_ylabel('TSC within 1 ms (mA)', fontsize=14, color=color_tsc)
    
    slope, intercept = np.polyfit(lumi_ratio, tsc, 1)
    fit_tsc = slope * lumi_ratio + intercept
    
    ax1.scatter(lumi_ratio, tsc, color=color_tsc, marker='o', s=80, 
               edgecolor='k', alpha=0.8, label='TSC Data')
    ax1.plot(lumi_ratio, fit_tsc, color=color_tsc, linestyle='--', 
            linewidth=2, label=f'TSC Fit')
    
    ax1.tick_params(axis='y', labelcolor=color_tsc, labelsize=12)
    ax1.tick_params(axis='x', labelsize=12)
    ax1.grid(True, linestyle=':', alpha=0.6)

    ax2 = ax1.twinx()
    color_precision = 'tab:red'
    ax2.set_ylabel('Relative precision (%)', fontsize=14, color=color_precision)
    
    def fit_func(x, a):
        return a / np.sqrt(x)
    params, _ = curve_fit(fit_func, lumi_ratio, precision)
    a_fit = params[0]
    x_fit = np.linspace(0.1, 1.0, 300)
    y_fit = fit_func(x_fit, a_fit)
    
    ax2.scatter(lumi_ratio, precision, color=color_precision, marker='s', s=80, 
               edgecolor='k', alpha=0.8, label='Relative precision Data')
    ax2.plot(x_fit, y_fit, color=color_precision, linestyle='-', 
            linewidth=2, label=f'Relative precision Fit')
    
    ax2.tick_params(axis='y', labelcolor=color_precision, labelsize=12)
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, 
             loc='upper center', fontsize=12, framealpha=0.9)
    
    plt.savefig("src/raser/apps/lumi/figs/sample_lumi_fit.pdf")

if __name__ == "__main__":
    main()