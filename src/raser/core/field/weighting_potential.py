#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
@File    :   weighting_potential.py
@Time    :   2025/04/01
@Author  :   Chenxi Fu
@Version :   1.0
'''

import pickle

import numpy as np

from . import devsim_draw
from raser.supports.output import create_path
from raser.supports.paths import project_path

def main(v, electrode_name, det_name):
    v = float(v)

    potential_file = project_path("field",det_name, "Potential_"+str(v)+'V.pkl')
    added_potential_file = project_path(
        "field",det_name,
        "weightingfield",electrode_name,
        "Potential_"+str(v)+'V.pkl',
    )
    with open(potential_file,'rb') as file:
        potential = pickle.load(file)
    with open(added_potential_file,'rb') as file:
        added_potential = pickle.load(file)
    values = np.array(potential['values'])
    added_values = np.array(added_potential['values'])
    points = potential['points']
    dimension = potential['metadata']['dimension']

    values = (added_values-values)/1 
    # assume 1 volt added for weighting field calculation

    w_p_data = {'points': points, 'values': values, 'metadata':{'voltage': 1, 'dimension': dimension},}
    path = project_path("field",det_name, "weightingfield",electrode_name)
    create_path(path)
    w_p_file = path / 'Potential_1V.pkl'
    with open(w_p_file, 'wb') as file:
        pickle.dump(w_p_data, file)

    if dimension == 1:
        devsim_draw.draw1D(points, values, "Weighting Potential", "Depth[um]", "Weighting Potential", 1, path,)

    elif dimension == 2:
        x = [point[0] for point in points]
        y = [point[1] for point in points]
        devsim_draw.draw2D(x, y, values, "Weighting Potential", 1, path)
        
    elif dimension == 3:
        x = [point[0] for point in points]
        y = [point[1] for point in points]
        z = [point[2] for point in points]
        devsim_draw.draw3D(x, y, z, values, "Weighting Potential", 1, path)

if __name__ == '__main__':
    import sys
    args = sys.argv
    main(args[1], args[2], args[3])
