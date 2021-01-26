@echo off

if not exist test_dxf.pretty ( md test_dxf.pretty )

for %%f in (*.dxf) do py ../dxf2kicad_mod.py %%f  test_dxf.pretty\%%~nf.kicad_mod %1

 py ../dxf2kicad_mod.py Inverted_F_Antenna.dxf  test_dxf.pretty\Inverted_F_Antenna.kicad_mod %1 -u mil


