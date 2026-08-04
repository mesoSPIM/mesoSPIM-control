# mesoSPIM-control Roadmap

*Last updated: July 2026*

`mesoSPIM-control` is the acquisition software for the mesoSPIM family of open-source
light-sheet microscopes, running on 38+ platforms across three hardware generations.
The software is mature and stable. This document describes the directions we consider
most important for the next few years.

It is a statement of intent, not a release schedule. Priorities shift as hardware,
users and contributors change. If you want to work on something here — or think we
have the priorities wrong — open an issue or raise it on the
[image.sc forum](https://forum.image.sc/tag/mesospim).

---

## Extensibility through plugins

The plugin system is where most new capability should come from. Image processors and
image writers can already be added without touching core acquisition code, and this is
currently the most active area of development, driven largely by the Center for Biologic
Imaging in Pittsburgh.

Our aim is for the plugin API to become the default contribution path: someone with a
processing method, a file format, or a piece of hardware should be able to add it
without needing to understand the acquisition loop. That means a stable API, a
documented template, and worked examples — and a willingness to move functionality out
of the core when a plugin is the better home for it.

## Acquisition performance

Acquisition speed is currently bounded by our own waveform and triggering model rather
than by the cameras and stages we drive. Waveforms are regenerated per sweep, which
imposes a software round trip on every frame.

Moving toward hardware-timed, continuously regenerated waveforms would remove that
round trip and benefit every existing setup without any hardware change. Work in this
direction is underway. Alongside it, we want timing to be measurable rather than
anecdotal, so that speed claims can be verified per setup.

## Bridging acquisition and interpretation

Multi-terabyte datasets currently leave the microscope raw and are processed elsewhere,
often days later. We would like the common workflows — denoising, stitching,
segmentation, atlas registration — to run during or immediately after acquisition, so
that what comes off the microscope is closer to being interpretable.

We integrate rather than reimplement. Downstream ecosystems around BigStitcher,
multiview-stitcher, BrainGlobe, Cellpose, napari and neuroglancer are better than
anything we would write ourselves; our job is to hand data to them cleanly, and to
reduce data volume where it can be done without losing scientific content.

## Lowering the expertise barrier

Operating a light-sheet microscope well requires judgement that novice and occasional
users do not have — alignment, ETL settings, magnification and step size, illumination
choices. This is the most common reason good instruments produce mediocre data.

We are interested in exposing microscope state and hardware limits through a safe,
documented external interface, and in what becomes possible once software agents can
use it: guided setup, troubleshooting, and parameter selection in plain language. Any
such interface has to enforce hardware limits independently of whatever is calling it,
and log what it did. We would rather this became a shared convention across acquisition
software than another one-off API.

---

## Out of scope

- **Data repositories or hosting.** Data stays with the institution that acquired it.
- **Arbitrary microscope geometries.** mesoSPIM-control is purpose-built for the
  mesoSPIM family. Micro-Manager, ImSwitch and Python-Microscope serve the general case
  well, and interoperating with them beats duplicating them.
