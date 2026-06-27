#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
import gmsh

from raser.supports.output import create_path
from raser.supports.paths import project_path
geo = gmsh.model.geo

gmsh.initialize()
gmsh.model.add("CMOS_strip")

lc_bulk = 1e-4
lc_bottom_mid = 5e-5
lc_bottom_mid_2 = 3e-5
lc_bottom = 1e-5

lp = 1e-5
ln_up = 1e-5
ln = 1e-5
ln_well = 2e-5

# bulk points
P1 = geo.addPoint(0.4e-4, 0, 0, lp)
P2 = geo.addPoint(0.4e-4, 75.5e-4, 0, lp)
P3 = geo.addPoint(150e-4, 75.5e-4, 0, lc_bottom)
P4 = geo.addPoint(150e-4, 0, 0, lc_bottom)

P17 = geo.addPoint(147e-4, 75.5e-4, 0, lc_bottom_mid)
P18 = geo.addPoint(147e-4, 0, 0, lc_bottom_mid)

P1701 = geo.addPoint(149e-4, 75.5e-4, 0, lc_bottom_mid_2)
P1801 = geo.addPoint(149e-4, 0, 0, lc_bottom_mid_2)

P29 = geo.addPoint(10e-4, 75.5e-4, 0, lc_bulk)
P30 = geo.addPoint(10e-4, 0, 0, lc_bulk)

P31 = geo.addPoint(140e-4, 75.5e-4, 0, lc_bulk)
P32 = geo.addPoint(140e-4, 0, 0, lc_bulk)

# p stop 1
# P1 = geo.addPoint(0.4e-4, 0, 0, lp)
P6 = geo.addPoint(0.4e-4, 1e-4, 0, lp)
P7 = geo.addPoint(0e-4, 1e-4, 0, lp)
P8 = geo.addPoint(0e-4, 0, 0, lp)

L1 = geo.addLine(P1, P8)
L2 = geo.addLine(P8, P7)
L3 = geo.addLine(P7, P6)
L15 = geo.addLine(P1, P6)

loop1 = geo.addCurveLoop([L1, L2, L3, -L15])
surf1 = geo.addPlaneSurface([loop1])

# p well 1
P19 = geo.addPoint(1.6e-4, 0, 0, lp)
P20 = geo.addPoint(1.6e-4, 1e-4, 0, lp)
# P1 = geo.addPoint(0.4e-4, 0, 0, lp)
# P6 = geo.addPoint(0.4e-4, 1e-4, 0, lp)

L21 = geo.addLine(P1, P19)
L22 = geo.addLine(P19, P20)
L23 = geo.addLine(P20, P6)
# L15 = geo.addLine(P1, P6)

loop2 = geo.addCurveLoop([L21, L22, L23, -L15])
surf2 = geo.addPlaneSurface([loop2])

P2001 = geo.addPoint(1.6e-4, 3e-4, 0, lp)
P0601 = geo.addPoint(0.4e-4, 3e-4, 0, lp)

L2201 = geo.addLine(P20, P2001)
L2301 = geo.addLine(P2001, P0601)
L1501 = geo.addLine(P6, P0601)

loop201 = geo.addCurveLoop([L2201, L2301, -L1501, -L23])
surf201 = geo.addPlaneSurface([loop201])

# p stop 2
P9 = geo.addPoint(0.4e-4,74.5e-4, 0, lp)
# P2 = geo.addPoint(0.4e-4,75.5e-4, 0, lp)
P11 = geo.addPoint(0e-4,75.5e-4, 0, lp)
P12 = geo.addPoint(0e-4,74.5e-4, 0, lp)

L9 = geo.addLine(P9, P12)
L10 = geo.addLine(P12, P11)
L11 = geo.addLine(P11, P2)
L17 = geo.addLine(P9, P2)

loop3 = geo.addCurveLoop([L9, L10, L11, -L17])
surf3 = geo.addPlaneSurface([loop3])

# p well 2

P21 = geo.addPoint(1.6e-4,75.5e-4, 0, lp)
P22 = geo.addPoint(1.6e-4,74.5e-4, 0, lp)
# P9 = geo.addPoint(0.4e-4,74.5e-4, 0, lp)
# P2 = geo.addPoint(0.4e-4,75.5e-4, 0, lp)

L24 = geo.addLine(P2, P21)
L25 = geo.addLine(P21, P22)
L26 = geo.addLine(P22, P9)
# L17 = geo.addLine(P9, P2)

loop4 = geo.addCurveLoop([L24, L25, L26, L17])
surf4 = geo.addPlaneSurface([loop4])

P2201 = geo.addPoint(1.6e-4,72.5e-4, 0, lp)
P0901 = geo.addPoint(0.4e-4,72.5e-4, 0, lp)

L2501 = geo.addLine(P22, P2201)
L2601 = geo.addLine(P2201, P0901)
L1701 = geo.addLine(P0901, P9)

loop401 = geo.addCurveLoop([L2501, L2601, L1701, -L26])
surf401 = geo.addPlaneSurface([loop401])

