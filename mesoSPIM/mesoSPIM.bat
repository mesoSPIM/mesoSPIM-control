echo off
echo Setting up your Mamba enviroment:
echo Change the Mamba path "...\activate.bat" to your own
echo To print your Mamba path, run this in Miniforge prompt:
echo $ where mamba
echo off
"%windir%\System32\cmd.exe" /k ""C:\ProgramData\miniforge3\Scripts\activate.bat" "C:\Users\Public\mamba\envs\mesoSPIM-py312" && python "mesoSPIM_Control.py""
pause