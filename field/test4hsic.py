import ROOT
import pickle
import numpy as np
from scipy.interpolate import Rbf
from scipy.interpolate import griddata
import math
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# TODO: rewrite this after 3D field extraction verified

def main(simname):
    if '3d' in simname:
        with open('./output/{}/x_500.0.pkl'.format(simname), 'rb') as file:
            x = pickle.load(file)
        with open('./output/{}/y_500.0.pkl'.format(simname), 'rb') as file:
            y = pickle.load(file)
        with open('./output/{}/z_500.0.pkl'.format(simname), 'rb') as file:
            z = pickle.load(file)
        with open('./output/{}/potential_500.0.pkl'.format(simname), 'rb') as file:
            potential = pickle.load(file)

        # 定义插值网格
        nPoints = 100
        x_min, x_max = np.min(x), np.max(x)
        y_min, y_max = np.min(y), np.max(y)
        z_min, z_max = np.min(z), np.max(z)

        # 进行插值
        xi = np.linspace(x_min, x_max, nPoints)
        yi = np.linspace(y_min, y_max, nPoints)
        zi = np.linspace(z_min, z_max, nPoints)
        xi, yi, zi = np.meshgrid(xi, yi, zi)
        pi = griddata((x, y, z), potential, (xi, yi, zi), method='linear')

        # 计算梯度
        dx, dy, dz = np.gradient(pi, xi[0,0,0], yi[0,0,0], zi[0,0,0])

        # 计算总场强
        total_field = np.sqrt(dx**2 + dy**2 + dz**2)
        # 绘制电势的xz平面截面图
        fig_potential_xz = plt.figure()
        ax_potential_xz = fig_potential_xz.add_subplot(111)
        ax_potential_xz.contourf(xi[:, nPoints//2, :], zi[:, nPoints//2, :], pi[:, nPoints//2, :], cmap='viridis')
        ax_potential_xz.set_xlabel('x')
        ax_potential_xz.set_ylabel('z')
        ax_potential_xz.set_title('Potential XZ Plane')
        plt.savefig('./output/{}/Potential_XZ_Plane.png'.format(simname))

        # 绘制电势的yz平面截面图
        fig_potential_yz = plt.figure()
        ax_potential_yz = fig_potential_yz.add_subplot(111)
        ax_potential_yz.contourf(yi[:, nPoints//2, :], zi[:, nPoints//2, :], pi[:, nPoints//2, :], cmap='viridis')
        ax_potential_yz.set_xlabel('y')
        ax_potential_yz.set_ylabel('z')
        ax_potential_yz.set_title('Potential YZ Plane')
        plt.savefig('./output/{}/Potential_YZ_Plane.png'.format(simname))
        # 绘制电势的xy平面截面图
        fig_xy_planes = plt.figure(figsize=(10, 10))
        for i in range(0, nPoints, 5):
            ax_xy_plane = fig_xy_planes.add_subplot(5, 5, i//5+1)
            ax_xy_plane.imshow(pi[:,:,i], extent=[x_min, x_max, y_min, y_max], cmap='viridis', origin='lower')
            ax_xy_plane.set_xlabel('x')
            ax_xy_plane.set_ylabel('y')
            ax_xy_plane.set_title('XY Plane')
        plt.tight_layout()
        plt.savefig('./output/{}/Potential_XY_Planes.png'.format(simname))
        #Plot total field XY plane
        fig_total_field_xy = plt.figure()
        ax_total_field_xy = fig_total_field_xy.add_subplot(111)
        ax_total_field_xy.contourf(xi[:, :, nPoints // 2], yi[:, :, nPoints // 2], total_field[:, :, nPoints // 2], cmap='viridis')
        ax_total_field_xy.set_xlabel('x')
        ax_total_field_xy.set_ylabel('y')
        ax_total_field_xy.set_title('Total Field XY Plane')
        plt.savefig('./output/{}/Total_Field_XY_Plane.png'.format(simname))

        #Plot total field YZ plane
        fig_total_field_yz = plt.figure()
        ax_total_field_yz = fig_total_field_yz.add_subplot(111)
        ax_total_field_yz.contourf(yi[:, nPoints // 2, :], zi[:, nPoints // 2, :], total_field[:, nPoints // 2, :], cmap='viridis')
        ax_total_field_yz.set_xlabel('y')
        ax_total_field_yz.set_ylabel('z')
        ax_total_field_yz.set_title('Total Field YZ Plane')
        plt.savefig('./output/{}/Total_Field_YZ_Plane.png'.format(simname))

        #Plot 20 dianchang XY planes
        fig_xy = plt.figure(figsize=(15, 15))
        nPlanes = 20
        for i in range(nPlanes):
            index = int(nPoints*i/(nPlanes-1)) % nPoints  # Wrap index within the range of nPoints
            ax_xy = fig_xy.add_subplot(4, 5, i+1)
            ax_xy.imshow(pi[:, :, index], extent=[x_min, x_max, y_min, y_max], cmap='viridis', origin='lower')
            ax_xy.set_xlabel('x')
            ax_xy.set_ylabel('y')
            ax_xy.set_title('XY Plane {}'.format(i+1))
        plt.tight_layout()
        plt.savefig('./output/{}/Total_Field_XY_Planes.png'.format(simname))



    else:
        # 从pickle文件中加载x、y和电势数据
        with open('./output/{}/x_500.0.pkl'.format(simname), 'rb') as file:
            x = pickle.load(file)
        with open('./output/{}/y_500.0.pkl'.format(simname), 'rb') as file:
            y = pickle.load(file)
        with open('./output/{}/potential_500.0.pkl'.format(simname), 'rb') as file:
            potential = pickle.load(file)

        # 定义插值网格
        nPoints = 1000
        x_min, x_max = np.min(x), np.max(x)
        y_min, y_max = np.min(y), np.max(y)

        # 进行插值
        rbf = Rbf(x, y, potential, function='cubic')

        # 获取插值结果
        xi = np.linspace(x_min, x_max, nPoints)
        yi = np.linspace(y_min, y_max, nPoints)
        xi, yi = np.meshgrid(xi, yi)
        zi = rbf(xi, yi)

        # 创建TH2F对象，用于存储插值结果
        hInterpolated = ROOT.TH2F('hInterpolated', 'Interpolated Potential', nPoints, x_min, x_max, nPoints, y_min, y_max)

        # 将插值结果填充到TH2F对象中
        for i in range(nPoints):
            for j in range(nPoints):
                hInterpolated.SetBinContent(i+1, j+1, zi[i, j])

        # 保存插值结果为ROOT对象
        output_file = ROOT.TFile('./output/{}/Interpolated_Potential_2D.root'.format(simname), 'recreate')
        hInterpolated.Write()
        output_file.Close()

        # 计算梯度
        dx = np.gradient(zi, xi[0,0], axis=0)
        dy = np.gradient(zi, yi[0,0], axis=1)

        # 计算总场强
        total_field = np.sqrt(dx**2 + dy**2)

        # 创建TH2F对象，用于存储总场强
        hTotalField = ROOT.TH2F('hTotalField', 'Total Field', nPoints, x_min, x_max, nPoints, y_min, y_max)

        # 将总场强填充到TH2F对象中
        for i in range(nPoints):
            for j in range(nPoints):
                hTotalField.SetBinContent(i+1, j+1, total_field[i, j])

        # 保存总场强为ROOT对象
        output_file = ROOT.TFile('./output/{}/Total_Field_2D.root'.format(simname), 'recreate')
        hTotalField.Write()
        output_file.Close()
            
if __name__ == "__main__":
    main(simname)               