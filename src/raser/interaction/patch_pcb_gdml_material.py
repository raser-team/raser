from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
G4EXPERIMENT_DIR = REPO_ROOT / "setting" / "g4experiment"

RAW_GDML = G4EXPERIMENT_DIR / "pcb_readout_raw.gdml"
FINAL_GDML = G4EXPERIMENT_DIR / "pcb_readout.gdml"

BOARD_VOLUME = "LV_Board_0jgr"
BOARD_MATERIAL = "FR4"

FR4_MATERIAL_BLOCK = """<materials>
  <element name="H" formula="H" Z="1">
    <atom value="1.00794"/>
  </element>
  <element name="C" formula="C" Z="6">
    <atom value="12.011"/>
  </element>
  <element name="O" formula="O" Z="8">
    <atom value="15.999"/>
  </element>
  <element name="Si" formula="Si" Z="14">
    <atom value="28.0855"/>
  </element>

  <material name="FR4" state="solid">
    <D value="1.86" unit="g/cm3"/>
    <fraction n="0.0684428" ref="H"/>
    <fraction n="0.2780420" ref="C"/>
    <fraction n="0.4056330" ref="O"/>
    <fraction n="0.2478822" ref="Si"/>
  </material>
</materials>
"""

def fail(msg: str, code: int = 1) -> None:
    print(f"[ERROR] {msg}")
    sys.exit(code)

def main() -> None:
    if not RAW_GDML.exists():
        fail(f"找不到原始 GDML 文件: {RAW_GDML}")

    text = RAW_GDML.read_text(encoding="utf-8")

    if "<materials/>" in text:
        text = text.replace("<materials/>", FR4_MATERIAL_BLOCK, 1)
    else:
        if '<material name="FR4"' not in text:
            pattern_materials = re.compile(r"<materials>(.*?)</materials>", re.DOTALL)
            m = pattern_materials.search(text)
            if not m:
                fail("找不到 <materials> 块，也找不到 <materials/>，无法注入 FR4。")
            inner = m.group(1)
            fr4_only = """
  <element name="H" formula="H" Z="1">
    <atom value="1.00794"/>
  </element>
  <element name="C" formula="C" Z="6">
    <atom value="12.011"/>
  </element>
  <element name="O" formula="O" Z="8">
    <atom value="15.999"/>
  </element>
  <element name="Si" formula="Si" Z="14">
    <atom value="28.0855"/>
  </element>

  <material name="FR4" state="solid">
    <D value="1.86" unit="g/cm3"/>
    <fraction n="0.0684428" ref="H"/>
    <fraction n="0.2780420" ref="C"/>
    <fraction n="0.4056330" ref="O"/>
    <fraction n="0.2478822" ref="Si"/>
  </material>
"""
            text = text[:m.start()] + f"<materials>{inner}{fr4_only}</materials>" + text[m.end():]

    volume_pattern = re.compile(
        rf'(<volume name="{re.escape(BOARD_VOLUME)}">\s*)(<materialref ref="[^"]+"/>)',
        re.MULTILINE
    )
    text, n = volume_pattern.subn(
        rf'\1<materialref ref="{BOARD_MATERIAL}"/>',
        text,
        count=1
    )

    if n != 1:
        fail(f"没有找到 volume `{BOARD_VOLUME}` 的 materialref，补丁未应用。")

    FINAL_GDML.write_text(text, encoding="utf-8")

    print("[OK] 已生成最终 GDML：", FINAL_GDML)
    print("[OK] 原始 GDML 保留：", RAW_GDML)
    print(f"[OK] 板子 volume `{BOARD_VOLUME}` 材料已改为 `{BOARD_MATERIAL}`")

if __name__ == "__main__":
    main()
