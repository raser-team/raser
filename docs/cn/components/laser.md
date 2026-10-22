# Laser 组件

Laser 组件定义 TCT 所用的光注入。它包含吸收方式、入射方向、波长、折射率、吸收参数、脉冲能量与时序、焦点、空间宽度和采样分辨率。

SPA 使用线性吸收系数。TPA 使用双光子吸收系数与瑞利长度描述。[Interaction](../core/interaction.md) 产生载流子群时，焦点以 Device 坐标表示。

[TCT 应用](../apps/tct.md)为扫描加入注入位置，并随每项结果记录所选 Laser 定义。
