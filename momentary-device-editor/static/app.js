const { createApp, ref, computed, onMounted } = Vue;

function decodeBase64Utf8(base64Str) {
  try {
    const binary = atob(base64Str);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return new TextDecoder("utf-8").decode(bytes);
  } catch (e) {
    return atob(base64Str);
  }
}

const TEMPLATES = [
  {
    id: "pulse_1s",
    name: "Standard Push Button (1s)",
    description: "Momentary switch that turns ON for 1 second, then reverts to OFF.",
    create: (name) => ({
      name: name || "Doorbell",
      collapsed: false,
      switches: [
        {
          name: name || "Doorbell",
          mode: "on",
          toggle_for: 1,
          cancellable: false,
        },
      ],
    }),
  },
  {
    id: "garage_pulse",
    name: "Garage Door Pulse (2s)",
    description: "Momentary trigger switch for garage doors or gate openers.",
    create: (name) => ({
      name: name || "Garage Opener",
      collapsed: false,
      switches: [
        {
          name: name || "Garage Opener",
          mode: "on",
          toggle_for: 2,
          cancellable: false,
        },
      ],
    }),
  },
  {
    id: "staircase_timer",
    name: "Staircase / Hallway Timer (60s, Cancellable)",
    description: "Timed switch that turns ON for 60 seconds. Can be turned OFF early to cancel.",
    create: (name) => ({
      name: name || "Staircase Light Timer",
      collapsed: false,
      switches: [
        {
          name: name || "Staircase Light Timer",
          mode: "on",
          toggle_for: 60,
          cancellable: true,
        },
      ],
    }),
  },
  {
    id: "normally_closed_reset",
    name: "Normally-Closed Breaker Reset (5s)",
    description: "Normally ON switch that breaks contact (turns OFF) for 5s before reverting to ON.",
    create: (name) => ({
      name: name || "Power Reset",
      collapsed: false,
      switches: [
        {
          name: name || "Power Reset",
          mode: "off",
          toggle_for: 5,
          cancellable: false,
        },
      ],
    }),
  },
  {
    id: "multi_button_keypad",
    name: "Multi-Button Keypad (2 Buttons)",
    description: "A single device with multiple momentary switches.",
    create: (name) => ({
      name: name || "Wall Keypad",
      collapsed: false,
      switches: [
        {
          name: "Button 1",
          mode: "on",
          toggle_for: 1,
          cancellable: false,
        },
        {
          name: "Button 2",
          mode: "on",
          toggle_for: 2,
          cancellable: true,
        },
      ],
    }),
  },
];

