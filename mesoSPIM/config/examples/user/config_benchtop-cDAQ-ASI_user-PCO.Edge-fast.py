"""
mesoSPIM user configuration: pco.edge 4.2 bi on the cDAQ-ASI benchtop, 2x faster waveform
(6.6 fps instead of 3.3 fps).

To use it, copy this file to config/ and the hardware file
config/examples/hardware/config_benchtop-cDAQ-ASI-PCOedge42bi_hw.py to config/hardware/
(the include() path below is relative to config/). Only the scan timing is overridden here.

Everything is halved: line time 0.118 -> 0.059 ms, so the 2048-line readout takes half as long, and the
sweep 301 -> 150.6 ms. The slit stays 169 lines (= 220 um = L_beam at 5x, same axial resolution), so the
exposure per line halves too: 169 x 0.059 ms = 9.97 ms. Each pixel gets half the light per frame: raise the
laser power by up to 2x for the same signal, or accept the lower SNR.

The camera line time moves in steps of 1/46 MHz = 21.74 ns (measured: 13 us min); 59.000 us = 2714 steps,
so it is set exactly. Timing checked with the ASLM simulator (5x, L_beam 220 um): all 11 checks pass for the
left arm. The simulator models only a rising ETL sweep; the right arm sweeps on the falling ramp over the same
3-96 % window, so its timing is the mirror image of the left one.

Known issue (benchtop at HIFO, 2026-11-27): a ~56.5 Hz mechanical vibration, most likely the camera fan,
showed as a "wave" running through each frame (0.2 px rms image shift). The 9.97 ms exposure averages it
much less than the 20 ms exposure of the standard config (residual 0.2 px vs 0.03 px), so it is visible
only with this config. Fix it at the source (fan, mounting); a longer exposure is not a good workaround.
"""
config_format = 2

include('hardware/config_benchtop-cDAQ-ASI-PCOedge42bi_hw.py')

startup.update({
    'state': 'init',
    'folder': 'F:/Test/',
    'snap_folder': 'F:/Test/',
    'file_prefix': '',
    'file_suffix': '000001',

    'sweeptime': 0.1506,        # 3765 samples at 25 kS/s; readout 9.97 + 2047 x 0.059 = 130.7 ms
    'camera_exposure_time': 0.00997,    # s; 169 x 0.059 ms = 9.971 ms
    'camera_line_interval': 0.000059,   # s; slit 169 lines
    # Camera, laser and stage-trigger percentages are unchanged from the hardware file (7 %, 7-95 %, 95 %).
    # The ETL ramp starts earlier, at 3 % instead of 5 %: halving the sweep would otherwise put the first line
    # only 3 ms into the ramp, and the ETL needs 3 tau = 6 ms (tau = 2 ms) to follow it.
    # Sweep ramp 3-96 % = 4.5-144.6 ms; first line at 10.5 ms (6.0 ms into it); last line done at 141.3 ms.
    # ETL flyback: left 6.0 ms (falling 96-100 %), right 4.5 ms (rising 0-3 %).
    'etl_l_delay_%': 3.0,
    'etl_l_ramp_rising_%': 93.0,
    'etl_l_ramp_falling_%': 4.0,
    'etl_r_delay_%': 0.0,
    'etl_r_ramp_rising_%': 3.0,
    'etl_r_ramp_falling_%': 93.0,
    # Galvo kept at ~100 Hz (higher frequencies overheat it): exactly 2 half-periods per 9.971 ms exposure.
    # At exactly 100.0 Hz it is 1.994: an ~18 um band gets one pass instead of two (dose-stripe CV 3.7 %).
    'galvo_l_frequency': 100.3,
    'galvo_r_frequency': 100.3,
    'average_frame_rate': 4.4,   # stacks ran at 4.2 fps (per-frame DAQ start/stop overhead), 1/sweeptime = 6.64 fps
})
