echo off
echo Setting up your Mamba enviroment:
echo Change the Mamba path "...\activate.bat" to your own
echo To print your Mamba path, run this in Miniforge prompt:
echo $ where mamba
echo off
"%windir%\System32\cmd.exe" /k ""C:\Users\lab\miniconda3\condabin\activate.bat" "C:\Users\lab\miniconda3\envs\mesoSPIM_dev" && python "mesoSPIM_Control.py""
pause