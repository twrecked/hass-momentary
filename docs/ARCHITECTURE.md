# 🏛️ `hass-momentary` System Architecture

This document describes the architectural design, lifecycle, and component interactions of `hass-momentary` (v0.8+).

---

## 1. High-Level Architecture Overview

```text
┌────────────────────────────────────────────────────────┐
│               momentary-*.yaml Files                   │
│   (Device groupings, standalone switches, durations)   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                       BlendedCfg                       │
│       (In-memory momentary hardware coordinator)       │
│  - Parses YAML switch definitions                      │
│  - Correlates with HA device_registry & entity_registry│
│  - Resolves standalone vs multi-entity switch IDs      │
│  - Generates deterministic unique IDs                  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                   async_setup_entry                    │
│                  (__init__.py Lifecycle)               │
│  - Registers/updates devices in HA device_registry     │
│  - Automatically prunes unreferenced/orphaned devices  │
│  - Automatically prunes unreferenced/orphaned entities │
│  - Forwards entry setup to switch platform             │
│  - Hosts token-authenticated builder hot-reload webhook│
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                 Switch Platform Platform               │
│                     (switch.py)                        │
│  - MomentarySwitch (RestoreEntity, SwitchEntity)       │
│  - Restores timestamps across HA restarts              │
│  - Resumes active timers via async_track_point_in_time │
│  - Supports Normally-Open (NO) & Normally-Closed (NC)  │
│  - Handles early cancellation when enabled             │
└────────────────────────────────────────────────────────┘
```

---

## 2. Configuration & Hub Coordinator Layer (`cfg.py`)

In standard physical integrations, a hardware bridge or cloud controller is queried during startup to discover devices and channels.

Because `hass-momentary` runs entirely in Home Assistant with local YAML configuration, **`BlendedCfg` acts as that virtual hardware coordinator**:

* **YAML Ingestion**: Loads user configuration files (`momentary.yaml`, `momentary-umbrella.yaml`, etc.) linked to a config entry.
  * **Standalone Switch**: Defined directly as a top-level list entry with `name: "My Switch"`. Represents a single device and switch entity.
  * **Multi-Entity Device Group**: Defined as a mapping key (e.g. `Momentary Umbrella:`) with a nested list of child switches (`- name: Front Doorbell Pulse`, etc.).
* **Registry Correlation**:
  * Directly queries Home Assistant's `device_registry` and `entity_registry` for the current config entry (`entry_id`).
* **3-Tier Identity Resolution**:
  1. **HA Native Registry**:
     * Existing devices are matched by identifier `(DOMAIN, device_slug)` or device name. Existing registered device IDs are reused.
     * Existing switch entities are matched by domain (`switch`) and `original_name`. Registered `unique_id` and `entity_id` are preserved, maintaining historical state, automations, and dashboard cards across reboots without disruption.
  2. **Legacy Storage Fallback**:
     * If not matched in HA's native registries, `BlendedCfg` checks legacy metadata (e.g. `.storage/momentary.meta.json`) for backwards compatibility during migration from older versions.
  3. **Deterministic ID Generation for New Entities**:
     * **Multi-Entity Devices**:
       * Entity ID: `switch.{switch_slug}` (or `switch.momentary_{switch_slug}` if prefixed with `+`). Does not repeat `dev_slug`.
       * Unique ID: `{dev_slug}_{switch_slug}.momentary`.
     * **Standalone Switches**:
       * Entity ID: `switch.{dev_slug}` (or `switch.momentary_{dev_slug}` if prefixed with `+`).
       * Unique ID: `{dev_slug}.momentary`.
     * **Device ID**: `slugify(clean_device_name)`.
* **Deprecation of Sidecar Storage**:
  * `.storage/momentary.meta.json` is no longer written to. Home Assistant's native registries serve as the single source of truth for identity and state.

---

## 3. Integration Lifecycle & Self-Cleaning Registries (`__init__.py`)

The integration entry lifecycle is managed in `custom_components/momentary/__init__.py`:

### Entry Setup (`async_setup_entry`)
1. **Device Registration**:
   Registers all devices defined in the YAML file into Home Assistant's `device_registry` with `manufacturer="twrecked"` and `model="momentary"`.
2. **Self-Cleaning Orphan Cleanup**:
   Compares all devices and entities currently registered in Home Assistant under this `config_entry_id` against active definitions in the YAML file:
   * **Orphaned Devices**: Any device belonging to this entry that is no longer in the YAML file (e.g. after a rename or removal) is automatically purged using `device_registry.async_remove_device()`.
   * **Orphaned Entities**: Any entity belonging to this entry that is no longer in the YAML file is automatically purged using `entity_registry.async_remove()`.
3. **Platform Forwarding**:
   Dispatches switch configurations to `custom_components/momentary/switch.py` via `hass.config_entries.async_forward_entry_setups()`.
4. **Hot-Reload Builder Webhook**:
   Registers an authenticated webhook endpoint (`/api/webhook/momentary_<entry_id>`). When the companion **Momentary Device Editor** web application saves changes, it delivers the updated YAML to this webhook, triggering an instantaneous reload of the config entry without requiring a full Home Assistant restart.

---

## 4. Entity Platform & Timing Mechanics (`switch.py`)

All momentary switches are implemented by `MomentarySwitch`, deriving from both `RestoreEntity` and `SwitchEntity`.

### A. Modes & Relay Logic
Momentary switches model physical pushbuttons, relays, and timers:
* **Normally-Open (NO) / Default Mode (`mode: "on"`, `"true"`, or `"old"`)**:
  * **Idle State**: `off` (relay contact open).
  * **Timed State**: `on` (relay contact closed).
  * Activating the switch turns it `on` for `toggle_for` duration, after which it automatically reverts to `off`.
* **Normally-Closed (NC) Mode (`mode: "off"` or `"false"`)**:
  * **Idle State**: `on` (relay contact closed).
  * **Timed State**: `off` (relay contact open / broken circuit).
  * Useful for power breaker resets, normally-closed circuit interrupters, or fail-safe triggers.

### B. State Persistence & Restart Recovery
* **`toggle_until` Timestamp**:
  * When switched into its timed state, `MomentarySwitch` computes an absolute UTC expiration timestamp (`toggle_until = now + toggle_for`) and exposes it in `extra_state_attributes`.
* **Restoration Across Restarts**:
  * During Home Assistant reboot, `_restore_state()` reads the saved `toggle_until` timestamp.
  * If the deadline is in the future (`toggle_until > now`), the switch resumes in its active timed state and schedules a point-in-time callback (`async_track_point_in_time`) for the remaining duration.
  * If the deadline has passed, the switch immediately restores to its idle state.

### C. Early Cancellation
* When configured with `cancellable: true`, toggling the switch while it is in its timed state cancels the active timer and immediately returns the switch to its idle state.
* When `cancellable: false`, re-triggering while active recalculates the expiration timestamp, extending the pulse.

---

## 5. Companion Momentary Device Editor & Webhook Integration

The integration includes a visual web editor companion (`momentary-device-editor/`):
* **Options Flow Launch**:
  * Selecting "Configure" on a Momentary integration entry opens an options dialog displaying an encrypted launch link (`builder_url`).
  * The link includes the current YAML content encoded in base64, the webhook callback URL, and an entry-specific security token.
* **Instant Hot Reload**:
  * Edits made in the browser editor are POSTed back directly to the webhook handler in `__init__.py`.
  * The webhook validates the token, atomically writes the updated YAML to disk, and triggers `async_reload` on the config entry.
