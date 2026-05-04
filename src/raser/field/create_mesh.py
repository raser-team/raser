'''  
@Date       : 2025/06/05
@Author     : Tao Yang, Sen Zhao, Chenxi Fu
@version    : 2.0
'''

import os

import devsim
import matplotlib.pyplot as plt

from ..device.build_device import Detector
from ..util.output import output
from . import model_create

class DevsimMesh():
    def __init__(self, my_d: Detector, devsim_solve_paras):  
        self.device_dict = my_d.device_dict
        self.det_name = my_d.det_name
        self.dimension = my_d.dimension
        self.device = my_d.device
        self.region = my_d.region
        self.solve_paras = devsim_solve_paras

    def mesh_define(self):
        if self.dimension == 1:
            self.create1DMesh()
        elif self.dimension == 2:
            if self.device_dict.get("mesh", {}).get("gmsh_mesh", {}):
                self.createGmshMesh()
            else:
                self.create2DMesh()
        elif self.dimension == 3:
            self.createGmshMesh()
        else:
            raise ValueError(self.dimension)

        self.setDoping()
        path = output(__file__, self.det_name)
        if self.solve_paras["weightfield"] == True or self.solve_paras["ac-weightfield"] == True:
            pass
        else:
            self.drawDoping(path)

        devsim.write_devices(file=os.path.join(path, self.det_name+".dat"),type="tecplot")

    def create1DMesh(self):
        mesh_name = self.device
        devsim.create_1d_mesh(mesh=mesh_name)
        mesh = self.device_dict["mesh"]["1D_mesh"]
        for mesh_line in mesh["mesh_line"]:
            devsim.add_1d_mesh_line(mesh=mesh_name, **mesh_line)
        if (self.solve_paras["weightfield"] == True) :
            for region in mesh["region"]:
                if region["material"] != "air":
                    # air for space for electrode, gas for relpacement of semiconductor
                    region["material"] = "gas"
        else:
            pass
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
        if (self.solve_paras["weightfield"] == True) :
            for region in mesh["region"]:
                if region["material"] != "air":
                    # air for space for electrode, gas for relpacement of semiconductor
                    region["material"] = "gas"
        else:
            pass
        for region in mesh["region"]:
            # Must define material regions before air regions when material borders not clarified!
            devsim.add_2d_region   (mesh=mesh_name, **region)
        
        for contact in mesh["contact"] :
            devsim.add_2d_contact  (mesh=mesh_name, **contact)
        if self.solve_paras["ac-weightfield"] == True:
            print("==============================================")
            for ac_contact in mesh["ac_contact"] :
                devsim.add_2d_contact  (mesh=mesh_name, **ac_contact)
            for interface in mesh["interface"]:
                devsim.add_2d_interface(mesh=mesh_name, **interface)
        devsim.finalize_mesh(mesh=mesh_name)
        devsim.create_device(mesh=mesh_name, device=mesh_name)

    def createGmshMesh(self):
        mesh_name = self.device
        mesh = self.device_dict["mesh"]["gmsh_mesh"]
        devsim.create_gmsh_mesh (mesh=mesh_name, file=mesh['file'])
        if (self.solve_paras["weightfield"] == True) :
            for region in mesh["region"]:
                region["material"] = "gas"
        else:
            pass
        for region in mesh["region"]:
            devsim.add_gmsh_region   (mesh=mesh_name ,**region)
        for contact in mesh["contact"]:
            devsim.add_gmsh_contact  (mesh=mesh_name, **contact)
        devsim.finalize_mesh(mesh=mesh_name)
        devsim.create_device(mesh=mesh_name, device=mesh_name)

    def setDoping(self):
        '''
        Doping
        '''
        if self.solve_paras["weightfield"] == True or self.solve_paras["ac-weightfield"] == True:
            self.device_dict["doping"]["Acceptors"] = "0"
            self.device_dict["doping"]["Donors"] = "1"
            self.device_dict.update({"doping": self.device_dict["doping"]})
        else:
            pass
        if 'Acceptors_ir' in self.device_dict['doping']:
            model_create.CreateNodeModel(self.device, self.region, "Acceptors", self.device_dict['doping']['Acceptors']+"+"+self.device_dict['doping']['Acceptors_ir'])
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
        if self.dimension == 1:
            fig1=plt.figure(num=1,figsize=(4,4))
            x=devsim.get_node_model_values(device=self.device, region=self.region, name="x")
            fields = ("Donors", "Acceptors")

            for i in fields:
                y=devsim.get_node_model_values(device=self.device, region=self.region, name=i)
                plt.semilogy(x, y)
            
            plt.xlabel('x (cm)')
            plt.ylabel('Density (#/cm^3)')
            plt.legend(fields)
            plt.savefig(os.path.join(path, "Doping"))
        elif self.dimension == 2:
            pass
        elif self.dimension == 3:
            pass
        