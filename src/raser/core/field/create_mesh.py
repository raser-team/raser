"""
@Date       : 2025/06/05
@Author     : Tao Yang, Sen Zhao, Chenxi Fu
@version    : 2.0
"""

import os
from pathlib import Path

import devsim
import numpy as np

from ..device.build_device import Detector
from raser.supports import figures
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
    def __init__(self, my_d: Detector, devsim_solve_paras, output_directory=None, cells_either_side=0):
        # The mesh of the device is one cell of a row of equal electrodes:
        # copies of it are laid side by side, this many on either side.
        self.cells_either_side = cells_either_side
        self.pitch = my_d.p_x
        self.device_dict = my_d.device_dict
        self.det_name = my_d.det_name
        self.dimension = my_d.dimension
        self.device = my_d.device
        self.region = my_d.region
        self.solve_paras = devsim_solve_paras
        self.output_directory = output_directory
        self.file = my_d.file

    def mesh_define(self):
        if self.cells_either_side:
            self.createRowOfCells()
        elif self.dimension == 1:
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

    def create2DMesh(self, mesh_name=None):
        mesh_name = mesh_name or self.device
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

    def createGmshMesh(self, mesh_name=None):
        mesh_name = mesh_name or self.device
        mesh = self.device_dict["mesh"]["gmsh_mesh"]
        mesh_file = self.file(mesh["file"])
        devsim.create_gmsh_mesh (mesh=mesh_name, file=str(mesh_file))
        for region in self._regions(mesh, keep_air=False):
            devsim.add_gmsh_region   (mesh=mesh_name ,**region)
        for contact in mesh["contact"]:
            devsim.add_gmsh_contact  (mesh=mesh_name, **contact)
        devsim.finalize_mesh(mesh=mesh_name)
        devsim.create_device(mesh=mesh_name, device=mesh_name)

    def createRowOfCells(self):
        """The mesh of the device laid side by side: its own cell in the
        middle and `cells_either_side` copies on either side, one region.

        The electrodes of the middle cell keep their names, and so do the
        electrodes that are not read out, which become one over all the cells.
        The read-out electrodes of the two cells that are as many cells
        from the middle one are one electrode, "neighbour1" for the nearest.
        The cell has to be one pitch wide, with the same nodes on its two
        faces.
        """
        if self.dimension != 2 or self.device_dict.get("mesh", {}).get("plugin", False):
            raise ValueError(
                "{}: cells are laid side by side only along x on a mesh of depth and x so far".format(
                    self.det_name
                )
            )
        cell = self.device + "_cell"
        if self.device_dict["mesh"].get("gmsh_mesh", {}):
            self.createGmshMesh(cell)
        else:
            self.create2DMesh(cell)
        depth, across = (
            np.array(devsim.get_node_model_values(device=cell, region=self.region, name=axis))
            for axis in "xy"
        )
        width, pitch = float(np.ptp(across)), float(self.pitch) * 1e-4
        if abs(width - pitch) > 1e-6 * pitch:
            raise ValueError(
                "the mesh of {} is {:g} um wide, not one pitch of {:g} um: one listed electrode "
                "that is read out over its neighbours needs the mesh of one cell".format(
                    self.det_name, width * 1e4, pitch * 1e4
                )
            )
        triangles = np.array(devsim.get_element_node_list(device=cell, region=self.region))
        read_out = [electrode["name"] for electrode in self.device_dict["read_out_contact"]]
        edges = {
            contact: np.array(devsim.get_element_node_list(device=cell, region=self.region, contact=contact))
            for contact in devsim.get_contact_list(device=cell)
            if devsim.get_region_list(device=cell, contact=contact) == (self.region,)
        }
        devsim.delete_device(device=cell)
        devsim.delete_mesh(mesh=cell)

        # Nodes of two cells at one place are one node of the row.
        copies = 2 * self.cells_either_side + 1
        places = np.concatenate(
            [np.column_stack([depth, across + number * width]) for number in range(copies)]
        )
        grain = 1e-9 * width
        row, node = np.unique(np.round(places / grain).astype(np.int64), axis=0, return_inverse=True)
        node = node.reshape(copies, -1)
        on_a_face = int(np.sum(np.abs(across - across.min()) < grain))
        if len(row) != copies * len(depth) - (copies - 1) * on_a_face:
            raise ValueError(
                "the cells of {} do not fit side by side: its two faces, one pitch apart, "
                "must hold the same nodes".format(self.det_name)
            )
        names = [self.region] + list(edges) + [
            "neighbour{}".format(apart) for apart in range(1, self.cells_either_side + 1)
        ]
        elements = []
        for number in range(copies):
            for triangle in node[number][triangles]:
                elements += [2, 0, *triangle]
            for contact, of_contact in edges.items():
                apart = abs(number - self.cells_either_side) if contact in read_out else 0
                name = names.index("neighbour{}".format(apart) if apart else contact)
                for edge in node[number][of_contact]:
                    elements += [1, name, *edge]
        coordinates = np.column_stack([row * grain, np.zeros(len(row))]).ravel()
        devsim.create_gmsh_mesh(
            mesh=self.device,
            coordinates=coordinates.tolist(),
            elements=[int(entry) for entry in elements],
            physical_names=names,
        )
        # the row is for the weighting field, whose regions are dielectric
        devsim.add_gmsh_region(mesh=self.device, gmsh_name=self.region, region=self.region, material="gas")
        for contact in names[1:]:
            devsim.add_gmsh_contact(
                mesh=self.device, gmsh_name=contact, name=contact, region=self.region, material="metal"
            )
        devsim.finalize_mesh(mesh=self.device)
        devsim.create_device(mesh=self.device, device=self.device)

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
            x = np.array(devsim.get_node_model_values(device=self.device, region=self.region, name="x"))
            depth = x * 1e-2 / figures.UNIT["um"]  # cm to um
            figure, axis = figures.new()
            colors = figures.series(2, False)
            for field, text, color in zip(("Donors", "Acceptors"), ("donors", "acceptors"), colors):
                y = devsim.get_node_model_values(device=self.device, region=self.region, name=field)
                axis.plot(depth, np.array(y) * 1e6 / figures.UNIT["cm-3"], color=color, label=text)
            axis.set_yscale("log")
            axis.set_xlabel(figures.label("Depth", "um"))
            axis.set_ylabel(figures.label("Doping", "cm-3"))
            axis.legend()
            figures.save(figure, os.path.join(path, "plots"), "doping")
        elif self.dimension == 2:
            pass
        elif self.dimension == 3:
            pass
