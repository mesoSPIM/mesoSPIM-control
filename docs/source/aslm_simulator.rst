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
* the dose stripes along y (galvo axis): the in-focus dose per row of the centre sensor line, and the galvo passes
  during its exposure that cause it,
* a simulated camera frame of a phantom with cell bodies, filaments and autofluorescence,
* pass/warn checks for the ASLM timing rules (slit width vs. light-sheet length, ETL settling before the first line (≥ 3τ, τ = ETL response time), readout vs. ETL ramp,
  integer galvo half-periods per exposure, laser coverage).

Light-sheet thickness is given as FWHM throughout; w\ :sub:`0` (1/e² radius) and the 1/e² diameter are shown
as auxiliary values. The simulator is in beta. The default beam is a measured Benchtop beam: 561 nm, length
L\ :sub:`beam` = 220 µm, waist FWHM 6.0 µm and illumination NA 0.07 (n = 1.56), measured from the fluorescence of the
bulk medium excited by a static beam. The illumination NA is for information only; the model uses L\ :sub:`beam` and
the waist FWHM, and compares the waist with the Gaussian limit for that NA. The **Scenario** list holds timing presets from Benchtop and V5/V6 setups, two
hand-tuned Benchtop configs, and an NA 0.15 example (1.42 µm FWHM waist, L\ :sub:`beam` = 25 µm) that shows how much
the line interval has to grow, and the frame rate drop, when the slit is matched to a 4× shorter sheet.

To measure the waist and the beam length on your instrument, use **Utils → Analyse Beam Profile** in
mesoSPIM-control on a snap of a static beam (see the :doc:`User Guide <user_guide>`).

Plots: hover over a plot to read its values; drag a box to zoom (a flat horizontal drag zooms only the time or x
axis), double-click to reset. The three waveform plots zoom together in time. Legends sit above the plots.

**Dose stripes.** Each galvo pass gives every row it crosses the same dose, so a row's dose is the number of passes
that cross it during the line's exposure. A whole galvo period crosses every row twice, wherever it starts. An odd
number of half-periods leaves one half-period that starts wherever the galvo is when the line starts, so rows get
n−1, n or n+1 passes (±1/n): 0, 1 or 2 passes (coefficient of variation ~66%) at one half-period, ±33% at three. The rolling shutter
starts each line at a different galvo phase, so the stripes run diagonally. An even number of half-periods gives a
flat dose. Rows the galvo sweep does not reach get no light at all; the sweep length depends on the galvo
calibration (µm per volt), which is a model value, not part of a config. The plot shows the galvo position against
time in the centre line's exposure (left) and the dose per row (right), both with y vertical. The check reports the coefficient of variation (standard deviation / mean) of the dose over all lines (central 90% of rows, each line relative to its own
mean).

**Load mesoSPIM config (.py)** reads a mesoSPIM-control config and checks its timing. For a user config that
uses ``include()``, select it together with its hardware file (Ctrl+click). The file is parsed, not run. It reads the
camera (sensor size, pixel size, binning), the start zoom (magnification from ``pixelsize``), exposure, line interval,
sweeptime, camera delay and one arm's ETL timing, galvo and laser settings (pick left or right). For a Photometrics
camera the line interval comes from ``scan_line_delay`` (10.26 µs × (n+1)), and a ``camera_line_interval`` that
disagrees is flagged. Optics (beam length, waist) are not in a config and stay as set; ETL voltages are refitted,
because the model's ETL calibration is relative.

**Optimize for** sets the goal of **Optimize all**:

* *Balanced*: slit = light-sheet length, exposure as set.
* *Z resolution*: a narrower slit (default 0.5 × L\ :sub:`beam`), exposure as set; slower.
* *Speed*: the shortest exposure that still gives the minimum SNR, and a wider slit (default 2 × L\ :sub:`beam`).
* *SNR*: the exposure that gives the target SNR, slit = L\ :sub:`beam`.

For every goal, **Optimize all** sets ``camera_line_interval`` so the slit has the goal's width at the goal's
exposure (slit lines = slit width × M / pixel size, line interval = exposure / slit lines), within the sensor's
line-time limits and, for the Iris 15, rounded to 10.26 µs steps. The note under the goal list shows the line
interval it will set.

SNR is for a bright cell lit by the ideal sheet, from the photon rate per pixel (e⁻ per ms of exposure) and the read
noise in **Optimization targets**; measure the rate as (bright cell − background) / exposure time on your sample, and
enter the magnification it was measured at. At fixed laser power the rate per pixel is the sample area a pixel sees,
(dx/M)², times the excitation per area, which is the laser power spread over the galvo sweep. The galvo amplitude
follows the zoom (as with ``scale_galvo_amp_with_zoom``), so the sweep is ∝ 1/M and the rate per pixel ∝ 1/M:
2.5× higher at 2× than at 5×. Changes of detection NA between objectives are not included.
Iris 15 line intervals are rounded to 10.26 µs steps. Choosing a magnification scales ``galvo_l_amplitude`` with it.

**Re-fit amplitude/offset on every change** (ETL group, on by default) fits ``etl_l_amplitude`` and
``etl_l_offset`` to the slit after any other parameter is edited, so the waist keeps following the rolling shutter.
Nothing else is changed. Loading a scenario or config keeps its ETL values until something is changed. Typing an ETL
amplitude or offset turns the option off.

Values that differ from what was last loaded (page defaults, a scenario or a config) are marked with ●, bold text and
a border; hovering a field shows the old value. The box above the panel offers **Revert** and lists the changed
timing values as config lines (``startup`` keys) to copy.

**Optimize all** proposes a line interval, sweeptime, camera/laser delays, galvo frequency and ETL amplitude/offset
for the current sensor and light-sheet length. These are starting points: the ETL and galvo calibration values
(µm per volt, ETL response time) are model inputs and must be matched to the instrument before the suggested
voltages are used. Validate any new timing on the microscope.

The file is self-contained; it can also be opened directly from ``docs/source/_static/aslm_simulator.html``,
or from mesoSPIM-control via **Utils → ASLM scan simulator**.
