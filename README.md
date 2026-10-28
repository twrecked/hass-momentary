# **Momentary Switches for Home Assistant**

_Momentary_ is a custom integration for [Home Assistant](https://www.home-assistant.io/) that provides momentary switches — switches that toggle to an active state and automatically revert back to their idle state after a configurable duration.

![icon](images/momentary-icon.png)

---

> ### 🚀 Momentary `v0.8.0-beta.1` Notice
>
> **Momentary v0.8 modernizes the integration with native Home Assistant entity models, an interactive web-based Visual Device Editor, options flow webhook synchronization, and non-blocking asynchronous state storage.**
>
> **This is an active beta release — community testing and feedback are welcome!**
>
> Full release details and highlights can be found in the [v0.8.0-beta.1 Release Notes](docs/RELEASE_NOTES_v0.8.0-beta.1.md).
>
> If you encounter issues, regressions, or unexpected behavior, please [open a GitHub issue](https://github.com/twrecked/hass-momentary/issues).

---

# Table Of Contents

- [Introduction](#introduction)
- [What's New in v0.8](#whats-new-in-v08)
- [Installation](#installation)
  - [HACS (Recommended)](#hacs-recommended)
  - [Manual Installation](#manual-installation)
- [Visual Device Editor](#visual-device-editor)
  - [One-Click Sync via Home Assistant](#1-one-click-sync-via-home-assistant-recommended)
  - [Manual Copy-Paste / Offline Fallback](#2-manual-copy-paste--offline-fallback)
  - [Running the Editor Locally on Your LAN](#3-running-the-editor-locally-on-your-lan)
- [Entity Configuration](#entity-configuration)
  - [Standalone Switches](#standalone-switches)
  - [Multi-Switch Devices](#multi-switch-devices)
  - [Configuration Options](#configuration-options)
  - [Name Prefixes](#name-prefixes)
- [Services](#services)
- [Turning on Debug](#turning-on-debug)

---

# Introduction

Momentary switches are ideal for simulating pushbuttons, garage door openers, gate triggers, timed staircase/hallway lighting, or reset relays that should only pulse for a designated duration before returning to their idle state.

All state transitions are driven locally in memory (`local_push`) and persist cleanly across Home Assistant restarts.

---

# What's New in v0.8

- **Visual Device Editor**: A web-based visual card builder hosted on Google App Engine ([https://momentary-dot-twrecked-tools.nn.r.appspot.com](https://momentary-dot-twrecked-tools.nn.r.appspot.com)) or run locally.
- **Webhook Sync**: Open the editor directly from the Home Assistant UI via **Configure** to edit switches visually and save them straight back into your configuration file.
- **Async & Lifecycle Hardening**: Fully asynchronous executor-backed atomic file writes, elimination of unapproved third-party dependencies (`aiofiles`), and strict timer lifecycle teardown.
- **Resilient State Persistence**: Timezone-safe state restoration that prevents crashes on missing attributes or Home Assistant restarts mid-countdown.

---

# Installation

## HACS (Recommended)

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)

Momentary is part of the default HACS store. Search for "Momentary" under Integrations and install it.

## Manual Installation

Copy the `custom_components/momentary` folder into your Home Assistant `/config/custom_components` directory and restart Home Assistant.

---

# Visual Device Editor

You can manage your momentary switches visually using the hosted editor:
👉 **[https://momentary-dot-twrecked-tools.nn.r.appspot.com](https://momentary-dot-twrecked-tools.nn.r.appspot.com)**

### 1. One-Click Sync via Home Assistant (Recommended)

1. In Home Assistant, go to **Settings -> Devices & Services -> Momentary**.
2. Click **Configure** on your group.
3. Click the link **Open Momentary Device Editor** to open the builder in a new tab.
4. Add, edit, or customize your switches with live YAML previews and templates.
5. Click **Save & Return** in the top bar. The editor securely delivers the updated YAML back to Home Assistant via an authenticated webhook and automatically reloads the integration.
6. Click **Submit** in Home Assistant to close the dialog.

### 2. Manual Copy-Paste / Offline Fallback

If you don't use webhooks or external access:
1. Open [https://momentary-dot-twrecked-tools.nn.r.appspot.com](https://momentary-dot-twrecked-tools.nn.r.appspot.com).
2. Click **Import YAML** and paste your `/config/momentary.yaml` content.
3. Edit your switches visually.
4. Click **Copy** (or **Download**) in the top right bar and paste the content into `/config/momentary.yaml`.
5. In Home Assistant, click the three dots on the Momentary integration card and select **Reload**.

### 3. Running the Editor Locally on Your LAN

You can also run the editor locally inside your private network:

```bash
cd momentary-device-editor
pip install -r requirements.txt
python main.py
```

The editor will listen on `http://localhost:8080`. In Home Assistant's **Configure** dialog, set **Editor URL** to your local address (`http://192.168.1.X:8080`).

---

# Entity Configuration

Momentary stores its devices in `/config/momentary.yaml`.

### Standalone Switches

```yaml
version: 1
switches:
  - name: Front Doorbell
    mode: "on"
    toggle_for: 1
    cancellable: false
  - name: Staircase Light
    mode: "on"
    toggle_for: 60
    cancellable: true
```

### Multi-Switch Devices

You can group switches together under an umbrella parent device:

```yaml
version: 1
switches:
  - Alarm Keypad:
      - name: Arm Away Pulse
        mode: "on"
        toggle_for: 2
      - name: Arm Stay Pulse
        mode: "on"
        toggle_for: 2
      - name: Panic Reset
        mode: "off"
        toggle_for: 5
        cancellable: false
```

### Configuration Options

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `name` | string | *required* | Friendly name for the switch entity. |
| `mode` | string | `"on"` | Operating mode: `"on"` for normally-off (pulse on), or `"off"` for normally-on (pulse off). |
| `toggle_for` | int / str | `1` | Duration to hold the active state in seconds before toggling back to idle. |
| `cancellable` | boolean | `false` | If `true`, manually toggling the switch during the countdown cancels the timer immediately and resets to idle. |

### Name Prefixes

* **No prefix** (default): The entity ID is derived directly from the name (e.g. `switch.doorbell`).
* **`+` prefix**: Tells the integration to prefix the entity ID with `momentary_` (e.g. `+Doorbell` creates `switch.momentary_doorbell`).

---

# Services

Momentary switch entities integrate directly with Home Assistant's standard `switch` platform services:

### `switch.turn_on`
Activates the switch into its timed state:
* In `mode: "on"` (default), this turns the switch **ON** for `toggle_for` duration, after which it automatically turns **OFF**.
* In `mode: "off"`, this resets the switch to its idle state (**ON**).

```yaml
service: switch.turn_on
target:
  entity_id: switch.front_doorbell
```

### `switch.turn_off`
Returns the switch to its idle state:
* If `cancellable: true` is configured and the switch is currently counting down in its active state, calling `switch.turn_off` cancels the countdown immediately and returns the switch to idle.
* If `cancellable: false` (default), calling `switch.turn_off` while the switch is active is safely ignored until the timer naturally elapses.

```yaml
service: switch.turn_off
target:
  entity_id: switch.staircase_timer
```

### `switch.toggle`
Toggles between the idle state and the active momentary timed state.

```yaml
service: switch.toggle
target:
  entity_id: switch.front_doorbell
```

---

# Turning on Debug

If you run into issues, enable debug logging in your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.momentary: debug
```
