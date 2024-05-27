
#goto openweathermap.org and get an api key.
#setup main.plugins.weather2pwn.api_key = "apikey"
#if you lack a gps or don't want to use itsetup main.plugins.weather2pwn..getbycity = "true"
# also for getbycity set main.plugins.weather2pwn.city_id = "city id on openweathermap.org"
#depends on gpsd and clients installed
 
import socket, json, requests, logging, os, toml, time
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.plugins as plugins

class Weather2Pwn(plugins.Plugin):
    __author__ = 'NeonLightning'
    __version__ = '1.0.2'
    __license__ = 'GPL3'
    __description__ = 'Weather display from location data'

    def _is_internet_available(self):
        try:
            socket.create_connection(("www.google.com", 80))
            return True
        except OSError:
            return False

    def get_weather_by_city_id(self):
        try:
            base_url = "http://api.openweathermap.org/data/2.5/weather"
            complete_url = f"{base_url}?id={self.city_id}&appid={self.api_key}&units=metric&lang=en"
            logging.debug(f"[Weather2Pwn] Weather API URL: {complete_url}")
            response = requests.get(complete_url)
            logging.debug(f"[Weather2Pwn] Weather API Response: {response.text}")
            if response.status_code == 200:
                data = response.json()
                logging.debug(f"[Weather2Pwn] Weather data for city ID {self.city_id} obtained.")
                return data
            else:
                logging.error(f"[Weather2Pwn] Error fetching weather data: {response.status_code}")
                return None
        except Exception as e:
            logging.error(f"[Weather2Pwn] Exception fetching weather data: {e}")
            return None
    
    def get_gps_coordinates(self):
        try:
            gpsd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            gpsd_socket.connect(('localhost', 2947))
            gpsd_socket.sendall(b'?WATCH={"enable":true,"json":true}')

            while True:
                data = gpsd_socket.recv(4096).decode('utf-8')
                for line in data.splitlines():
                    try:
                        report = json.loads(line)
                        if report['class'] == 'TPV' and 'lat' in report and 'lon' in report:
                            return report['lat'], report['lon']
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logging.error(f"[Weather2Pwn] Error getting GPS coordinates: {e}")
            return None, None

    def get_weather_by_gps(self, lat, lon, api_key, units="metric", lang="en"):
        try:
            base_url = "http://api.openweathermap.org/data/2.5/weather"
            complete_url = f"{base_url}?lat={lat}&lon={lon}&units={units}&lang={lang}&appid={api_key}"
            response = requests.get(complete_url)
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"[Weather2Pwn] Error fetching weather data: {response.status_code}")
                return None
        except Exception as e:
            logging.error(f"[Weather2Pwn] Exception fetching weather data: {e}")
            return None
        
    def on_ready(self, agent):
        if self._is_internet_available():
            logging.debug("[Weather2Pwn] Internet is available on load.")
            if self.getbycity:
                logging.debug("[Weather2Pwn] bycity")
                self.weather_data = self.get_weather_by_city_id()
            else:
                logging.debug("[Weather2Pwn] bygps")
                latitude, longitude = self.get_gps_coordinates()
                if latitude and longitude:
                    logging.debug(f"[Weather2Pwn] GPS coordinates obtained: {latitude}, {longitude}")
                    self.weather_data = self.get_weather_by_gps(latitude, longitude, self.api_key)
                    if self.weather_data:
                        with open('/tmp/weather2pwn_data.json', 'w') as f:
                            json.dump(self.weather_data, f)
                        logging.info("[Weather2Pwn] Weather data obtained successfully.")
                    else:
                        logging.error("[Weather2Pwn] Failed to fetch weather data.")
                else:
                    logging.error("[Weather2Pwn] GPS coordinates not obtained.")
            
    def on_loaded(self):
        self.internet_counter = 0
        if os.path.exists('/tmp/weather2pwn_data.json'):
            os.remove('/tmp/weather2pwn_data.json')
            logging.debug("[Weather2Pwn] Existing weather data JSON file deleted.")
        self.api_key = self.options.get('api_key', '')
        self.getbycity = self.options.get('getbycity', 'False')
        self.city_id = self.options.get('city_id', '')
        self.last_fetch_time = 3599
        self.fetch_interval = 3600 
        logging.info("[Weather2Pwn] Plugin loaded.")

    def on_agent(self, agent) -> None:
        self.on_internet_available(self, agent)
        
    def on_ui_setup(self, ui):
        pos1 = (150, 37)
        ui.add_element('city', LabeledValue(color=BLACK, label='', value='',
                                            position=pos1,
                                            label_font=fonts.Small, text_font=fonts.Small))
        pos2 = (155, 47)
        ui.add_element('feels_like', LabeledValue(color=BLACK, label='Temp:', value='',
                                                position=pos2,
                                                label_font=fonts.Small, text_font=fonts.Small))
        pos3 = (155, 57)
        ui.add_element('weather', LabeledValue(color=BLACK, label='Sky :', value='',
                                                position=pos3,
                                                label_font=fonts.Small, text_font=fonts.Small))

    def on_internet_available(self, agent):
        current_time = time.time()
        if current_time - self.last_fetch_time >= self.fetch_interval:
            if self.getbycity:
                logging.debug("[Weather2Pwn] bycity")
                self.weather_data = self.get_weather_by_city_id()
            else:
                logging.debug("[Weather2Pwn] bygps")
                latitude, longitude = self.get_gps_coordinates()
                if latitude and longitude:
                    logging.debug(f"[Weather2Pwn] GPS coordinates obtained: {latitude}, {longitude}")
                    self.weather_data = self.get_weather_by_gps(latitude, longitude, self.api_key)
                    if self.weather_data:
                        with open('/tmp/weather2pwn_data.json', 'w') as f:
                            json.dump(self.weather_data, f)
                        logging.info("[Weather2Pwn] Weather data obtained successfully.")
                    else:
                        logging.error("[Weather2Pwn] Failed to fetch weather data.")
                else:
                    logging.error("[Weather2Pwn] GPS coordinates not obtained.")
            self.last_fetch_time = current_time
        else:
            logging.debug("[Weather2Pwn] Internet is available but not fetching weather data this time.")
 
    def on_ui_update(self, ui):
        if self._is_internet_available():
            if os.path.exists('/tmp/weather2pwn_data.json'):
                with open('/tmp/weather2pwn_data.json', 'r') as f:
                    self.weather_data = json.load(f)
            if self.weather_data:
                if "name" in self.weather_data:
                    city_name = self.weather_data["name"]
                    logging.debug(f"[Weather2Pwn] City: {city_name}")
                    ui.set('city', f"{city_name}")
                if "main" in self.weather_data and "feels_like" in self.weather_data["main"]:
                    feels_like = self.weather_data["main"]["feels_like"]
                    logging.debug(f"[Weather2Pwn] Feels Like: {feels_like}")
                    ui.set('feels_like', f"{feels_like}°C")
                if "weather" in self.weather_data and len(self.weather_data["weather"]) > 0:
                    main_weather = self.weather_data["weather"][0]["main"]
                    logging.debug(f"[Weather2Pwn] Weather: {main_weather}")
                    ui.set('weather', f"{main_weather}")
                
    def on_unload(self, ui):
        with ui._lock:
            for element in ['city', 'feels_like', 'weather']:
                try:
                    ui.remove_element(element)
                except KeyError:
                    pass
            logging.info("[Weather2Pwn] Unloaded")

if __name__ == "__main__":
    config_file = '/etc/pwnagotchi/config.toml'
    api_key = ''
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = toml.load(f)
            if 'weather2pwn' in config['main']['plugins']:
                api_key = config['main']['plugins']['weather2pwn'].get('api_key', '')
    plugin = Weather2Pwn()
    plugin.api_key = api_key
    plugin.on_ready(None)