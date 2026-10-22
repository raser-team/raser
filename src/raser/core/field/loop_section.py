# #!/usr/bin/env python3
# # -*- encoding: utf-8 -*-

# '''
# @File    :   loop_section.py
# @Time    :   2025/05
# @Author  :   Sen Zhao
# @Version :   1.0
# '''

# import os
# import pickle

# import devsim
# import numpy as np

# from . import initial
# from . import physics_drift_diffusion
# from .create_parameter import delete_init
# from raser.supports.output import output
# from raser.supports.memory_decorator import memory_decorator

# class loop_section:
#     def __init__(self, paras, device, region, solve_model, irradiation):
#         self.paras = paras
#         self.step_model  = False
#         self.solve_model = solve_model
#         self.device = device
#         self.region = region
#         self.irradiation = irradiation
#         self.voltage = []
#         self.current = []
#         self.capacitance = []
#         self.noise = []
#         self.voltage_milestone = []
#         self.positions_mid = []
#         self.intensities = []

#         self.positions = []
#         self.electrons = []
#         self.holes = []

#     def initial_solver(self, contact, set_contact_type, irradiation_model, irradiation_flux, impact_model,):
#         initial.PotentialOnlyInitialSolution(device=self.device, region=self.region, circuit_contacts=contact, paras=self.paras, set_contact_type=set_contact_type,)
#         devsim.solve(type="dc", absolute_error=self.paras['absolute_error_Initial'], relative_error=self.paras['relative_error_Initial'], maximum_iterations=self.paras['maximum_iterations_Initial'],)
#         print("======================\nFirst initialize successfully\n===============================")
#         if self.solve_model == "wf":
#             pass
#         else:
#             print("======RASER info ===========\nradiation\n================info=================")
#             initial.DriftDiffusionInitialSolution(device=self.device,region=self.region,circuit_contacts=contact,paras=self.paras,set_contact_type=set_contact_type,irradiation_model=irradiation_model,
#             irradiation_flux=irradiation_flux,impact_model=impact_model,)

#             # 第一次只求解本征缺陷 N_t0。
#             # 对 flux>0，physics_irradiation.py 中 IrradiationScale 初始为0。
#             devsim.solve(type="dc",absolute_error=self.paras["absolute_error_Initial"],relative_error=self.paras["relative_error_Initial"],maximum_iterations=self.paras["maximum_iterations_Initial"],)

#             # 从本征缺陷逐渐增加到目标辐照缺陷浓度。
#             if (irradiation_model is not None and float(irradiation_flux or 0.0) > 0.0):
#                 irradiation_scales = (1.0e-6,1.0e-5,1.0e-4,1.0e-3,1.0e-2,5.0e-2,1.0e-1,2.0e-1,4.0e-1,6.0e-1,8.0e-1,1.0,)

#                 for irradiation_scale in irradiation_scales:
#                     print("Loading irradiation defects: scale={:.6g}".format(irradiation_scale))

#                     devsim.set_parameter(device=self.device,region=self.region,name="IrradiationScale",value=irradiation_scale,)

#                     devsim.solve(type="dc",absolute_error=self.paras["absolute_error_Initial"],relative_error=self.paras["relative_error_Initial"],maximum_iterations=self.paras["maximum_iterations_Initial"],)

#             # 缺陷完全加载并收敛后，再逐步打开 U_const。
#             for scale in (1.0e-6, 1.0e-4, 1.0e-2, 1.0):
#                 devsim.set_parameter(device=self.device, region=self.region,name="U_const_scale",value=scale,)
#             # initial.DriftDiffusionInitialSolution(device=self.device, region=self.region, circuit_contacts=contact,paras=self.paras,set_contact_type=set_contact_type,
#             #                                     irradiation_model=irradiation_model,irradiation_flux=irradiation_flux,impact_model=impact_model,)
#             # devsim.solve(type="dc", absolute_error=self.paras['absolute_error_Initial'], relative_error=self.paras['relative_error_Initial'], maximum_iterations=self.paras['maximum_iterations_Initial'],)
#             # for scale in (1e-6, 1e-4, 1e-2, 1.0):
#             #     devsim.set_parameter(device=self.device, region=self.region, name="U_const_scale", value=scale)
#                 devsim.solve(
#                     type="dc",
#                     absolute_error=self.paras['absolute_error_Initial'],
#                     relative_error=self.paras['relative_error_Initial'],
#                     maximum_iterations=self.paras['maximum_iterations_Initial']
#                     )
#         # eliminate calculation fatals from intrinsic carrier concentration
#         delete_init(device=self.device, region=self.region)

