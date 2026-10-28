# 🚀 Momentary v0.8.0-beta.1 — Visual Device Editor, Probatio Support & Beta Pre-Release

> ### 🧪 Beta Release & Community Testing Notice
> **Momentary v0.8 enters the Beta phase! This major release features a dedicated web-based Visual Device Editor, options flow webhook synchronization, native Home Assistant lifecycle hardening, Probatio validation engine compatibility, and non-blocking asynchronous state storage.**
>
> **This is an active beta release — features are stabilized and ready for broader community testing.**
>
> If you encounter any bugs, edge cases, state restoration anomalies, or configuration issues, please [open a GitHub issue](https://github.com/twrecked/hass-momentary/issues) with your configuration snippet and debug logs.

---

## 🌟 What's New in v0.8.0-beta.1

### 1. Compatibility with Modern Home Assistant (Probatio Validation Engine)
- **Probatio Support**: Home Assistant's modern validation engine (`probatio`) is fully supported in config and options flows, resolving strict static typing and schema validation in Home Assistant 2026.9+.
- **Backwards Compatibility**: Gracefully falls back to `voluptuous` on earlier releases, ensuring broad compatibility across Home Assistant versions.
- **Minimum Requirement**: Declared `"homeassistant": "2026.7.0"` in `hacs.json` to guarantee all modern entity models and helpers are present.

### 2. Interactive Web-Based Visual Momentary Device Editor
Configure your momentary switches with an intuitive card-based visual builder instead of editing raw YAML by hand:
- **Hosted Cloud Builder:** Live on Google App Engine at **[https://momentary-dot-twrecked-tools.nn.r.appspot.com](https://momentary-dot-twrecked-tools.nn.r.appspot.com)** (and accessible via the central hub at **[https://twrecked-tools.nn.r.appspot.com](https://twrecked-tools.nn.r.appspot.com)**).
- **One-Click Sync via Home Assistant:** In Home Assistant, navigate to **Settings -> Devices & Services -> Momentary** and click **Configure** on any group to launch the editor with your switches preloaded. Click **Save & Return**, and the editor automatically updates your file on disk and reloads the integration via an authenticated webhook.
- **Preset Switch Templates ("Quick Adds"):** One-click generation of common momentary hardware patterns:
  - *Standard Push Button* (Pulse ON for 1s, then revert to OFF)
  - *Garage Door Opener* (Pulse ON for 2s trigger)
  - *Staircase / Hallway Timer* (Hold ON for 60s with early cancel support)
  - *Normally-Closed Breaker Reset* (Normally ON, break contact/pulse OFF for 5s)
  - *Multi-Button Keypad* (Multiple momentary switches under a single device)
- **Duration Presets & Controls:** Instant preset buttons (`1s`, `2s`, `5s`, `10s`, `30s`, `60s`) alongside custom second inputs.
- **Collapsible Cards & Live YAML Preview:** Expand or collapse individual devices, toggle all cards, and preview formatted YAML side-by-side with immediate copy to clipboard.
- **Local & Offline Friendly:**
  - **Local LAN Mode:** Run the editor locally using `python main.py` in the `momentary-device-editor/` folder with zero data leaving your private network.
  - **Manual Copy-Paste Fallback:** No webhooks or network access required — edit visually, click **Copy** or **Download**, and paste into your `/config/momentary.yaml`.

---

### 3. Core Entity Architecture & Lifecycle Hardening
- **Synchronous Event Callback:** Corrected `_handle_timer_expired` to a synchronous `@callback` running directly on the event loop, using `self.async_write_ha_state()` to eliminate invalid async scheduling.
- **Re-trigger Timer Overwrite Fix:** Fixed a race condition where rapidly re-triggering a momentary switch during an active countdown overwrote the timer handle without cancelling the active callback, causing premature reversion. The active timer is now explicitly cancelled before rescheduling.
- **Entity Teardown & Timer Cleanup:** Implemented `async_will_remove_from_hass` to cleanly cancel any running timer callbacks when switches are deleted, disabled, or when the integration is reloaded.
- **Timezone-Safe State Restoration:** Stored `toggle_until` timestamps are now parsed safely with `dt_util.parse_datetime`, validated against `None`, and normalized to UTC, preventing `TypeError` comparison crashes and attribute exceptions across restarts mid-countdown.
- **Preserved Metadata on Reload:** Removed metadata deletion from `async_unload_entry`. Integration reloads and Home Assistant restarts now retain stored unique IDs, delegating metadata cleanup strictly to `async_remove_entry`.
- **Operating Modes:** Full support for both `mode: "on"` (normally off / pulse on) and `mode: "off"` (normally on / pulse off).

---

### 4. Non-Blocking Storage & Asynchronous Core
- **Atomic Executor-Backed File I/O:** Replaced synchronous/unmanaged file I/O with atomic file writes using `pathlib.Path` executed safely on Home Assistant's executor pool via `hass.async_add_executor_job`.
- **Zero Undeclared Dependencies:** Eliminated third-party `aiofiles` dependency in favor of standard library file operations and Home Assistant core async helpers.
- **Manifest Modernization:**
  - Configured `"iot_class": "local_push"` for instant, event-driven state transitions.
  - Added `"dependencies": ["webhook"]`.
  - Retained standard integration categorization (`hub`) for visibility in the **Integrations** dashboard.
- **HACS Integration:**
  - Added `"render_readme": true` to `hacs.json` so modern HACS displays full documentation directly in the HACS dashboard.
  - Specified `"homeassistant": "2026.7.0"` minimum requirement.
- **Strict Typing:**
  - Full Python 3.12+ type annotations (`from __future__ import annotations`, PEP 585 generics, and PEP 604 union types).

---

## 🛠️ Testing Checklist for Beta Testers

1. **Visual Device Editor Sync**: Open **Settings -> Devices & Services -> Momentary -> Configure**, click the editor link, edit or add a switch, and click **Save & Return**. Confirm the file updates on disk and the integration reloads cleanly.
2. **Timer Expiration**: Test switches configured with different toggle durations (`toggle_for: 1`, `5`, `60`) and verify they toggle state and revert back accurately.
3. **Early Cancellation**: For switches with `cancellable: true`, verify that manually toggling the switch during a countdown cancels the timer and returns it to idle immediately.
4. **Rapid Re-Triggering**: Toggle a switch multiple times in rapid succession to ensure the countdown resets cleanly without premature shutoff.
5. **State Restoration Across Restart**: Turn on a long-duration switch (e.g. 60s), restart Home Assistant, and verify the remaining timed state is properly restored or cleanly reset.
