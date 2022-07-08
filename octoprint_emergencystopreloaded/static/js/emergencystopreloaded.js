$( function() {
	
	function EmergencyStopReloadedViewModel( parameters ) {
		
		var self = this;
		
		self.validPinsBoard				= [ 3, 5, 7, 11, 13, 15, 19, 21, 23, 27, 29, 31, 33, 35, 37, 8, 10, 12, 16, 18, 22, 24, 26, 28, 32, 36, 38, 40 ];
		
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
			let	mode			= parseInt( self.getSetting( "gpioMode" ).val(), 10 ),
			
            // What pin is the sensor connected to:
				pin				= parseInt( self.getSetting( "pinInput" ).val(), 10 ),
			
            // What is the sensor connected to - ground or 3.3v:
				sensorWiring	= parseInt( self.getSetting( "powerInput" ).val(), 10 );

            // Show alerts
			if (
			
				sensorWiring == 1 && ( // 1 = 3.3v
				
					( mode == 10 && ( pin == 3 || pin == 5 ) )
					
                    ||
					
                    ( mode == 11 && ( pin == 2 || pin == 3 ) )
					
				)
				
			) {
				
				self.getSetting( "pullupwarn" )
				.removeClass( "hidden pulsAlert" )
				.addClass( "pulsAlert" );
				
			} else {
				
				self.getSetting( "pullupwarn" )
				.addClass( "hidden" )
				.removeClass( "pulsAlert" );
				
			}

            // Set max to right board type - 10 = Boardmode
			let showWarning = true;
			if ( mode == 10 ) {
				
				self.getSetting( "pinInput" ).attr( "max", 40 );
				
				if ( pin != 0 && $.inArray( pin, self.validPinsBoard ) == -1 ) {
					
					showWarning = false;
					
					self.getSetting( "badpin" )
					.removeClass( "hidden pulsAlert" )
					.addClass( "pulsAlert" );
					
				} else {
					
					self.getSetting( "badpin" )
					.addClass( "hidden" )
					.removeClass( "pulsAlert" );
					
				}
				
			} else self.getSetting( "pinInput" ).attr( "max", 27 );

            // High or low
			if ( self.getSetting( "pinInput" ).attr( "max" ) < pin || pin < 0 ) {
				
				self.getSetting( "badpin" )
				.removeClass( "hidden pulsAlert" )
				.addClass( "pulsAlert" );
				
			} else {
				
                // If the warning is not already shown then show it now:
				if ( showWarning ) {
					
					self.getSetting( "badpin" )
					.addClass( "hidden" )
					.removeClass( "pulsAlert" );
					
				}
				
			}
		
		};

		self.getDisabled = function( item ) {
			
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
			
			self.getDisabled();
			
            // Check for broken settings:
			self.getSetting( [ "gpioMode", "pinInput", "powerInput" ] )
			.off( "change.fsensor" )
			.on( "change.fsensor", self.checkWarningPullUp );
			
			self.getSetting( "gpioMode" )
			.trigger( "change.fsensor" );
			
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
