$( function() {
	
	function EmergencyStopReloadedViewModel( parameters ) {
		
		var self = this;
		
		self.invalidPhysicalPins				= [ 1, 2, 4, 6, 9, 14, 17, 20, 25, 27, 28, 30, 34, 39 ];
		
		self.settingsViewModel			= parameters[ 0 ];
		
		self.testSensorResult			= ko.observable( null );
		self.printing					= ko.observable( false );
		
		self.gpio_mode_disabled			= ko.observable( false );
		
		self.onDataUpdaterPluginMessage = function( plugin, data ) {
			
			if ( plugin !== "emergencystopreloaded" ) return;
			
			new PNotify( {
				
				title: "Emergency Stop Reloaded",
				text:  new Date().toLocaleString() + ": " + data.msg,
				type:  data.type,
				hide:  data.autoClose,
				
			} );

		};
		
		self.getSetting = function( ids ) {
			
			if ( !Array.isArray( ids ) ) ids = [ ids ];
			
			return $(
				ids
				.filter( id => typeof id == "string" )
				.map( id => "#emergencystopreloaded_settings_" + id ).join( ", " )
			);
			
		};

		self.testSensor = function() {
			
            // Cleanup:
			self.getSetting( "testResult" )
			.hide()
			.removeClass( "hide alert-warning alert-error alert-info alert-success" );
			
            // Make api request:
			$.ajax( {
				url:         "/api/plugin/emergencystopreloaded",
				type:        "post",
				dataType:    "json",
				contentType: "application/json",
				headers:     { "X-Api-Key": UI_API_KEY },
					
				data: JSON.stringify( {
						
					command:   "testSensor",
					pin:       self.getSetting( "pinInput" ).val(),
					power:     self.getSetting( "powerInput" ).val(),
					mode:      self.getSetting( "gpioMode" ).val(),
					triggered: self.getSetting( "triggeredInput" ).val(),
						
				} ),
					
				statusCode: {
						
					500:	function() {
							
						self.getSetting( "testResult" )
						.addClass( "alert-error" );
							
						self.testSensorResult( "<i class=\"fas icon-warning-sign fa-exclamation-triangle\"></i> OctoPrint experienced a problem. Check octoprint.log for further info." );
							
					},
						
					555:	function() {
							
						self.getSetting( "testResult" )
						.addClass( "alert-error" );
							
						self.testSensorResult( "<i class=\"fas icon-warning-sign fa-exclamation-triangle\"></i> This pin is already in use, choose other pin." );
							
					},
						
					556:	function() {
							
						self.getSetting( "testResult" )
						.addClass( "alert-error" );
							
						self.testSensorResult( "<i class=\"fas icon-warning-sign fa-exclamation-triangle\"></i> The pin selected is power, ground or out of range pin number, choose other pin" );
							
					},
						
				},
					
				error:	function() {
						
					self.getSetting( "testResult" )
					.addClass( "alert-error" );
						
					self.testSensorResult( "<i class=\"fas icon-warning-sign fa-exclamation-triangle\"></i> There was an error :(" );
						
				},
					
				success:	function( result ) {
						
					switch ( result.triggered ) {
								
						case true:
							
							self.getSetting( "testResult" )
							.addClass( "alert-success" );
								
							self.testSensorResult( "<i class=\"fa fa-toggle-on\"></i> Sensor triggered! ( This whould send the G-code. )" );
								
							break;
							
						case false:
							
							self.getSetting( "testResult" )
							.addClass( "alert-info" );
							self.testSensorResult( "<i class=\"fa fa-toggle-off\"></i> Sensor not triggered!" );
								
							break;
							
						default:
								
							self.getSetting( "testResult" )
							.addClass( "alert-error" );
								
							self.testSensorResult( `<i class="fas icon-warning-sign fa-exclamation-triangle"></i> Received an unexpected server response: ${ result.triggered }` );
								
							break;
					
					}
						
				},
			}
				
			).always( function() {
				
				self.getSetting( "testResult" ).fadeIn();
				
			} );
			
		};

		self.checkWarningPullUp = function( event ) {
			
            	// Which mode are we using:
			let	mode				= parseInt( self.getSetting( "gpioMode" ).val(), 10 ),
			
				// Pin input element:
				pinInput			= self.getSetting( "pinInput" ),
			
            	// What pin is the sensor connected to:
				pin					= parseInt( pinInput.val(), 10 ),
			
            	// What is the sensor connected to - ground ( 0 ) or 3.3v ( 1 ):
				sensorWiring		= parseInt( self.getSetting( "powerInput" ).val(), 10 ),
				
				// some pins have physical pull up resistors which disallow wiring to 3.3v:
				pullUpPins			= ( {
					
					10: [ 3, 5 ], // Physical mode
					11: [ 2, 3 ], // BCM mode
					
				} )[ mode ],
				
				max					= ( { 10: 40, 11: 27 } )[ mode ],
				
				pullUpWarning		= self.getSetting( "pullupwarn" ),
				badPinWarning		= self.getSetting( "badpin" );
			
			// Set max attr to right board type:
			pinInput.attr( "max", max );
				
            // Toggle pull up warning:
			if ( sensorWiring == 1 && pullUpPins.includes( pin ) ) {
				
				pullUpWarning
				.removeClass( "hidden pulsAlert" )
				.addClass( "pulsAlert" );
				
			} else {
				
				pullUpWarning
				.addClass( "hidden" )
				.removeClass( "pulsAlert" );
				
			}
			
			if ( // show badPinWarning if...
				
				( mode == 10 && self.invalidPhysicalPins.includes( pin ) ) || // pin is ground or voltage pin
				
				( mode == 11 && pin == 1 ) || // pin is GPIO 1 which is reserved for I2C HAT communication
				
				// is out of range:
				pin > pinInput.attr( "max" ) ||
				pin < 0
				
			) {
				
				badPinWarning
				.removeClass( "hidden pulsAlert" )
				.addClass( "pulsAlert" );
			
			} else {
					
				badPinWarning
				.addClass( "hidden" )
				.removeClass( "pulsAlert" );
				
			}
		
		};

		self.fetchState = function( item ) {
			
			$.ajax( {
				
				type:     "GET",
				dataType: "json",
				url:      "plugin/emergencystopreloaded/state",
				success:  function( result ) {
					
					self.gpio_mode_disabled( result.gpio_mode_disabled );
					self.printing( result.printing );
					
				},
				
			} );
			
		};

		self.onSettingsShown = function() {
			
			self.testSensorResult( "" );
			self.fetchState();
			
            // Check for broken settings:
			self.getSetting( [ "gpioMode", "pinInput", "powerInput" ] )
			.off( "change.fsensor" )
			.on( "change.fsensor", self.checkWarningPullUp );
			
			self.getSetting( "gpioMode" )
			.trigger( "change.fsensor" );
			
		};
		
		self.onSettingsHidden = function() {
			
			$.ajax( {
				url:         "/api/plugin/emergencystopreloaded",
				type:        "post",
				dataType:    "json",
				contentType: "application/json",
				headers:     { "X-Api-Key": UI_API_KEY },
					
				data: JSON.stringify( { command: "exitSettings" } ),
						
			} )
			
		};
	
	}

    // This is how our plugin registers itself with the application, by adding some configuration
    // information to the global variable OCTOPRINT_VIEWMODELS
	ADDITIONAL_VIEWMODELS.push( {
		
		construct:    EmergencyStopReloadedViewModel,
		dependencies: [ "settingsViewModel" ],
		elements:     [ "#settings_plugin_emergencystopreloaded" ],
		
	} );

} );
