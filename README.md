# OctoPrint Emergency Stop Reloaded

This plugin reacts to a physical short lever microswitch output like [this](https://chinadaier.en.made-in-china.com/product/ABVJkvyMAqcT/China-1A-125VAC-on-off-Kw10-Mini-Micro-Mouse-Switch.html)
If actuated it issues configured command to printer.

Let's check some features:
* pop-up notification and sending of M112 G-CODE (customizable) when the emergency stop button is actuated
* test button so you know if your sensor really works or not
* info pop-up when plugin hasn't been configured
* user-friendly and easy to configure
* pin validation so you don't accidentally save wrong pin number
* detection of used GPIO mode - this makes it compatible with other plugins
* runs on OctoPrint 1.8.1 and higher

## Setup

Install manually using this URL:

    https://github.com/CMR-DEV/OctoPrint-EmergencyStopReloaded/archive/master.zip

## Configuration

Configuration consists of these parameters:
1. **Board mode** - Physical/BOARD or GPIO/BCM mode, **Physical/BOARD mode** - referring to the pins by the number, **GPIO/BCM mode** - referring to the pins
by the "Broadcom SOC channel", if this is selected by 3rd party, this option will be disabled with note on GUI
2. **pin number** - pin number based on selected mode
3. **power input to sensor** - input is connected to **ground or 3.3 V**
4. **switch type** - button should be **triggered when opened** (input of the sensor doesn't transfer to its output) or **triggered when closed** (input of the sensor is transferred to its output)
5. **g-code** to send to printer when the button is triggered - default is M112

Default pin is 0 (not configured) and ground (as it is safer, read below).

After configuring it is best to restart Octoprint and dry-run to check if the button works correctly in order to avoid any problems.

**WARNING! Never connect the switch input to 5V as it could fry the GPIO section of your Raspberry!**

#### Advice

You might experience the same problem as I experienced - the sensor was randomly triggered. Turns out that if running sensor wires along motor wires, it was enough to interfere with sensor reading.

To solve this connect a shielded wire to your sensor and ground the shielding, ideally on both ends.

If you are unsure about your sensor being triggered, check [OctoPrint logs](https://community.octoprint.org/t/where-can-i-find-octoprints-and-octopis-log-files/299)