# n stop
P13 = geo.addPoint(0.4e-4, 30.25e-4, 0, ln_up)
P14 = geo.addPoint(0.4e-4, 45.25e-4, 0, ln_up)
P23 = geo.addPoint(0.2e-4, 45.25e-4, 0, ln_up)
P24 = geo.addPoint(0.2e-4, 30.25e-4, 0, ln_up)
P15 = geo.addPoint(0e-4, 45.25e-4, 0, ln_up)
P16 = geo.addPoint(0e-4, 30.25e-4, 0, ln_up)

L27 = geo.addLine(P15, P23)
L28 = geo.addLine(P23, P24)
L29 = geo.addLine(P24, P16)
L6 = geo.addLine(P16, P15)

loop5 = geo.addCurveLoop([L27, L28, L29, L6])
surf5 = geo.addPlaneSurface([loop5])

L5 = geo.addLine(P23, P14)
L35 = geo.addLine(P13, P14)
L7 = geo.addLine(P13, P24)
# L28 = geo.addLine(P23, P24)

loop6 = geo.addCurveLoop([L5, -L35, L7, -L28])
surf6 = geo.addPlaneSurface([loop6])

# n well

P25 = geo.addPoint(1.2e-4, 46.75e-4, 0, ln_well)
P26 = geo.addPoint(1.2e-4, 28.75e-4, 0, ln_well)
P27 = geo.addPoint(0.4e-4, 46.75e-4, 0, ln_well)
P28 = geo.addPoint(0.4e-4, 28.75e-4, 0, ln_well)
# P13 = geo.addPoint(0.4e-4, 30.25e-4, 0, ln_up)
# P14 = geo.addPoint(0.4e-4, 45.25e-4, 0, ln_up)

L30 = geo.addLine(P28, P26)
L31 = geo.addLine(P26, P25)
L32 = geo.addLine(P25, P27)
L33 = geo.addLine(P27, P14)
L34 = geo.addLine(P13, P28)
# L35 = geo.addLine(P13, P14)

loop7 = geo.addCurveLoop([L30, L31, L32, L33, -L35, L34])
surf7 = geo.addPlaneSurface([loop7])

# bulk lines & surfaces

# L22 = geo.addLine(P19, P20)
# L2201 = geo.addLine(P20, P2001)
# L2301 = geo.addLine(P2001, P0601)
L4 = geo.addLine(P0601, P28)
# L30 = geo.addLine(P28, P26)
# L31 = geo.addLine(P26, P25)
# L32 = geo.addLine(P25, P27)
L36 = geo.addLine(P27, P0901)
# L2601 = geo.addLine(P2201, P0901)
# L2501 = geo.addLine(P22, P2201)
# L25 = geo.addLine(P21, P22)
L12 = geo.addLine(P21, P29)
L13 = geo.addLine(P29, P30)
L14 = geo.addLine(P30, P19)

loop8 = geo.addCurveLoop([L22, L2201, L2301, L4, L30, L31, L32, L36, -L2601, -L2501, -L25, L12, L13, L14])
surf8 = geo.addPlaneSurface([loop8])

L18 = geo.addLine(P31, P29)
L19 = geo.addLine(P31, P32)
L20 = geo.addLine(P30, P32)
# L13 = geo.addLine(P29, P30)

loop9 = geo.addCurveLoop([-L18, L19, -L20, -L13])
surf9 = geo.addPlaneSurface([loop9])

L40 = geo.addLine(P31, P17)
L41 = geo.addLine(P17, P18)
L42 = geo.addLine(P18, P32)
# L19 = geo.addLine(P31, P32)

loop10 = geo.addCurveLoop([L40, L41, L42, -L19])
surf10 = geo.addPlaneSurface([loop10])

L3701 = geo.addLine(P17, P1701)
L3801 = geo.addLine(P1701, P1801)
L3901 = geo.addLine(P1801, P18)
# L41 = geo.addLine(P17, P18)

loop11 = geo.addCurveLoop([L3701, L3801, L3901, -L41])
surf11 = geo.addPlaneSurface([loop11])

L37 = geo.addLine(P1701, P3)
L38 = geo.addLine(P3, P4)
L39 = geo.addLine(P4, P1801)
# L3801 = geo.addLine(P1701, P1801)

loop12 = geo.addCurveLoop([L37, L38, L39, -L3801])
surf12 = geo.addPlaneSurface([loop12])

geo.synchronize()

gmsh.model.addPhysicalGroup(1, [L38], name="bot")
gmsh.model.addPhysicalGroup(1, [L6], name="top")

gmsh.model.addPhysicalGroup(2, [surf1, surf2, surf3, surf4, surf5, surf6, surf7, surf8, surf9, surf10, surf11, surf12, surf201, surf401], name="CMOS_strip")

gmsh.option.setNumber("Geometry.MatchMeshTolerance", 1e-12)
gmsh.model.mesh.generate(2)

gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
mesh_path = project_path("components", "detector", "CMOS_strip.msh")
create_path(mesh_path.parent)
gmsh.write(str(mesh_path))
gmsh.finalize()
# gmsh.fltk.run()
