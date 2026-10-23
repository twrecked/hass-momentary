# AI Agent Instructions for Creating Momentary Configurations

These guidelines instruct AI agents on how to generate, validate, and structure YAML configuration files (`momentary.yaml`) for the Home Assistant **Momentary** integration.

---

## 1. File Structure & Root Schema

Every configuration file must follow this exact top-level structure:

```yaml
version: 1
switches:
  - <switch_or_umbrella_device_1>
  - <switch_or_umbrella_device_2>
```

- **`version`**: Must be integer `1`.
- **`switches`**: List containing standalone switches or umbrella multi-switch device groups.

---

## 2. Topologies

The integration supports two layout patterns:

### Pattern A: Standalone Single-Switch Device
Use when a momentary switch represents its own independent device in Home Assistant's device registry:

```yaml
- name: Front Doorbell
  mode: "on"
  toggle_for: 1
  cancellable: false
```

### Pattern B: Umbrella Multi-Switch Device
Use when grouping multiple related momentary switches under a single physical or logical hardware device (e.g. keypads, multi-button wall panels, multi-relay boards):

```yaml
- Wall Keypad:
    - name: Keypad Button 1
      mode: "on"
      toggle_for: 1
      cancellable: false
    - name: Keypad Button 2
      mode: "on"
      toggle_for: 2
      cancellable: true
```
* The key (`Wall Keypad`) becomes the device name in the Home Assistant Device Registry.
* The items in the list become child `SwitchEntity` entities attached to that device.

---

## 3. Parameter Specifications

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `name` | string | **Yes** | — | The friendly name of the switch entity. |
| `mode` | string | No | `"on"` | Operating behavior: `"on"` for normally-off (pulse on), `"off"` for normally-on (pulse off). |
| `toggle_for` | integer / string | No | `1` | Duration to hold the active timed state before reverting to idle. Minimum `1` second. |
| `cancellable` | boolean | No | `false` | Whether turning the switch off early cancels the active countdown. |

### Parameter Details & Invariants

1. **`name` & Prefix Rules**:
   - Plain string (e.g., `Front Doorbell`): Results in entity ID `switch.front_doorbell`.
   - `+` prefix (e.g., `+Front Doorbell`): Adds the integration domain prefix to the entity ID, creating `switch.momentary_front_doorbell`.
   - `!` prefix (legacy): Strips `!` and creates standard entity ID.
   - Names must be unique within a group file.

2. **`mode` Rules**:
   - `"on"` (or `true`): **Normally Off / Pulse On** (default momentary pushbutton).
     - **Idle State**: `off` (False)
     - **Timed State**: `on` (True)
     - When turned on, stays on for `toggle_for` duration, then automatically reverts to `off`.
   - `"off"` (or `false`): **Normally On / Pulse Off** (normally-closed contacts, breaker resets).
     - **Idle State**: `on` (True)
     - **Timed State**: `off` (False)
     - When triggered off, stays off for `toggle_for` duration, then automatically reverts to `on`.

3. **`toggle_for` Rules**:
   - Integer seconds (e.g. `1`, `2`, `5`, `60`) is preferred for clean YAML serialization.
   - Can also accept Home Assistant time strings (e.g. `'00:00:05'`).
   - Must be greater than 0. Minimum recommended is `1` second.

4. **`cancellable` Rules**:
   - `false` (default): Once triggered, any service call attempting to toggle back during the countdown is safely ignored. The switch is guaranteed to hold its timed state until the countdown naturally completes.
   - `true`: Calling `switch.turn_off` (or opposite service) during an active countdown immediately cancels the timer and resets the entity to its idle state.

---

## 4. Standard Recipes for Common Use Cases

### Pushbutton / Doorbell (1 Second Pulse)
```yaml
- name: Front Doorbell
  mode: "on"
  toggle_for: 1
  cancellable: false
```

### Garage Door / Gate Opener (2 Second Pulse)
```yaml
- name: Garage Door Opener Trigger
  mode: "on"
  toggle_for: 2
  cancellable: false
```

### Staircase / Hallway Light Timer (60s with Early Cancel)
```yaml
- name: Staircase Light Timer
  mode: "on"
  toggle_for: 60
  cancellable: true
```

### Normally-Closed Reset / Breaker Trip (5s Break)
```yaml
- name: Router Power Reset
  mode: "off"
  toggle_for: 5
  cancellable: false
```

### Multi-Button Alarm Station (Umbrella Device)
```yaml
- Alarm Keypad Station:
    - name: Arm Away Pulse
      mode: "on"
      toggle_for: 1
      cancellable: false
    - name: Arm Home Pulse
      mode: "on"
      toggle_for: 1
      cancellable: false
    - name: Panic Trigger
      mode: "on"
      toggle_for: 3
      cancellable: true
```

---

## 5. Agent Generation Checklist

When writing or modifying a Momentary configuration:
- [ ] Root contains `version: 1` and `switches:` key.
- [ ] Indentation strictly uses 2 spaces (no tabs).
- [ ] Every entity has a descriptive `name`.
- [ ] `mode` is explicitly quoted (`"on"` or `"off"`) to prevent YAML boolean parsing ambiguities.
- [ ] `toggle_for` is an integer number of seconds >= 1.
- [ ] `cancellable` is explicitly set to `true` or `false` when relevant.
- [ ] Multiple related switches are grouped under an umbrella device dictionary.
