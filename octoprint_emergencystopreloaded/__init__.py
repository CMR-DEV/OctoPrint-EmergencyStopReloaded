# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin as plugin
import re
from octoprint.events import Events
from time import sleep
import RPi.GPIO as GPIO
import flask
from enum import IntEnum, unique

@unique
class GPIO_MODE( IntEnum ):
    UNSET   = -1
    BOARD   = 10
    BCM     = 11

    @classmethod
    def has_name( cls, name ):
        return name in cls._value2member_map_

class EmergencyStopReloadedPlugin(
    plugin.StartupPlugin,
    plugin.EventHandlerPlugin,
    plugin.TemplatePlugin,
    plugin.SettingsPlugin,
    plugin.SimpleApiPlugin,
    plugin.BlueprintPlugin,
    plugin.AssetPlugin):

    # default gcode
    default_gcode       = "M112"

    # gpio mode set by 3rd party
    gpio_mode_disabled  = False

    # gpio mode set by this plugin
    gpio_mode_set = False

    # whether or not there is a sensor test running currently
    testing            = False

    # whether or not the printer is currently printing
    printing            = False

    # whether or not the gcode has already been sent
    gcode_sent          = False

    initialized         = False

    def initialize( self ):
        GPIO.setwarnings( False )

    @property
    def setting_gpio_mode( self ):
        return int( self._settings.get( ["gpio_mode"] ) )

    @property
    def setting_pin( self ):
        return int( self._settings.get( ["pin"] ) )

    @property
    def setting_power( self ):
        return int( self._settings.get( ["power"] ) )

    @property
    def setting_gcode( self ):
        return self._settings.get( ["g_code"] )

    @property
    def setting_triggered( self ):
        return int( self._settings.get( ["triggered"] ) )

    @property
    def setting_bounce_time( self ):
        return int( self._settings.get( ["bounce_time"] ) )

    @property
    def setting_reading_iterations( self ):
        return int( self._settings.get( ["reading_iterations"] ) )

    @property
    def setting_reading_delay( self ):
        return int( self._settings.get( ["reading_delay"] ) )

    # AssetPlugin hook
    def get_assets( self ):
        return {
            "js":   [ "js/emergencystopreloaded.js"    ],
            "css":  [ "css/emergencystopreloaded.css"  ],
        }

    # Template hooks
    def get_template_configs( self ):
        return [{
            "type":                 "settings",
            "custom_bindings":      True
        }]

    # Settings hook
    def get_settings_defaults( self ):
        return {
            "gpio_mode":            GPIO_MODE.BOARD.value,
            "pin":                  0,
            "power":                0,
            "g_code":               self.default_gcode,
            "triggered ":           0,

            "bounce_time":          250,
            "reading_iterations":   5,
            "reading_delay":        100,
        }

    @plugin.BlueprintPlugin.route( "/state", methods=[ "GET" ] )
    def on_api_get_state( self ):
        self._logger.debug("getting state info")

        return flask.jsonify( printing=self.printing, gpio_mode_disabled=self.gpio_mode_disabled )

    # simpleApiPlugin
    def get_api_commands( self ):
        return { "testSensor": [ "pin", "power" ] }

    # test pin value, power pin or if its used by someone else
    def on_api_command( self, command, data ):

        try:
            selected_power          = int( data.get("power") )
            selected_pin            = int( data.get("pin") )
            selected_mode           = int( data.get("mode") )
            selected_switch_type    = int( data.get("triggered") )

            if selected_pin is 0:
                return "", 556

            self.testing = True

            # init gpios with the test values:
            self.init_gpio(
                selected_mode,
                selected_pin,
                selected_power,
                selected_switch_type,
                True
            )

            # take measurement:
            triggered = self.read_sensor_multiple(
                selected_pin,
                selected_power,
                selected_switch_type
            )

            # restore gpio setup with the values from the plugin settings:
            self.init_gpio(
                self.setting_gpio_mode,
                self.setting_pin,
                self.setting_power,
                self.setting_triggered
            )

            return flask.jsonify( triggered=triggered )
            self.testing = False


        except ValueError as e:
            self._logger.error( str(e) )
            # ValueError occurs when reading from power, ground or out of range pins
            return "", 556

    def send_gcode( self, msg ):

        self._logger.info( f"Sending GCODE: {self.setting_gcode}" )
        self._printer.commands( self.setting_gcode )
        self.gcode_sent = True

        self._plugin_manager.send_plugin_message(
            self._identifier,
            {
                "type":         "error",
                "autoClose":    False,
                "msg":          str( msg )
            }
        )

    def sensor_callback( self, _ ):

        if self.testing:
            return

        self._logger.info( "Sensor callback called" )

        if self.read_sensor_multiple( self.setting_pin, self.setting_power, self.setting_triggered ):

            if not self.gcode_sent:
                self.send_gcode( "Triggered!" )

        else:
            self.gcode_sent = False

    def init_gpio( self, gpio_mode, pin, power, trigger_mode, test = False ):
        self._logger.info( "Initializing GPIO" )

        preset_gpio_mode = GPIO.getmode()

        if preset_gpio_mode is not None:
            self.gpio_mode_disabled = True
            gpio_mode               = preset_gpio_mode
            self._settings.set( [ "gpio_mode" ], preset_gpio_mode )

        else:
            self._logger.info( "Preset mode is %s" % preset_gpio_mode )

        if self.plugin_enabled( pin ):

            gpio_mode_name = GPIO_MODE(gpio_mode).name if GPIO_MODE.has_name( gpio_mode ) else "???"

            self._logger.info( f"Enabling emergency stop sensor with GPIO mode { gpio_mode } ({ gpio_mode_name })" )

            # BOARD
            if gpio_mode == GPIO_MODE.BOARD:

                # if mode set by 3rd party don't set it again
                if not self.gpio_mode_disabled:
                    self._logger.info( "Setting Board mode" )
                    GPIO.cleanup()
                    GPIO.setmode( GPIO.BOARD )
                    self.gpio_mode_set = True

                # first check pins not in use already
                usage = GPIO.gpio_function( pin )
                self._logger.debug( f"Usage on pin {pin} is {usage}" )
                # 1 = input
                if usage is not 1:
                    # 555 is not http specific so I chose it
                    return "", 555

            # BCM
            elif gpio_mode == GPIO_MODE.BCM:

                # BCM range 1-27
                if pin > 27:
                    return "", 556

                # if mode set by 3rd party don't set it again
                if not self.gpio_mode_disabled:
                    self._logger.debug( "Setting BCM mode" )
                    GPIO.cleanup()
                    GPIO.setmode( GPIO.BCM )
                    self.gpio_mode_set = True

            # attach event listener ( = self.sensor_callback ) when method is not called for testing:
            if not test:
                try:
                    # 0 = sensor is grounded, react to rising edge pulled up by pull up resistor
                    if power is 0:

                        self.pull_resistor( pin, power )

                        # triggered when open
                        if trigger_mode is 0:
                            self._logger.debug( "Reacting to rising edge" )
                            GPIO.add_event_detect(

                                pin,
                                GPIO.RISING,
                                callback=self.sensor_callback,
                                bouncetime=self.setting_bounce_time

                            )

                        # triggered when closed
                        else:
                            self._logger.debug( "Reacting to falling edge" )
                            GPIO.add_event_detect(

                                pin,
                                GPIO.FALLING,
                                callback=self.sensor_callback,
                                bouncetime=self.setting_bounce_time

                            )

                    # 1 = sensor is powered, react to falling edge pulled down by pull down resistor
                    else:

                        self.pull_resistor( pin, power )

                        # triggered when open
                        if trigger_mode is 0:
                            self._logger.debug( "Reacting to falling edge" )
                            GPIO.add_event_detect(

                                pin,
                                GPIO.FALLING,
                                callback=self.sensor_callback,
                                bouncetime=self.bounce_time

                            )
                        # triggered when closed
                        else:
                            self._logger.debug( "Reacting to rising edge" )
                            GPIO.add_event_detect(
                                pin, GPIO.RISING,
                                callback=self.sensor_callback,
                                bouncetime=self.bounce_time)

                except RuntimeError as e:
                    self._logger.warn( str( e ) )
        else:
            self._logger.info( "Sensor disabled" )

    # pulls resistor up or down based on the parameters
    def pull_resistor( self, pin, power ):
        if power is 0:
            # self._logger.debug("Pulling up resistor")
            GPIO.setup( pin, GPIO.IN, pull_up_down=GPIO.PUD_UP )

        elif power is 1:
            # self._logger.debug("Pulling down resistor")
            GPIO.setup( pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN )

        # self._logger.debug("Done")

    def on_after_startup( self ):
        self._logger.info( "Emergency Stop Reloaded started" )

        self.init_gpio(
            self.setting_gpio_mode,
            self.setting_pin,
            self.setting_power,
            self.setting_triggered
        )

        self.initialized = True

        if self.plugin_enabled( self.setting_pin ):
            self._logger.info( "Reading sensor due to startup" )
            self.sensor_callback( None ) # inital read

    def on_settings_save( self, data ):
        # Retrieve any settings not changed in order to validate that the combination of new and old settings end up in a bad combination

        self._logger.info( "Saving settings for Emergency Stop Reloaded" )

        pin_to_save             = self._settings.get_int(["pin"])
        gpio_mode_to_save       = self._settings.get_int(["gpio_mode"])
        power_to_save           = self._settings.get_int(["power"])
        trigger_mode_to_save    = self._settings.get_int(["triggered"])

        for key in [
            "pin",
            "gpio_mode",
            "power",
            "trigger",

            "bounce_time",
            "reading_iterations",
            "reading_delay",
        ]:
            if key in data:
                value = data.get( key )

                if not value.isdigit():

                    self._plugin_manager.send_plugin_message(
                        self._identifier,
                        {
                            "type":         "error",
                            "autoClose":    True,
                            "msg":          f"Emergency stop settings not saved: {key} is not an integer"
                        }
                    )

                    return

                intVal = int( value )

                if key is "reading_iterations" and intVal < 1:

                    self._plugin_manager.send_plugin_message(
                        self._identifier,
                        {
                            "type":         "error",
                            "autoClose":    True,
                            "msg":          f"Emergency stop settings not saved: {key} must be positive"
                        }
                    )

                    return

                elif key in ( "bounce_time", "reading_delay" ) and intVal < 0:

                    self._plugin_manager.send_plugin_message(
                        self._identifier,
                        {
                            "type":         "error",
                            "autoClose":    True,
                            "msg":          f"Emergency stop settings not saved: {key} must be non-negative"
                        }
                    )

                    return

        if "pin" in data:
            pin_to_save             = int( data.get("pin") )

        if "gpio_mode" in data:
            gpio_mode_to_save       = int( data.get("gpio_mode") )

        if "power" in data:
            power_to_save           = int( data.get("power") )

        if "trigger" in data:
            trigger_mode_to_save    = int( data.get("triggered") )

        # pin validation:
        if pin_to_save is not None:
            # check if pin is not power/ground pin or out of range but allow the disabled value (0)
            if pin_to_save is not 0:
                try:
                    # BOARD
                    if gpio_mode_to_save == GPIO_MODE.BOARD:
                        # before saving check if pin not used by others
                        usage = GPIO.gpio_function( pin_to_save )
                        self._logger.debug( f"usage on pin {pin_to_save} is {usage}" )

                        if usage is not 1:
                            self._logger.info( f"You are trying to save pin {pin_to_save} which is already used by others" )
                            self._plugin_manager.send_plugin_message(
                                self._identifier,
                                {
                                    "type":         "error",
                                    "autoClose":    True,
                                    "msg":          "Emergency stop settings not saved, you are trying to use a pin which is already used by others"
                                }
                            )
                            return
                    # BCM
                    elif gpio_mode_to_save == GPIO_MODE.BCM:

                        if pin_to_save > 27:
                            self._logger.info( f"You are trying to save pin {pin_to_save} which is out of range" )
                            self._plugin_manager.send_plugin_message(
                                self._identifier, {
                                    "type":         "error",
                                    "autoClose":    True,
                                    "msg":          "Emergency stop settings not saved, you are trying to use a pin which is out of range"
                                }
                            )
                            return

                except ValueError:
                    self._logger.info( f"You are trying to save pin {pin_to_save} which is ground/power pin or out of range" )
                    self._plugin_manager.send_plugin_message(
                        self._identifier, {
                            "type":         "error",
                            "autoClose":    True,
                            "msg":          "Emergency stop settings not saved, you are trying to use a pin which is ground/power pin or out of range"
                        }
                    )

                    return

                self.init_gpio(
                    gpio_mode_to_save,
                    pin_to_save,
                    power_to_save,
                    trigger_mode_to_save
                )

        plugin.SettingsPlugin.on_settings_save( self, data )

    def read_sensor_multiple( self, pin, power, trigger_mode ):

        gpio_mode_name = " " + GPIO_MODE( self.setting_gpio_mode ).name if GPIO_MODE.has_name( self.setting_gpio_mode ) else ""

        self._logger.info( f"Reading sensor values {self.setting_reading_iterations} times from{gpio_mode_name} pin {pin}" )

        prevVal = None
        i       = 0

        # take a reading of multiple consecutive reads to prevent false positives
        while True:
            curentVal = self.read_sensor( pin, power, trigger_mode )
            i += 1

            if prevVal is None:
                prevVal = curentVal

            elif prevVal != curentVal:
                i = 0
                self._logger.info( "Repeating sensor read due to false positives" )

            if i < self.setting_reading_iterations:
                sleep( self.setting_reading_delay / 1000 )

            else:

                self._logger.info( f"Reading result: {curentVal}" )
                return curentVal

    # read sensor input value
    def read_sensor( self, pin, power, trigger_mode ):

        # self._logger.debug("Reading pin %s " % pin)

        self.pull_resistor( pin, power )

        return ( GPIO.input( pin ) + power + trigger_mode ) % 2 is 0

    # plugin disabled if pin set to 0
    def plugin_enabled( self, pin ):
        return pin >= 0

    def on_event( self, event, payload ):

        if event in (
            Events.HOME,
            Events.Z_CHANGE,
            Events.CONNECTED,
            Events.PRINT_STARTED,
            Events.PRINT_RESUMED
        ):

            self.gcode_sent = False

            if event in ( Events.PRINT_STARTED, Events.PRINT_RESUMED ):
                self.printing = True

            # ignore z_change when printing
            if event is not Events.Z_CHANGE or not self.printing:

                if self.initialized and self.plugin_enabled( self.setting_pin ):

                    self._logger.debug( "Reading sensor due to event: " + event )

                    if self.read_sensor_multiple( self.setting_pin, self.setting_power, self.setting_triggered ):
                        self.send_gcode( "Emergency stop is still active! Please reset!" )

        elif event is Events.CLIENT_OPENED:

            # if the plugin hasn't been configured
            if not self.plugin_enabled( self.setting_pin ):

                self._plugin_manager.send_plugin_message(

                    self._identifier,
                    dict(
                        type        = "info",
                        autoClose   = True,
                        msg         = "Don't forget to configure this plugin."
                    )

                )

        elif event in (
            Events.PRINT_DONE,
            Events.PRINT_FAILED,
            Events.PRINT_CANCELLED,
            Events.ERROR,
            Events.E_STOP
        ):

            self._logger.debug( "Resetting due to event: " + event )
            self.gcode_sent = False
            self.printing   = False

        # else:
            # self._logger.debug( "Event: " + event )

    def get_update_information( self ):

        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        # for details.

        return {

            "emergencystopreloaded": {

                "displayName":      "Emergency Stop Reloaded",
                "displayVersion":   self._plugin_version,

                # version check: github repository
                "type":             "github_release",
                "user":             "CMR-DEV",
                "repo":             "OctoPrint-EmergencyStopReloaded",
                "current":          self._plugin_version,

                # update method: pip
                "pip":              "https://github.com/CMR-DEV/OctoPrint-EmergencyStopReloaded/archive/{target_version}.zip"

            }

        }


# Starting with OctoPrint 1.4.0 OctoPrint will also support to run under Python 3 in addition to the deprecated
# Python 2. New plugins should make sure to run under both versions for now. Uncomment one of the following
# compatibility flags according to what Python versions your plugin supports!
# __plugin_pythoncompat__ = ">=2.7,<3" # only python 2
__plugin_pythoncompat__ = ">=3,<4" # only python 3
#__plugin_pythoncompat__ = ">=2.7,<4"  # python 2 and 3

__plugin_name__     = "Emergency Stop Reloaded"
__plugin_version__  = "1.0.0"


def __plugin_check__():

    try:
        import RPi.GPIO as GPIO

        if GPIO.VERSION < "0.6":  # Need at least 0.6 for edge detection
            return False

    except ImportError:
        return False

    return True


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = EmergencyStopReloadedPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
