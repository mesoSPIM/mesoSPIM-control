'''
Log the hardware of the computer running the microscope (Windows only).

Acquisition speed is usually limited by the PC, not by the microscope, so the log
file has to say what the PC was: writing to a SATA HDD and writing to an NVMe SSD
are different experiments.
'''
import json
import logging
import subprocess

import psutil

logger = logging.getLogger(__name__)

GB = 1024 ** 3

# One PowerShell round trip for everything WMI knows and psutil does not.
# [string] forces the MediaType/BusType enums to 'SSD'/'NVMe' instead of 4/17.
_QUERY = '''ConvertTo-Json -Compress -Depth 3 @{
 cpu=@(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed)
 gpu=@(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,AdapterRAM)
 disk=@(Get-PhysicalDisk | Select-Object FriendlyName,@{n='MediaType';e={[string]$_.MediaType}},@{n='BusType';e={[string]$_.BusType}},Size)
}'''


def log_system_info():
    '''Write a CPU/GPU/RAM/disk summary at INFO level, the details at DEBUG.'''
    ram = psutil.virtual_memory()
    logger.info(f'RAM: {ram.total / GB:.0f} GB total, {ram.available / GB:.0f} GB available')
    logger.debug(f'RAM: {ram}')
    logger.debug(f'Disk partitions: {psutil.disk_partitions()}')

    try:
        out = subprocess.run(['powershell', '-NoProfile', '-Command', _QUERY],
                             capture_output=True, text=True, timeout=30, check=True).stdout
        info = json.loads(out)
    except Exception as e:
        # Never let hardware reporting stop the microscope from starting.
        logger.warning(f'Could not query system info: {e!r}')
        return

    for cpu in info['cpu']:
        logger.info(f"CPU: {cpu['Name'].strip()}, {cpu['NumberOfCores']} cores / "
                    f"{cpu['NumberOfLogicalProcessors']} threads, {cpu['MaxClockSpeed']} MHz")
    for gpu in info['gpu']:
        logger.info(f"GPU: {gpu['Name']}")
    for disk in info['disk']:
        logger.info(f"Disk: {disk['FriendlyName']} ({disk['MediaType']}, {disk['BusType']}, "
                    f"{(disk['Size'] or 0) / GB:.0f} GB)")
    logger.debug(f'System info (raw): {out.strip()}')
