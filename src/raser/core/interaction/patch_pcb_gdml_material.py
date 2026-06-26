import os
import re
import sys
import json
from pathlib import Path

from raser.supports.paths import app_file_path
from raser.supports.paths import project_path

def patch_gdml():
    raw_path = project_path('g4experiment', 'pcb_readout_raw.gdml')
    out_path = Path(raw_path).with_name('pcb_readout.gdml')
    json_path = app_file_path('signal', 'pcb_readout_gdml.json')

    if not os.path.exists(raw_path):
        print(f"[Error] 找不到原始文件: {raw_path}", file=sys.stderr)
        return

    print(f"[Info] 正在读取 GDML 数据: {raw_path}")
    with open(raw_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # ====================================================
    # 步骤 1：排除游离点，计算核心几何中心并加上手动微调参数
    # ====================================================
    xs, ys, zs = [], [], []
    pattern = r'<position\s+name="Mesh2Tess_\d+"[^>]*x="([^"]+)"[^>]*y="([^"]+)"[^>]*z="([^"]+)"'
    for match in re.finditer(pattern, content):
        xs.append(float(match.group(1)))
        ys.append(float(match.group(2)))
        zs.append(float(match.group(3)))

    if xs and ys and zs:
        xs.sort()
        ys.sort()
        zs.sort()
        
        trim = max(1, int(len(xs) * 0.10))
        valid_xs = xs[trim:-trim]
        valid_ys = ys[trim:-trim]
        valid_zs = zs[trim:-trim]
        
        center_x = (valid_xs[-1] + valid_xs[0]) / 2.0
        center_y = (valid_ys[-1] + valid_ys[0]) / 2.0
        center_z = (valid_zs[-1] + valid_zs[0]) / 2.0
       
        manual_offset_x = 0.0
        manual_offset_y = 0.0
        manual_offset_z = 0.0 
        
        off_x = -center_x + manual_offset_x
        off_y = -center_y + manual_offset_y
        off_z = -center_z + manual_offset_z
        
        print(f"[Info] 计算实际几何中心坐标: X={center_x:.3f}, Y={center_y:.3f}, Z={center_z:.3f} mm")
        print(f"[Info] 应用位置校准平移参数 (含手动微调): X={off_x:.3f}, Y={off_y:.3f}, Z={off_z:.3f} mm")

        new_position = ( f'<position name="center" x="{off_x}" y="{off_y}" z="{off_z}" unit="mm"/>'
        )
        if re.search(r'<position\s+name="center"[^>]*/>', content):
            content = re.sub(r'<position\s+name="center"[^>]*/>', new_position, content)
        else:
            if "</define>" in content:
                content = content.replace("</define>", f"  {new_position}\n</define>")
    else:
        print("[Warning] 未提取到有效顶点数据，位置校准已跳过。")

    # ====================================================
    # 步骤 2：移除占位符 (dummy) 引用
    # ====================================================
    print("[Info] 正在清理 dummy 引用...")
    content = re.sub(r'<physvol[^>]*>\s*<volumeref\s+ref=["\']dummy["\']\s*/>.*?</physvol>', '', content, flags=re.DOTALL | re.IGNORECASE,)

    # ====================================================
    # 步骤 3：修复同名体积嵌套及定义顺序
    # ====================================================
    print("[Info] 正在重构结构定义顺序...")
    struct_match = re.search(r'<structure>(.*?)</structure>', content, flags=re.DOTALL)
    if struct_match:
        struct_content = struct_match.group(1)
        volumes = re.findall(r'<volume\s+name="[^"]+">.*?</volume>', struct_content, flags=re.DOTALL)
        
        inner_volumes = []
        wrapper_volume = ""
        
        for vol in volumes:
            if 'ref="WorldBox"' in vol:
                wrapper_volume = re.sub(r'<volume\s+name="[^"]+">', '<volume name="World_Wrapper">', vol, count=1,)
            else:
                inner_volumes.append(vol)
                
        new_struct_content = "\n".join(inner_volumes) + "\n\n\n" + wrapper_volume
        content = content.replace(struct_content, "\n" + new_struct_content + "\n")

    # ====================================================
    # 步骤 4：更新环境属性与世界边界
    # ====================================================
    print("[Info] 正在更新环境属性与世界边界...")
    content = re.sub(r'<world\s+ref=["\'][^"\']+["\']\s*/>', '<world ref="World_Wrapper"/>', content)
    content = re.sub(r'<materialref\s+ref=["\']Material["\']\s*/>', '<materialref ref="FR4"/>', content,)
    content = re.sub(
        r'<box\s+name=["\']WorldBox["\'][^>]*/>',
        '<box name="WorldBox" x="2000000" y="2000000" z="2000000" lunit="um"/>',
        content,
    )

    # ====================================================
    # 步骤 5：处理 JSON 配置防偏移干扰
    # ====================================================
    if os.path.exists(json_path):
        print(f"[Info] 正在检查和修正 JSON 配置文件: {json_path}")
        try:
            with open(json_path, 'r', encoding='utf-8') as jf:
                config = json.load(jf)
            
            modified = False
            if 'gdml' in config:
                if config['gdml'].get('position_um') != [0, 0, 0]:
                    config['gdml']['position_um'] = [0, 0, 0]
                    modified = True
                if config['gdml'].get('auto_center') is not False:
                    config['gdml']['auto_center'] = False
                    modified = True
            
            if modified:
                with open(json_path, 'w', encoding='utf-8') as jf:
                    json.dump(config, jf, indent=4)
                print(f"[Info] 成功将 JSON 配置文件中的偏移坐标归零。")
            else:
                print(f"[Info] JSON 配置文件坐标正常，无需修改。")
        except Exception as e:
            print(f"[Warning] 修改 JSON 配置失败: {e}")

    # ====================================================
    # 保存结果
    # ====================================================
    print(f"[Info] 正在将处理结果写入文件: {out_path}")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("[Success] GDML 文件处理完成。")

if __name__ == '__main__':
    patch_gdml()
