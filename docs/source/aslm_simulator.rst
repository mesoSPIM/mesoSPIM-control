ASLM Scan Simulator
===================

`Open the ASLM scan simulator <_static/aslm_simulator.html>`_ (runs in the browser, no installation).

The simulator models axially swept light-sheet microscopy (ASLM) with one illumination arm and one galvo,
using the same waveform shapes and parameter names as mesoSPIM-control
(``etl_l_delay_%``, ``etl_l_ramp_rising_%``, ``galvo_l_frequency``, ``camera_line_interval``, ...).
Change sensor size, pixel size, exposure, line interval, sweeptime, delays and galvo settings, and see:

* which part of the beam the virtual slit takes in (slit vs. light-sheet length, for the centre sensor line),
* how the z resolution (effective sheet FWHM) changes with exposure time, line interval or effective frame rate,
* the rolling shutter and the beam waist in a time vs. sensor-line plot (collapsed timing detail),
* the waveforms as sent to the DAQ,
* the exposure-integrated light-sheet profile across the field of view and its effective thickness,
* a simulated camera frame of a phantom with cell bodies, filaments and autofluorescence,
* pass/warn checks for the ASLM timing rules (slit width vs. light-sheet length, readout vs. ETL ramp,
  integer galvo half-periods per exposure, laser coverage).

Light-sheet thickness is given as FWHM throughout; w\ :sub:`0` (1/e² radius) and the 1/e² diameter are shown
as auxiliary values. The simulator is in beta. The default beam is a measured Benchtop beam: 561 nm, length
L\ :sub:`ls` = 220 µm, waist FWHM 6.0 µm and illumination NA 0.07 (n = 1.56), measured from the fluorescence of the
bulk medium excited by a static beam. The illumination NA is for information only; the model uses L\ :sub:`ls` and
the waist FWHM, and compares the waist with the Gaussian limit for that NA. The **Scenario** list holds timing presets from Benchtop and V5/V6 setups, two
hand-tuned Benchtop configs, and an NA 0.15 example (1.42 µm FWHM waist, L\ :sub:`ls` = 25 µm) that shows how much
the line interval has to grow, and the frame rate drop, when the slit is matched to a 4× shorter sheet.

To measure the waist and the beam length on your instrument, use **Utils → Analyse Beam Profile** in
mesoSPIM-control on a snap of a static beam (see the :doc:`User Guide <user_guide>`).

**Optimize all** proposes a line interval, sweeptime, camera/laser delays, galvo frequency and ETL amplitude/offset
for the current sensor and light-sheet length. These are starting points: the ETL and galvo calibration values
(µm per volt, ETL response time) are model inputs and must be matched to the instrument before the suggested
voltages are used. Validate any new timing on the microscope.

The file is self-contained; it can also be opened directly from ``docs/source/_static/aslm_simulator.html``,
or from mesoSPIM-control via **Utils → ASLM scan simulator**.
