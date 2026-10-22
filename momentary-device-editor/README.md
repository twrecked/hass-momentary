# Momentary Device Editor

A web-based visual builder for managing Home Assistant [Momentary](https://github.com/twrecked/hass-momentary) switches and multi-switch devices.

Hosted version available at: **[https://momentary-dot-twrecked-tools.nn.r.appspot.com](https://momentary-dot-twrecked-tools.nn.r.appspot.com)**

---

## Features

- **Visual Card Builder**: Add, edit, duplicate, and organize momentary switches and multi-button devices with a clean card UI.
- **Operating Modes**: Support for both standard "pulse-on" (turns off after timeout) and normally-closed "pulse-off" (turns on after timeout).
- **Duration Presets & Controls**: Configure toggle duration in seconds with one-click quick presets (1s, 2s, 5s, 10s, 30s, 60s).
- **Cancellable Option**: One-click configuration allowing premature toggling back to cancel the active countdown timer immediately.
- **Switch Templates**: Ready-to-use templates for common hardware patterns (Doorbell, Garage Opener Pulse, Staircase Timer, NC Breaker Reset, Multi-Button Keypad).
- **Live YAML Preview**: Real-time YAML generation side-by-side with your visual cards.
- **Automatic Home Assistant Sync**: If opened from Home Assistant's **Configure** dialog, clicking **Save & Return** automatically updates your YAML file on disk and reloads the integration via an authenticated webhook.
- **Manual Export & Import**: Full support for copying YAML to your clipboard, downloading the file, or pasting existing YAML directly into the editor.

---

## Running Locally (Private / Offline Mode)

If you prefer to run the editor locally on your home network without sending data through the cloud:

### 1. Requirements
* Python 3.10+
* Virtual environment (recommended)

### 2. Install & Run
```bash
cd momentary-device-editor
pip install -r requirements.txt
python main.py
```

The editor will start at: **`http://localhost:8080`** (and on your local network IP).

### 3. Connect to Home Assistant
In Home Assistant:
1. Go to **Settings -> Devices & Services -> Momentary**.
2. Click **Configure** on any group.
3. In the dialog, set **Editor URL** to your local address (e.g. `http://127.0.0.1:8080` or `http://192.168.1.X:8080`).
4. Click **Submit** to save your preference, then click **Open Momentary Device Editor**.

---

## Manual / Copy-Paste Fallback

If you don't use webhooks or have external access disabled:

1. Open the editor in your browser: [https://momentary-dot-twrecked-tools.nn.r.appspot.com](https://momentary-dot-twrecked-tools.nn.r.appspot.com).
2. Click **Import YAML** and paste your existing `momentary.yaml` content (or start from scratch with templates).
3. Make your edits visually.
4. Click **Copy** (or **Download**) in the top right bar.
5. Paste the YAML into your `/config/momentary.yaml` file using Home Assistant's File Editor or VS Code add-on.
6. In Home Assistant, go to **Settings -> Devices & Services -> Momentary**, click the three dots, and select **Reload**.

---

## Deployment to Google App Engine

The editor is configured as an App Engine service:

```bash
gcloud app deploy app.yaml
```
*(Make sure an App Engine `default` service is deployed in your GCP project first).*
