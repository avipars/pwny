import os, logging, re, subprocess, pwnagotchi, toml, json, requests
from io import TextIOWrapper
from pwnagotchi import plugins, config
import pwnagotchi.ui.components as components
import pwnagotchi.ui.view as view
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.plugins as plugins

class WeatherForecast(plugins.Plugin):
    __author__ = 'NeonLightning'
    __version__ = '0.3.0'
    __license__ = 'GPL3'
    __description__ = 'A plugin that displays the weather forecast on the pwnagotchi screen.'
    __name__ = 'WeatherForecast'

    def on_loaded(self):
        self.api_key = config['main']['plugins']['weather']['api_key']
        self.location = config['main']['plugins']['weather']['location']
        logging.info("Weather Forecast Plugin loaded.")

    def on_ui_setup(self, ui):
        ui.add_element('feels', components.LabeledValue(color=view.BLACK, label='', value='',
                                                                   position=(90, 85), label_font=fonts.Small, text_font=fonts.Small))
        ui.add_element('main', components.LabeledValue(color=view.BLACK, label='', value='',
                                                            position=(90, 100), label_font=fonts.Small, text_font=fonts.Small))
    def on_ui_update(self, ui):
        weather_url = f"https://api.openweathermap.org/data/2.5/weather?q={self.location}&units=metric&appid={self.api_key}"
        try:
            weather_response = requests.get(weather_url).json()
            current_temp = weather_response['main']['feels_like']
            description = weather_response['weather'][0]['description']
            ui.set('feels', f"TEMP:{current_temp}°C")
            ui.set('main', f"WTHR:{description}")
        except:
            ui.set('feels', "Temp:NA")

    def on_unload(self, ui):
        with ui._lock:
            ui.remove_element('feels')
            ui.remove_element('main')
            logging.info("Weather Plugin unloaded")