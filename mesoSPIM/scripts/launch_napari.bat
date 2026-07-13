@echo off

:: ============================================================
:: CONFIGURATION — Edit these two lines to match your setup
:: ============================================================
set CONDA_PATH=C:\ProgramData\Anaconda3
set CONDA_ENV=napari-env
:: ============================================================

:: Initialize conda for use in batch scripts
call "%CONDA_PATH%\Scripts\activate.bat" "%CONDA_PATH%"

:: Activate the napari environment
call conda activate %CONDA_ENV%

:: Launch napari
napari

:: Keep window open if napari crashes (optional — remove if unwanted)
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Napari exited with an error. Press any key to close...
    pause >nul
)