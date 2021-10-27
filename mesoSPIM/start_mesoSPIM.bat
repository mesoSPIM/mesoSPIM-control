rem Change the Anaconda path "C:\Users\Nikita\anaconda3\Scripts\" and environments path "C:\Users\Nikita\anaconda3\envs" to your own
rem To know your Anaconda path, run in Anaconda prompt:
rem $ where conda
rem
rem In a multi-user setting, you may want to create the py36 environment in a public folder accessible for all users:
rem $ conda create -p C:/full/public/path/to/envs/py36 python=3.6
rem Make sure all users have right to execute python in the py36 environment (you may need admin rights for that).
echo off
"%windir%\System32\cmd.exe" /k ""C:\ProgramData\Anaconda3\Scripts\activate.bat" "C:\Users\spim-user\.conda\envs\py37" && python "mesoSPIM_Control.py""
pause