#         print("=====================\nDriftDiffusion initialize successfully\n======================")
#         print("=========RASER info =========\nAll initialization successfully\n=========info========== ")    

#     @memory_decorator
#     def loop_solver(self, circuit_contact, v_trial, area_factor):
#         devsim.set_parameter(device=self.device, name=physics_drift_diffusion.GetContactBiasName(circuit_contact), value=v_trial,)
#         try:
#             devsim.solve(type="dc", absolute_error=self.paras['absolute_error_VoltageSteps'], relative_error=self.paras['relative_error_VoltageSteps'], maximum_iterations=self.paras['maximum_iterations_VoltageSteps'],)
#             self.voltage.append(v_trial)
#         except devsim.error as msg:
#             path = output(__file__, "default")
#             devsim.write_devices(file=os.path.join(path, "last_solvable.dd"), type="tecplot")
#             raise
        
#         if self.solve_model !="wf":     
#             physics_drift_diffusion.PrintCurrents(device=self.device, contact=circuit_contact)
#             electron_current = devsim.get_contact_current(device=self.device, contact=circuit_contact, equation="ElectronContinuityEquation",)
#             hole_current     = devsim.get_contact_current(device=self.device, contact=circuit_contact, equation="HoleContinuityEquation",)
#             total_current    = electron_current + hole_current
#             self.current.append(total_current*area_factor)
#             if self.solve_model == "cv":
#                 devsim.circuit_alter(name="V1", value=v_trial)
#                 devsim.solve(type="ac", frequency=self.paras["frequency"])
#                 cap= (1e12*devsim.get_circuit_node_value(node="V1.I", solution="ssac_imag")/ (-2*np.pi*self.paras["frequency"])) # pF/cm^dim
#                 self.capacitance.append(cap*area_factor)
#             if self.solve_model == "noise":
#                 devsim.solve(type="noise", frequency=self.paras["frequency"],output_node="V1.I")
#                 noise=devsim.get_circuit_node_value(node="V1.I")
#                 self.noise.append(noise)

#     def get_voltage_values(self):
#         return self.voltage
#     def get_current_values(self):
#         return self.current
#     def get_cap_values(self):
#         return self.capacitance
#     def get_noise_values(self):
#         return self.noise
# !/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os

import devsim
import numpy as np

from . import initial
from . import physics_drift_diffusion
from .create_parameter import delete_init
from raser.supports.output import output
from raser.supports.memory_decorator import memory_decorator


