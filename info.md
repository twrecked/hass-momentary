### Momentary Switch Component for Home Assistant
A simple switch component that once turned on will turn itself off (or turn off and revert to on).

### What's New in v0.8
- **Visual Momentary Device Editor**: Interactive web-based card builder hosted on Google App Engine ([https://momentary-dot-twrecked-tools.nn.r.appspot.com](https://momentary-dot-twrecked-tools.nn.r.appspot.com)) or locally.
- **One-Click Sync**: Direct integration options flow allowing visual edits and automatic authenticated webhook sync to disk.
- **Async & Lifecycle Hardening**: Non-blocking atomic file I/O via Home Assistant's executor pool, removal of undeclared dependencies, and robust timer lifecycle management.
- **Resilient State Persistence**: Timezone-safe state restoration across Home Assistant reboots.

## Features
* Run as momentary on or off (normally off or normally on).
* User configurable on/off duration.
* Allow switch to be turned off/on early to cancel timer.
* Standalone switches or multi-switch devices.
* Visual Device Editor with preset templates and live YAML preview.

## Documentation
See [here](https://github.com/twrecked/hass-momentary/blob/master/README.md) for full documentation.
