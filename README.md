# hass-momentary
![icon](images/momentary-icon.png)

### Momentary Switch Component for Home Assistant
A simple switch component that once turned on will turn itself off.

### NOTES!
**This documentation is for the 0.7x version, you can find the
0.6.x version** [here](https://github.com/twrecked/hass-momentary/blob/version-0.6.x/README.md).

This is a big update that moves the component over to the `config_flow`
system. The update should be seamless but if you run into any problems:

- You can revert back to the previous version (0.6) and it will still work.
- But if you can re-run the upgrade operation with debug enabled and create a
  bug report I would greatly appreciate it.


## Table Of Contents

1. [Notes](#Notes)
1. [Thanks](#Thanks)
1. [Installation](#Installation)
   1. [HACS](#HACS)
   1. [Manually](#Manually)
   1. [From Script](#From-Script)
1. [Component Configuration](#Component-Configuration)
2. [Upgrade Notes](#Upgrade-notes)


## Notes

Wherever you see `/config` in this README it refers to your home-assistant
configuration directory. For me, for example, it's `/home/steve/ha` that is
mapped to `/config` inside my docker container.


## Thanks

Many thanks to:
* [JetBrains](https://www.jetbrains.com/?from=hass-aarlo) for the excellent
  **PyCharm IDE** and providing me with an open source license to speed up the
  project development.
 
  [![JetBrains](/images/jetbrains.svg)](https://www.jetbrains.com/?from=hass-aarlo)

* Icon adapted from [svg icons](https://www.onlinewebfonts.com/icon)
  and is licensed by CC BY 4.0


## Installation

### HACS
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)

Momentary is part of the default HACS store. If you're not interested in
development branches this is the easiest way to install.

### Manually
Copy the `momentary` directory into your `/config/custom_components` directory.

### From Script
Run the install script. Run it once to make sure the operations look sane and
run it a second time with the `go` parameter to do the actual work. If you
update just rerun the script, it will overwrite all installed files.

```sh
install /config
# check output looks good
install go /config
```


## Component Configuration
Add the component using the standard _Home Assistant_  _Integration_ method.

Because this component creates fake entries and because I'm still figuring out
the _Config Flow_ interface you still have to configure it by file.

The default file is named `/config/momentary.yaml` and is a similar format to
the standard _Home Assistant_ configuration files. This file will be created
during an upgrade or when you add in a _Momentary_ integration. An empty 
file looks like this:


```yaml
version: 1
switches:
```

To create a single momentary device add the following:

```yaml
version: 1
switches:
- name: Empty House Trigger
```

To create a single momentary device with custom options use:

```yaml
version: 1
switches:
- name: Empty House Trigger
  mode: "on"
  toggle_for: 5
  cancellable: True
```

To create multiple momentary device add more devices at the bottom:

```yaml
version: 1
switches:
- name: Empty House Trigger
  mode: "on"
  toggle_for: 5
  cancellable: True
- name: Full House Trigger
- name: Overflowing House Trigger
  toggle_for: 2
```

Once you've updated the file you will need to reload the component from its
integration setting.

The integration uses the name to distinguish different switches. If you can 
the name of a switch the old name will be deleted and the new name created 
on reload. 

### Options

The following additional parameters can be specified against the switches:

| Field                   | Type       | Default            | Description                                                                        |
| ----------------------- | ---------- | ------------------ | -------------------------------------------------------------------------------    |
| name                    | strings    |                    | Name of the switch. Has to be supplied.                                            |
| mode                    | string     | "on"               | Is the switch a momentary ON or OFF switch. Use `"on"` for on and `"off"` for off. |
| toggle_for              | seconds    | 1                  | Amount of time to turn toggle switch for.                                          |
| cancellable             | Boolean    | False              | Allow switched to be untoggled manually.                                           |



## Upgrade Notes

### After the Upgrade

Check the devices and entities on the _Integrations_ page, if everything looks
good then you can comment out the old configuration. _Don't delete it yet, this
is alpha and I might change some settings..._

### Names

The qualifier applied to the name has changed. The old qualify of `!` has been
removed, not adding _momentary_ to the device/entity name is the default. A 
new qualify of `+` has been created, adding this tells the integration to add 
_momentary_ to the device/entity name.

The upgrade code will change this for you.

| Old Name             | New Name                      | Entity Name                          |
|----------------------| ----------------------------- | ------------------------------------ |
| Empty House Trigger  | +Empty House Trigger          | switch.momentary_empty_house_trigger |
| !Empty House Trigger | Empty House Trigger           | switch.empty_house_trigger           |

### `unique_id`

During an upgrade the original name based unique id will be created. For a new
install a _UUID_ based unique id will be created.

If you want to move to the new _UUID_ based unique IDs you can manage this
with the following:

- Delete the _Momentary_ integration.
- Delete `/config/.storage/momentary.meta.json`
- Add the _Momentary_ integration.

The system will re-create your devices with the correct entity ids but with
new _UUID_ based unique ids.

_I will look at how this can be made cleaner... maybe a config flow button 
or as part of the upgrade._

### Known Issues

You will see errors like this on upgrade. They don't seem to cause an issue 
and they disappear once you remove the legacy configuration.

```
2023-10-13 17:28:09.154 ERROR (MainThread) [homeassistant.components.switch] The momentary platform for the switch integration does not support platform setup. Please remove it from your config.
```

### Turning on Debug

If you do run into issues you can enable debug with the following configration.

```yaml
logger:
  default: info
  logs:
    custom_components.momentary: debug
```

If you can create a bug report with this debug output it would help me track 
down the problem.
