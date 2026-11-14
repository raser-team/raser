"""
@Date       : 2025/06/05
@Author     : Tao Yang, Sen Zhao, Chenxi Fu
@version    : 2.0
"""

import os
from pathlib import Path

import devsim
import matplotlib.pyplot as plt

from ..device.build_device import Detector
from raser.supports.output import create_path
from raser.supports.output import output
from . import model_create


def mesh_axes(my_d):
    """The device axis that each coordinate of the device's mesh runs along."""
    if my_d.dimension == 1:
        return ("z",)
    if my_d.dimension == 2:
        plugin = my_d.device_dict.get("mesh", {}).get("plugin", False)
        return ("x", "y") if plugin else ("z", "x")
    return ("x", "y", "z") if my_d.mesher == "sde" else ("z", "x", "y")


class DevsimMesh:
    def __init__(self, my_d: Detector, devsim_solve_paras, output_directory=None):
        self.device_dict = my_d.device_dict
        self.det_name = my_d.det_name
        self.dimension = my_d.dimension
        self.device = my_d.device
        self.region = my_d.region
        self.solve_paras = devsim_solve_paras
        self.output_directory = output_directory
        self.file = my_d.file

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
        if self.output_directory is None:
            path = output(__file__, "default")
        else:
            path = str(create_path(Path(self.output_directory)))
        if ( self.solve_paras["weightfield"] == True or self.solve_paras["ac-weightfield"] == True
        ):
            pass
        else:
            self.drawDoping(path)

        devsim.write_devices(file=os.path.join(path, self.det_name+".dat"),type="tecplot")

    def _regions(self, mesh, keep_air=True):
        """The regions of a mesh block as devsim is given them. For a weighting
        field the material of each is replaced by "gas", a dielectric; "air",
        the space left for an electrode, stays unless `keep_air` is False."""
        if self.solve_paras["weightfield"] != True:
            return mesh["region"]
        return [
            region if keep_air and region["material"] == "air" else {**region, "material": "gas"}
            for region in mesh["region"]
        ]

    def create1DMesh(self):
        mesh_name = self.device
        devsim.create_1d_mesh(mesh=mesh_name)
        mesh = self.device_dict["mesh"]["1D_mesh"]
        for mesh_line in mesh["mesh_line"]:
            devsim.add_1d_mesh_line(mesh=mesh_name, **mesh_line)
        for region in self._regions(mesh):
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
        for region in self._regions(mesh):
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
        # HEMT_TRANSPORT_V1_INTERFACE
        if (
            self.device_dict.get("hemt_physics", {}).get("transport_model")
            == "drift_diffusion_v1"
            and not self.solve_paras.get("ac-weightfield", False)
        ):
            interfaces = mesh.get("interface", [])
            if not interfaces:
                raise ValueError("HEMT transport requires a configured mesh interface")
            for interface in interfaces:
                devsim.add_2d_interface(mesh=mesh_name, **interface)

        devsim.finalize_mesh(mesh=mesh_name)
        devsim.create_device(mesh=mesh_name, device=mesh_name)

    def createGmshMesh(self):
        mesh_name = self.device
        mesh = self.device_dict["mesh"]["gmsh_mesh"]
        mesh_file = self.file(mesh["file"])
        devsim.create_gmsh_mesh (mesh=mesh_name, file=str(mesh_file))
        for region in self._regions(mesh, keep_air=False):
            devsim.add_gmsh_region   (mesh=mesh_name ,**region)
        for contact in mesh["contact"]:
            devsim.add_gmsh_contact  (mesh=mesh_name, **contact)
        devsim.finalize_mesh(mesh=mesh_name)
        devsim.create_device(mesh=mesh_name, device=mesh_name)

    def setDoping(self):
        '''
        Doping
        '''
        doping = self.device_dict["doping"]
        if ( self.solve_paras["weightfield"] == True or self.solve_paras["ac-weightfield"] == True
        ):
            # The weighting field is solved without the doping of the device.
            doping = {**doping, "Acceptors": "0", "Donors": "1"}
        if 'Acceptors_ir' in doping:
            model_create.CreateNodeModel(self.device, self.region, "Acceptors", doping['Acceptors']+"+"+doping['Acceptors_ir'],)
        else:
            model_create.CreateNodeModel(self.device, self.region, "Acceptors", doping['Acceptors'],)
        if 'Donors_ir' in doping:
            model_create.CreateNodeModel(self.device, self.region, "Donors",    doping['Donors']+"+"+doping['Donors_ir'],)
        else:
            model_create.CreateNodeModel(self.device, self.region, "Donors",    doping['Donors'])
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
