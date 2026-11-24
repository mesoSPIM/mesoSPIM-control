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

**Load mesoSPIM config (.py)** reads a mesoSPIM-control config and checks its timing. For a user config that
uses ``include()``, select it together with its hardware file (Ctrl+click). The file is parsed, not run. It reads the
camera (sensor size, pixel size, binning), the start zoom (magnification from ``pixelsize``), exposure, line interval,
sweeptime, camera delay and one arm's ETL timing, galvo and laser settings (pick left or right). For a Photometrics
camera the line interval comes from ``scan_line_delay`` (10.26 µs × (n+1)), and a ``camera_line_interval`` that
disagrees is flagged. Optics (beam length, waist) are not in a config and stay as set; ETL voltages are refitted,
because the model's ETL calibration is relative.

**Optimize for** sets the goal of **Optimize all**:

* *Balanced*: slit = light-sheet length, exposure as set.
* *Z resolution*: a narrower slit (default 0.5 × L\ :sub:`ls`), exposure as set; slower.
* *Speed*: the shortest exposure that still gives the minimum SNR, and a wider slit (default 2 × L\ :sub:`ls`).
* *SNR*: the exposure that gives the target SNR, slit = L\ :sub:`ls`.

SNR is for a bright cell lit by the ideal sheet, from the photon rate (e⁻ per ms of exposure) and the read noise in
**Optimization targets**; measure the rate as (bright cell − background) / exposure time on your sample.
Iris 15 line intervals are rounded to 10.26 µs steps.

Values that differ from what was last loaded (page defaults, a scenario or a config) are marked with ●, bold text and
a border; hovering a field shows the old value. The box above the panel offers **Revert** and lists the changed
timing values as config lines (``startup`` keys) to copy.

**Optimize all** proposes a line interval, sweeptime, camera/laser delays, galvo frequency and ETL amplitude/offset
for the current sensor and light-sheet length. These are starting points: the ETL and galvo calibration values
(µm per volt, ETL response time) are model inputs and must be matched to the instrument before the suggested
voltages are used. Validate any new timing on the microscope.

The file is self-contained; it can also be opened directly from ``docs/source/_static/aslm_simulator.html``,
or from mesoSPIM-control via **Utils → ASLM scan simulator**.
