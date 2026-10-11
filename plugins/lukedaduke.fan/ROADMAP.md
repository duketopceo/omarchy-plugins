# Roadmap

## Current status

Ready to install. The manifest, README, and LICENSE all pass `omarchy plugin validate`. The marketplace registry does not list it yet.

## Launch checklist

- [x] Add a clean `preview.png` (bar widget and panel)
- [ ] Submit to https://plugins.omarchy.org/publish.html
- [x] Set GitHub repo topics
- [ ] Set GitHub social preview
- [x] Add a one-line tagline to the GitHub repo description
- [ ] Write a short release note / social post

## Future work

- [ ] Deeper RAM view (pressure/PSI, per-process RSS detail)
- [ ] Better process-kill UX (filter/search, GPU-client highlighting)
- [ ] GPU utilization % once asahi fdinfo counters land in the kernel
- [ ] Configurable temperature thresholds in the bar widget
- [ ] GPU-specific fan curves
- [ ] Hibernation / AC-power-aware auto curve
- [ ] Optional process list sort by CPU or memory
- [ ] Support for more `hwmon` laptops without per-device hardcoding
