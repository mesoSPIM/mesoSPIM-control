## Release September 2025 [1.11.1]
:rocket: Overhaul of internal bootlnecks that hampered performance on some systems and caused GUI freezing / high CPU loads.
### Bugfixes :bug: 
- fixed excessive communication between threads causing high CPU load on some systems.
- moved `serial_worker` into `core` thread to avoid conflicts of relative motion operations with GUI thread.
- added CPU core identifiers for different operations in `debug` mode or logging, to pinpoint performance issues.
- fixed autofocus (AF) function in the GUI.
- returned `'camera_display_live_subsampling': 2, `,  `'camera_display_acquisition_subsampling': 2,` and `'camera_display_temporal_subsampling': 2,` into the config file, to reduce camera display load on older computers.
- fixed light-sheet markers and box ROI markers in the Camera window, which were not displayed correctly after zoom change.