class loop_section:
    def __init__(
        self,
        paras,
        device,
        region,
        solve_model,
        irradiation,
    ):
        self.paras = paras
        self.step_model = False
        self.solve_model = solve_model
        self.device = device
        self.region = region
        self.irradiation = irradiation

        self.voltage = []
        self.current = []
        self.capacitance = []
        self.noise = []

        self.voltage_milestone = []
        self.positions_mid = []
        self.intensities = []

        self.positions = []
        self.electrons = []
        self.holes = []

        self.last_converged_bias = 0.0
        self.backup_solutions_created = False
        self.backup_solution_pairs = None
    def _save_converged_state(self):
        all_pairs = (
            ("Potential", "__backup_Potential"),
            ("Electrons", "__backup_Electrons"),
            ("Holes", "__backup_Holes"),
        )

        available_models = set(
            devsim.get_node_model_list(
                device=self.device,
                region=self.region,
            )
        )

        # 只备份当前模式中实际存在的解变量。
        # -wf 模式通常只有 Potential。
        if self.backup_solution_pairs is None:
            self.backup_solution_pairs = tuple(
                (
                    solution_name,
                    backup_name,
                )
                for solution_name, backup_name in all_pairs
                if solution_name in available_models
            )

        if not self.backup_solution_pairs:
            return

        if not self.backup_solutions_created:
            for _, backup_name in self.backup_solution_pairs:
                existing_models = set(
                    devsim.get_node_model_list(
                        device=self.device,
                        region=self.region,
                    )
                )

                if backup_name not in existing_models:
                    devsim.node_solution(
                        device=self.device,
                        region=self.region,
                        name=backup_name,
                    )

            self.backup_solutions_created = True

        for solution_name, backup_name in self.backup_solution_pairs:
            devsim.set_node_values(
                device=self.device,
                region=self.region,
                name=backup_name,
                init_from=solution_name,
            )
    # def _save_converged_state(self):
    #     backup_pairs = (
    #         ("Potential", "__backup_Potential"),
    #         ("Electrons", "__backup_Electrons"),
    #         ("Holes", "__backup_Holes"),
    #     )

    #     if not self.backup_solutions_created:
    #         for _, backup_name in backup_pairs:
    #             devsim.node_solution(
    #                 device=self.device,
    #                 region=self.region,
    #                 name=backup_name,
    #             )

    #         self.backup_solutions_created = True

    #     for solution_name, backup_name in backup_pairs:
    #         devsim.set_node_values(
    #             device=self.device,
    #             region=self.region,
    #             name=backup_name,
    #             init_from=solution_name,
    #         )
    def _restore_converged_state(self):
        if not self.backup_solution_pairs:
            return

        for solution_name, backup_name in self.backup_solution_pairs:
            devsim.set_node_values(
                device=self.device,
                region=self.region,
                name=solution_name,
                init_from=backup_name,
            )
    # def _restore_converged_state(self):
    #     backup_pairs = (
    #         ("Potential", "__backup_Potential"),
    #         ("Electrons", "__backup_Electrons"),
    #         ("Holes", "__backup_Holes"),
    #     )

        for solution_name, backup_name in backup_pairs:
            devsim.set_node_values(
                device=self.device,
                region=self.region,
                name=solution_name,
                init_from=backup_name,
            )

    def initial_solver(
        self,
        contact,
        set_contact_type,
        irradiation_model,
        irradiation_flux,
        impact_model,
    ):
        initial.PotentialOnlyInitialSolution(
            device=self.device,
            region=self.region,
            circuit_contacts=contact,
            paras=self.paras,
            set_contact_type=set_contact_type,
        )

        devsim.solve(
            type="dc",
            absolute_error=self.paras[
                "absolute_error_Initial"
            ],
            relative_error=self.paras[
                "relative_error_Initial"
            ],
            maximum_iterations=self.paras[
                "maximum_iterations_Initial"
            ],
        )

        print(
            "======================\n"
            "First initialize successfully\n"
            "==============================="
        )

        if self.solve_model != "wf":
            print(
                "======RASER info===========\n"
                "radiation\n"
                "================info================="
            )

            initial.DriftDiffusionInitialSolution(
                device=self.device,
                region=self.region,
                circuit_contacts=contact,
                paras=self.paras,
                set_contact_type=set_contact_type,
                irradiation_model=irradiation_model,
                irradiation_flux=irradiation_flux,
                impact_model=impact_model,
            )

            is_diamond_irradiation = (
                irradiation_model
                in ("Diamond", "Diamond3Level")
                and float(irradiation_flux or 0.0) > 0.0
            )

            if is_diamond_irradiation:
                devsim.set_parameter(
                    device=self.device,
                    region=self.region,
                    name="IrradiationScale",
                    value=0.0,
                )

            # 先求解只有 N_t0 的状态
            devsim.solve(
                type="dc",
                absolute_error=self.paras[
                    "absolute_error_Initial"
                ],
                relative_error=self.paras[
                    "relative_error_Initial"
                ],
                maximum_iterations=self.paras[
                    "maximum_iterations_Initial"
                ],
            )

            # 逐步增加辐照缺陷浓度
            if is_diamond_irradiation:
                irradiation_scales = (
                    1.0e-6,
                    1.0e-5,
                    1.0e-4,
                    1.0e-3,
                    1.0e-2,
                    5.0e-2,
                    1.0e-1,
                    2.0e-1,
                    4.0e-1,
                    6.0e-1,
                    8.0e-1,
                    1.0,
                )

                for irradiation_scale in irradiation_scales:
                    print(
                        "Loading irradiation defects: "
                        "scale={:.6g}".format(
                            irradiation_scale
                        )
                    )

                    devsim.set_parameter(
                        device=self.device,
                        region=self.region,
                        name="IrradiationScale",
                        value=irradiation_scale,
                    )

                    devsim.solve(
                        type="dc",
                        absolute_error=self.paras[
                            "absolute_error_Initial"
                        ],
                        relative_error=self.paras[
                            "relative_error_Initial"
                        ],
                        maximum_iterations=self.paras[
                            "maximum_iterations_Initial"
                        ],
                    )

        delete_init(
            device=self.device,
            region=self.region,
        )

        print(
            "=====================\n"
            "DriftDiffusion initialize successfully\n"
            "======================"
        )

        print(
            "=========RASER info=========\n"
            "All initialization successfully\n"
            "=========info=========="
        )

    @memory_decorator
    def loop_solver(
        self,
        circuit_contact,
        v_trial,
        area_factor,
    ):
        bias_name = (
            physics_drift_diffusion
            .GetContactBiasName(circuit_contact)
        )

        # 保存上一个收敛状态
        self._save_converged_state()

        devsim.set_parameter(
            device=self.device,
            name=bias_name,
            value=v_trial,
        )

        try:
            devsim.solve(
                type="dc",
                absolute_error=self.paras[
                    "absolute_error_VoltageSteps"
                ],
                relative_error=self.paras[
                    "relative_error_VoltageSteps"
                ],
                maximum_iterations=self.paras[
                    "maximum_iterations_VoltageSteps"
                ],
            )

        except devsim.error:
            # 失败后恢复上一个收敛解
            self._restore_converged_state()

            devsim.set_parameter(
                device=self.device,
                name=bias_name,
                value=self.last_converged_bias,
            )

            raise

        self.last_converged_bias = float(v_trial)
        self.voltage.append(float(v_trial))

        if self.solve_model != "wf":
            physics_drift_diffusion.PrintCurrents(
                device=self.device,
                contact=circuit_contact,
            )

            electron_current = devsim.get_contact_current(
                device=self.device,
                contact=circuit_contact,
                equation="ElectronContinuityEquation",
            )

            hole_current = devsim.get_contact_current(
                device=self.device,
                contact=circuit_contact,
                equation="HoleContinuityEquation",
            )

            total_current = (
                electron_current + hole_current
            )

            self.current.append(
                total_current * area_factor
            )

            if self.solve_model == "cv":
                devsim.circuit_alter(
                    name="V1",
                    value=v_trial,
                )

                devsim.solve(
                    type="ac",
                    frequency=self.paras["frequency"],
                )

                capacitance = (
                    1e12
                    * devsim.get_circuit_node_value(
                        node="V1.I",
                        solution="ssac_imag",
                    )
                    / (
                        -2.0
                        * np.pi
                        * self.paras["frequency"]
                    )
                )

                self.capacitance.append(
                    capacitance * area_factor
                )

            if self.solve_model == "noise":
                devsim.solve(
                    type="noise",
                    frequency=self.paras["frequency"],
                    output_node="V1.I",
                )

                noise = devsim.get_circuit_node_value(
                    node="V1.I",
                )

                self.noise.append(noise)

    def get_voltage_values(self):
        return self.voltage

    def get_current_values(self):
        return self.current

    def get_cap_values(self):
        return self.capacitance

    def get_noise_values(self):
        return self.noise