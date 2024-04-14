#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import devsim
from . import model_create

from util.output import output
import json
import os

import matplotlib.pyplot

class Detector:
    """
    Description:
    ---------
        Different types detectors parameters assignment.
    Parameters:
    ---------
    device_name : string
        name the device and define the device by device.json 
    dimension : int
        the dimension of devsim mesh
    Modify:
    ---------
        2023/12/03
    """ 
    def __init__(self, device_name):
        self.det_name = device_name
        self.device = device_name
        self.region = device_name
        device_json = "./setting/detector/" + device_name + ".json"
        with open(device_json) as f:
            self.device_dict = json.load(f)

        self.dimension = self.device_dict['default_dimension']

        self.l_x = self.device_dict['lx'] 
        self.l_y = self.device_dict['ly']  
        self.l_z = self.device_dict['lz'] 
        
        self.voltage = self.device_dict['bias']['voltage'] 
        self.temperature = self.device_dict['temperature']
        self.material = self.device_dict['material']
        self.det_model = self.device_dict['det_model']

        self.doping = self.device_dict['doping']

        self.absorber = self.device_dict['absorber']
        self.amplifier = self.device_dict['amplifier']

        if "lgad3D" in self.det_model:
            self.avalanche_bond = self.device_dict['avalanche_bond']
            self.avalanche_model = self.device_dict['avalanche_model']
            
        if 'plugin3D' in self.det_model: 
            self.e_r = self.device_dict['e_r']
            self.e_gap = self.device_dict['e_gap']
            self.e_t = self.device_dict['e_t']

        if "planarRing" in self.det_model:
            self.e_r_inner = self.device_dict['e_r_inner']
            self.e_r_outer = self.device_dict['e_r_outer']

        if "strip" in self.det_name or "Strip" in self.det_name: 
            # TODO: change this into model
            self.read_ele_num = self.device_dict['read_ele_num']
            
        if "pixeldetector" in self.det_model:
            self.p_x = self.device_dict['px']
            self.p_y = self.device_dict['py']
            self.p_z = self.device_dict['pz']
            self.lt_z = self.device_dict['ltz']
            self.seedcharge = self.device_dict['seedcharge']

    def mesh_define(self):
        if self.dimension == 1:
            self.create1DMesh()
        elif self.dimension == 2:
            self.create2DMesh()
        elif self.dimension == 3:
            self.createGmshMesh()
        else:
            raise ValueError(self.dimension)

        self.setDoping()
        path = output(__file__, self.det_name)

        if "irradiation" in self.device_dict:
            path = output(__file__, str(self.det_name)+"/"+str(self.device_dict['irradiation']['irradiation_flux']))
        self.drawDoping(path)
        devsim.write_devices(file=os.path.join(path, self.det_name+".dat"),type="tecplot")

    def create1DMesh(self):
        mesh_name = self.device
        devsim.create_1d_mesh(mesh=mesh_name)
        mesh = self.device_dict["mesh"]["1D_mesh"]
        for mesh_line in mesh["mesh_line"]:
            devsim.add_1d_mesh_line(mesh=mesh_name, **mesh_line)
        for region in mesh["region"]:
            devsim.add_1d_region   (mesh=mesh_name, **region)
        for contact in mesh["contact"]:
            devsim.add_1d_contact  (mesh=mesh_name, **contact)
        devsim.finalize_mesh(mesh=mesh_name)
        devsim.create_device(mesh=mesh_name, device=mesh_name)

    def create2DMesh(self):
        mesh_name = self.device
        devsim.create_2d_mesh(mesh=mesh_name)
        mesh = self.device_dict["mesh"]["2D_mesh"]
        for mesh_line in mesh["mesh_line"]:
            devsim.add_2d_mesh_line(mesh=mesh_name, **mesh_line)
        for region in mesh["region"]:
            # Must define material regions before air regions when material borders not clarified!
            devsim.add_2d_region   (mesh=mesh_name, **region)
        for contact in mesh["contact"]:
            devsim.add_2d_contact  (mesh=mesh_name, **contact)
        devsim.finalize_mesh(mesh=mesh_name)
        devsim.create_device(mesh=mesh_name, device=mesh_name)

    def createGmshMesh(self):
        mesh_name = self.device
        devsim.create_gmsh_mesh (mesh=mesh_name, file=mesh['file'])
        mesh = self.device_dict["mesh"]["gmsh_mesh"]
        for region in mesh["region"]:
            devsim.add_gmsh_region   (mesh=mesh_name, **region)
        for contact in mesh["contact"]:
            devsim.add_gmsh_contact  (mesh=mesh_name, **contact)
        devsim.finalize_mesh(mesh=mesh_name)
        devsim.create_device(mesh=mesh_name, device=mesh_name)

    def setDoping(self):
        '''
        Doping
        '''
        if 'Acceptors_ir' in self.device_dict['doping']:
          model_create.CreateNodeModel(self.device, self.region, "Acceptors",    self.device_dict['doping']['Acceptors']+"+"+self.device_dict['doping']['Acceptors_ir'])
        else:
          model_create.CreateNodeModel(self.device, self.region, "Acceptors", self.device_dict['doping']['Acceptors'])
        if 'Donors_ir' in self.device_dict['doping']:
          model_create.CreateNodeModel(self.device, self.region, "Donors",    self.device_dict['doping']['Donors']+"+"+self.device_dict['doping']['Donors_ir'])
        else:
          model_create.CreateNodeModel(self.device, self.region, "Donors",    self.device_dict['doping']['Donors'])
        model_create.CreateNodeModel(self.device, self.region, "NetDoping", "Donors-Acceptors")
        devsim.edge_from_node_model(device=self.device, region=self.region, node_model="Acceptors")
        devsim.edge_from_node_model(device=self.device, region=self.region, node_model="NetDoping")
        devsim.edge_from_node_model(device=self.device, region=self.region, node_model="Donors")

    def drawDoping(self, path):
        fig1=matplotlib.pyplot.figure(num=1,figsize=(4,4))
        x=devsim.get_node_model_values(device=self.device, region=self.region, name="x")
        fields = ("Donors", "Acceptors")

        for i in fields:
            y=devsim.get_node_model_values(device=self.device, region=self.region, name=i)
            matplotlib.pyplot.semilogy(x, y)
        
        matplotlib.pyplot.xlabel('x (cm)')
        matplotlib.pyplot.ylabel('Density (#/cm^3)')
        matplotlib.pyplot.legend(fields)
        matplotlib.pyplot.savefig(os.path.join(path, "Doping"))


if __name__ == "__main__":
    import sys
    Detector(sys.argv[1])