createApp({
  setup() {
    const devices = ref([]);
    const showYamlSidebar = ref(true);
    const showTemplateModal = ref(false);
    const showManualYamlModal = ref(false);
    const rawYamlInput = ref("");
    const isSaving = ref(false);
    const saveStatus = ref(null);
    const saveMessage = ref("");
    const copyButtonText = ref("Copy");

    const callbackUrl = ref(window.__MOMENTARY_CALLBACK_URL || "");
    const token = ref(window.__MOMENTARY_TOKEN || "");
    const groupName = ref(window.__MOMENTARY_GROUP_NAME || "momentary.yaml");
    const initialYaml = ref(window.__MOMENTARY_INITIAL_YAML || "");

    const allCollapsed = computed(() => {
      return devices.value.length > 0 && devices.value.every((d) => d.collapsed);
    });

    const toggleAllCollapse = () => {
      const target = !allCollapsed.value;
      devices.value.forEach((d) => {
        d.collapsed = target;
      });
    };

    const toggleCollapse = (device) => {
      device.collapsed = !device.collapsed;
    };

    const setPresetDuration = (sw, seconds) => {
      sw.toggle_for = Number(seconds);
    };

    const addDevice = () => {
      const idx = devices.value.length + 1;
      const defaultName = `Momentary Switch ${idx}`;
      devices.value.push({
        name: defaultName,
        collapsed: false,
        switches: [
          {
            name: defaultName,
            mode: "on",
            toggle_for: 1,
            cancellable: false,
          },
        ],
      });
    };

    const removeDevice = (idx) => {
      devices.value.splice(idx, 1);
    };

    const duplicateDevice = (idx) => {
      const original = devices.value[idx];
      const cloned = JSON.parse(JSON.stringify(original));
      cloned.name = `${cloned.name} (Copy)`;
      if (cloned.switches.length === 1 && cloned.switches[0].name === original.name) {
        cloned.switches[0].name = cloned.name;
      }
      cloned.collapsed = false;
      devices.value.splice(idx + 1, 0, cloned);
    };

    const addSwitchToDevice = (dIdx) => {
      const dev = devices.value[dIdx];
      const num = dev.switches.length + 1;
      dev.switches.push({
        name: `${dev.name} ${num}`,
        mode: "on",
        toggle_for: 1,
        cancellable: false,
      });
    };

    const removeSwitch = (dIdx, sIdx) => {
      devices.value[dIdx].switches.splice(sIdx, 1);
    };

    const applyTemplate = (tmpl) => {
      const newDev = tmpl.create();
      devices.value.push(newDev);
      showTemplateModal.value = false;
    };

    const generatedYaml = computed(() => {
      const output = {
        version: 1,
        switches: [],
      };

      for (const dev of devices.value) {
        if (!dev.name || !dev.name.trim()) continue;
        const deviceName = dev.name.trim();

        if (dev.switches.length === 0) continue;

        // If single switch whose name matches device name, format as standalone switch
        if (dev.switches.length === 1 && dev.switches[0].name.trim() === deviceName) {
          const sw = dev.switches[0];
          const item = {
            name: sw.name.trim(),
            mode: sw.mode || "on",
            toggle_for: Number.isFinite(Number(sw.toggle_for)) ? Number(sw.toggle_for) : (sw.toggle_for || 1),
            cancellable: Boolean(sw.cancellable),
          };
          output.switches.push(item);
        } else {
          // Multi-switch device or name differs
          const children = [];
          for (const sw of dev.switches) {
            if (!sw.name || !sw.name.trim()) continue;
            children.push({
              name: sw.name.trim(),
              mode: sw.mode || "on",
              toggle_for: Number.isFinite(Number(sw.toggle_for)) ? Number(sw.toggle_for) : (sw.toggle_for || 1),
              cancellable: Boolean(sw.cancellable),
            });
          }
          if (children.length > 0) {
            output.switches.push({
              [deviceName]: children,
            });
          }
        }
      }

      try {
        return jsyaml.dump(output, { indent: 2, lineWidth: -1, noRefs: true });
      } catch (err) {
        return `# Error generating YAML: ${err.message}`;
      }
    });

    const parseYamlToDevices = (yamlContent) => {
      if (!yamlContent || !yamlContent.trim()) return [];
      const parsed = jsyaml.load(yamlContent);
      if (!parsed || typeof parsed !== "object") return [];

      const rawSwitches = Array.isArray(parsed.switches)
        ? parsed.switches
        : Array.isArray(parsed)
        ? parsed
        : [];

      const result = [];

      for (const item of rawSwitches) {
        if (!item || typeof item !== "object") continue;

        if ("name" in item) {
          // Standalone switch
          const name = String(item.name || "Momentary Switch");
          let mode = "on";
          if (item.mode !== undefined) {
            const m = String(item.mode).toLowerCase();
            if (m === "off" || m === "false") mode = "off";
          }
          result.push({
            name,
            collapsed: false,
            switches: [
              {
                name,
                mode,
                toggle_for: item.toggle_for !== undefined ? item.toggle_for : 1,
                cancellable: Boolean(item.cancellable),
              },
            ],
          });
        } else {
          // Multi-switch device: { "Device Name": [ { name: ... } ] }
          const keys = Object.keys(item);
          if (keys.length > 0) {
            const deviceName = keys[0];
            const children = Array.isArray(item[deviceName]) ? item[deviceName] : [];
            const switchList = [];

            for (const child of children) {
              if (!child || typeof child !== "object") continue;
              const sName = String(child.name || "Switch");
              let mode = "on";
              if (child.mode !== undefined) {
                const m = String(child.mode).toLowerCase();
                if (m === "off" || m === "false") mode = "off";
              }
              switchList.push({
                name: sName,
                mode,
                toggle_for: child.toggle_for !== undefined ? child.toggle_for : 1,
                cancellable: Boolean(child.cancellable),
              });
            }

            result.push({
              name: deviceName,
              collapsed: false,
              switches: switchList.length > 0 ? switchList : [
                { name: deviceName, mode: "on", toggle_for: 1, cancellable: false }
              ],
            });
          }
        }
      }

      return result;
    };

    const importRawYaml = () => {
      try {
        const imported = parseYamlToDevices(rawYamlInput.value);
        if (imported.length === 0) {
          alert("No switches found in the provided YAML.");
          return;
        }
        devices.value = imported;
        showManualYamlModal.value = false;
        rawYamlInput.value = "";
      } catch (err) {
        alert(`Failed to parse YAML: ${err.message}`);
      }
    };

    const copyYaml = () => {
      navigator.clipboard.writeText(generatedYaml.value).then(() => {
        copyButtonText.value = "Copied!";
        setTimeout(() => {
          copyButtonText.value = "Copy";
        }, 2000);
      });
    };

    const downloadYaml = () => {
      const blob = new Blob([generatedYaml.value], { type: "text/yaml;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = groupName.value.endsWith(".yaml") ? groupName.value : `${groupName.value}.yaml`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    };

    const saveAndReturn = async () => {
      if (!callbackUrl.value) {
        downloadYaml();
        return;
      }

      isSaving.value = true;
      saveStatus.value = null;
      saveMessage.value = "";

      try {
        const response = await fetch("/api/save", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            callback_url: callbackUrl.value,
            token: token.value,
            yaml: generatedYaml.value,
          }),
        });

        const data = await response.json();
        if (response.ok && data.ok) {
          saveStatus.value = "success";
          saveMessage.value = "Saved successfully! Home Assistant is reloading your momentary configuration.";
        } else {
          saveStatus.value = "danger";
          saveMessage.value = data.error || `Failed to save (Status ${response.status})`;
        }
      } catch (err) {
        saveStatus.value = "danger";
        saveMessage.value = `Error communicating with server: ${err.message}`;
      } finally {
        isSaving.value = false;
      }
    };

    const closeTab = () => {
      window.close();
    };

    onMounted(() => {
      // 1. Try URL Hash #data=...
      const hash = window.location.hash;
      let loadedYaml = "";

      if (hash && hash.includes("data=")) {
        try {
          const rawParam = hash.substring(hash.indexOf("data=") + 5);
          loadedYaml = decodeBase64Utf8(decodeURIComponent(rawParam));
        } catch (e) {
          console.error("Failed to decode data from hash:", e);
        }
      }

      // 2. Fall back to injected initial YAML
      if (!loadedYaml && initialYaml.value) {
        loadedYaml = initialYaml.value;
      }

      if (loadedYaml && loadedYaml.trim()) {
        try {
          const parsed = parseYamlToDevices(loadedYaml);
          if (parsed && parsed.length > 0) {
            devices.value = parsed;
            return;
          }
        } catch (e) {
          console.error("Failed to parse initial YAML:", e);
        }
      }

      // Default starter if empty
      if (devices.value.length === 0) {
        devices.value.push({
          name: "Front Door Bell",
          collapsed: false,
          switches: [
            {
              name: "Front Door Bell",
              mode: "on",
              toggle_for: 1,
              cancellable: false,
            },
          ],
        });
      }
    });

    return {
      devices,
      showYamlSidebar,
      showTemplateModal,
      showManualYamlModal,
      rawYamlInput,
      isSaving,
      saveStatus,
      saveMessage,
      copyButtonText,
      callbackUrl,
      token,
      groupName,
      allCollapsed,
      templates: TEMPLATES,
      generatedYaml,
      toggleAllCollapse,
      toggleCollapse,
      setPresetDuration,
      addDevice,
      removeDevice,
      duplicateDevice,
      addSwitchToDevice,
      removeSwitch,
      applyTemplate,
      importRawYaml,
      copyYaml,
      downloadYaml,
      saveAndReturn,
      closeTab,
    };
  },
}).mount("#app");
