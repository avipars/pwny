# goto openweathermap.org and get an api key and cityid.
# gps requires gpsdeasy to be installed
#main.plugins.weather2pwn.enabled = true # enable plugin weather2pwn
#main.plugins.weather2pwn.log = False # log the weather data
#main.plugins.weather2pwn.cityid = "CITY_ID" # set the cityid
#main.plugins.weather2pwn.getbycity = false # get the weather data from gps or cityid by default(gps falls back to cityid if not available)
#main.plugins.weather2pwn.api_key = "API_KEY" # openweathermap.org api key
#main.plugins.weather2pwn.decimal = "true" # include 2 decimal places for the temperature
#main.plugins.weather2pwn.units = "c" or "f" to determine celsius or fahrenheit
#main.plugins.weather2pwn.displays = [ "city", "temp", "sky", ] # display these values on the screen

import socket, json, requests, logging, os, time, toml, subprocess, datetime
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.plugins as plugins

class Weather2Pwn(plugins.Plugin):
    __author__ = 'NeonLightning'
    __version__ = '2.1.1'
    __license__ = 'GPL3'
    __description__ = 'Weather display from gps data or city id, with optional logging'

    def __init__(self):
        self.config_path = '/etc/pwnagotchi/config.toml'
        self.check_and_update_config('main.plugins.weather2pwn.api_key', '""')
        self.check_and_update_config('main.plugins.weather2pwn.getbycity', 'false')
        self.check_and_update_config('main.plugins.weather2pwn.cityid', '""')
        self.check_and_update_config('main.plugins.weather2pwn.log', 'false')
        self.check_and_update_config('main.plugins.weather2pwn.decimal', 'true')
        self.check_and_update_config('main.plugins.weather2pwn.units', '"c"')
        self.check_and_update_config('main.plugins.weather2pwn.displays', '[ "city", "temp", "sky", ]')
        try:
            with open(self.config_path, 'r') as f:
                config = toml.load(f)
                self.displays = config['main']['plugins']['weather2pwn']['displays']
                self.units = config['main']['plugins']['weather2pwn']['units']
                self.decimal = config['main']['plugins']['weather2pwn']['decimal']
                self.decimal = self.decimal in [True, 'true', 'True']
                self.api_key = config['main']['plugins']['weather2pwn']['api_key']
                self.getbycity = config['main']['plugins']['weather2pwn']['getbycity']
                self.getbycity = self.getbycity in [True, 'true', 'True']
                self.city_id = config['main']['plugins']['weather2pwn']['cityid']
                self.weather_log = config['main']['plugins']['weather2pwn']['log']
                self.weather_log = self.weather_log in [True, 'true', 'True']
                self.language = config['main']['lang']
        except Exception as e:
            logging.exception(f'[Weather2Pwn] Error loading configuration: {e}')
        file_path = f'/root/weather/weather2pwn_tmp_data.json'
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                for line in f:
                    data = json.loads(line)
                    data_time = datetime.datetime.strptime(data['time'], "%Y-%m-%d %H:%M")
                    current_time = datetime.datetime.now()
                    time_diff = current_time - data_time
                    if abs(time_diff.total_seconds()) == 3600:
                        self.logged_long = data['lon']
                        self.logged_lat = data['lat']
                    else:
                        self.logged_lat, self.logged_long = 0, 0
        else:
            self.logged_lat, self.logged_long = 0, 0
        self.last_fetch_time = time.time()
        self.inetcount = 3
        self.fetch_interval = 1800
        self.weather_data = {}
        self.current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        self.readycheck = False
        self.running = False
        self.checkgps_time = 0
        self.ui_update_time = time.time()
        
    def on_ready(self, agent):
        self.readycheck = True
        time.sleep(5)
        self._update_weather()
        time.sleep(5)
        self.running = True
        logging.info("[Weather2Pwn] Ready")

    def _is_internet_available(self):
        try:
            socket.create_connection(("www.google.com", 80), timeout=3)
            return True
        except OSError:
            return False
        
    def ensure_gpsd_running(self):
        try:
            result = subprocess.run(['pgrep', '-x', 'gpsd'], stdout=subprocess.PIPE)
            if result.returncode != 0 or result.returncode != None:
                return True
            else:
                return False
        except Exception as e:
            logging.exception(f"[Weather2Pwn] Error ensuring gpsd is running: {e}")
            return False

    def get_weather_by_city_id(self, lang):
        try:
            base_url = "http://api.openweathermap.org/data/2.5/weather"
            complete_url = f"{base_url}?id={self.city_id}&appid={self.api_key}&units=metric&lang={lang}"
            response = requests.get(complete_url)
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                logging.error(f"[Weather2Pwn] Error fetching weather data: {response.status_code}")
                if os.path.exists('/tmp/weather2pwn_data.json'):
                    os.remove('/tmp/weather2pwn_data.json')
                return None
        except Exception as e:
            if os.path.exists('/tmp/weather2pwn_data.json'):
                os.remove('/tmp/weather2pwn_data.json')
            logging.error(f"[Weather2Pwn] Exception fetching weather data: {e}")
            return None

    def get_gps_coordinates(self):
        if not self.ensure_gpsd_running():
            return 0, 0
        else:
            try:
                gpsd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                gpsd_socket.connect(('localhost', 2947))
                gpsd_socket.sendall(b'?WATCH={"enable":true,"json":true}\n')
                time.sleep(2)
                data = gpsd_socket.recv(4096).decode('utf-8')
                for line in data.splitlines():
                    try:
                        report = json.loads(line)
                        if report['class'] == 'TPV' and 'lat' in report and 'lon' in report:
                            return report['lat'], report['lon']
                    except json.JSONDecodeError:
                        logging.warning('[Weather2Pwn] Failed to decode JSON response.')
                        return 0, 0
                logging.debug('[Weather2Pwn] No GPS data found.')
                return 0, 0
            except Exception as e:
                logging.exception(f"[Weather2Pwn] Error getting GPS coordinates: {e}")
                return 0, 0
            finally:
                gpsd_socket.close()

    def get_weather_by_gps(self, lat, lon, api_key, lang):
        try:
            base_url = "http://api.openweathermap.org/data/2.5/weather"
            complete_url = f"{base_url}?lat={lat}&lon={lon}&units=metric&lang={lang}&appid={api_key}"
            response = requests.get(complete_url)
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"[Weather2Pwn] Error fetching weather data: {response.status_code}")
                return None
        except Exception as e:
            logging.exception(f"[Weather2Pwn] Exception fetching weather data: {e}")
            return None

    def check_and_update_config(self, key, value):
        config_file = '/etc/pwnagotchi/config.toml'
        try:
            with open(config_file, 'r') as f:
                config_lines = f.readlines()
            key_found = False
            insert_index = -1
            for i, line in enumerate(config_lines):
                if 'main.plugins.weather2pwn.enabled' in line:
                    key_found = True
                    insert_index = i + 1
                    break
            key_found = False
            for line in config_lines:
                if key in line:
                    key_found = True
                    break
            if not key_found:
                config_lines.insert(insert_index, f"{key} = {value}\n")
                with open(config_file, 'w') as f:
                    f.writelines(config_lines)
                logging.info(f"[Weather2Pwn] Added {key} to the config file with value {value}")
        except Exception as e:
            logging.exception(f"[Weather2Pwn] Exception occurred while processing config file: {e}")

    def store_weather_data(self):
        if self.weather_log == True:
            self.current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            file_path = f'/root/weather/weather2pwn_data_{self.current_date}.json'
            directory = "/root/weather/"
            tmp_file_path = '/root/weather/weather2pwn_tmp_data.json'
            logging.info(f"[Weather2Pwn] Logging to {file_path}")
            tmp_data = {
                "time": time.strftime("%Y-%m-%d %H:%M"),
                "lon": self.weather_data.get('coord', {}).get('lon'),
                "lat": self.weather_data.get('coord', {}).get('lat')
            }
            data_to_store = {
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "weather_data": self.weather_data
            }
            try:
                os.makedirs(directory, exist_ok=True)
                with open(file_path, 'a') as f:
                    f.write(json.dumps(data_to_store) + '\n')
                logging.info("[Weather2Pwn] Weather data stored successfully.")
            except Exception as e:
                logging.exception(f"[Weather2Pwn] Error storing weather data: {e}")
            try:
                os.makedirs(directory, exist_ok=True)
                with open(tmp_file_path, 'w+') as f:
                    f.write(json.dumps(tmp_data) + '\n')
            except Exception as e:
                logging.exception(f"[Weather2Pwn] Error storing weather data location: {e}")
        else:
            pass

    def on_loaded(self):
        logging.info("[Weather2Pwn] loading")
        if os.path.exists('/tmp/weather2pwn_data.json'):
            os.remove('/tmp/weather2pwn_data.json')
        logging.info("[Weather2Pwn] Plugin loaded.")

    def on_agent(self, agent) -> None:
        self.on_internet_available(self, agent)

    def on_ui_setup(self, ui):
        if 'city' in self.displays:
            pos1 = (150, 37)
            ui.add_element('city', LabeledValue(color=BLACK, label='', value='',
                                                position=pos1,
                                                label_font=fonts.Small, text_font=fonts.Small))
        if 'temp' in self.displays:
            pos2 = (155, 47)
            ui.add_element('feels_like', LabeledValue(color=BLACK, label='Tmp:', value='',
                                                    position=pos2,
                                                    label_font=fonts.Small, text_font=fonts.Small))
        if 'sky' in self.displays:
            pos3 = (155, 57)
            ui.add_element('weather', LabeledValue(color=BLACK, label='Sky :', value='',
                                                    position=pos3,
                                                    label_font=fonts.Small, text_font=fonts.Small))

    def _update_weather(self):
        current_time = time.time()
        if (current_time - self.checkgps_time) >= (self.fetch_interval / 2):
            latitude, longitude = self.get_gps_coordinates()
            logging.debug(f"[Weather2Pwn] Latitude diff: {abs(self.logged_lat - latitude)}, Longitude diff: {abs(self.logged_long - longitude)}, inetcount: {self.inetcount}, last: {self.checkgps_time} current: {current_time} fetch: {self.fetch_interval} gpstime: {self.checkgps_time} diff: {current_time - self.checkgps_time}")
            self.checkgps_time = current_time
        if (self.readycheck or current_time - self.last_fetch_time >= self.fetch_interval or abs(self.logged_lat - latitude) >= 0.01 or abs(self.logged_long - longitude) > 0.01):
            if abs(self.logged_lat - latitude) >= 0.005 or abs(self.logged_long - longitude) >= 0.005 or (current_time - self.last_fetch_time >= self.fetch_interval):
                self.inetcount += 1
            try:
                if abs(self.logged_lat - latitude) >= 0.01 or abs(self.logged_long - longitude) >= 0.01 or self.inetcount >= 2:
                    if self.getbycity == False:
                        latitude, longitude = self.get_gps_coordinates()
                        if latitude != 0 and longitude != 0:
                            logging.info(f"[Weather2Pwn] GPS data found. {latitude}, {longitude}")
                            self.weather_data = self.get_weather_by_gps(latitude, longitude, self.api_key, self.language)
                            self.weather_data["name"] = self.weather_data["name"] + " *GPS*"
                            logging.info("[Weather2Pwn] weather setup by gps")
                            self.last_fetch_time = current_time
                        else:
                            logging.info(f"[Weather2Pwn] GPS data not found.")
                            self.weather_data = self.get_weather_by_city_id(self.language)
                            logging.info("[Weather2Pwn] weather setup by city")
                            self.last_fetch_time = current_time
                    else:
                        self.weather_data = self.get_weather_by_city_id(self.language)
                        logging.info("[Weather2Pwn] weather setup by city")
                        self.last_fetch_time = current_time
                    if os.path.exists('/tmp/weather2pwn_data.json'):
                        with open('/tmp/weather2pwn_data.json', 'r') as f:
                            self.weather_data = json.load(f)
                    if self.weather_data:
                        self.store_weather_data()
                        self.logged_lat = latitude
                        self.logged_long = longitude
                        self.inetcount = 0
            except Exception as e:
                logging.exception(f"[Weather2pwn] An error occurred {e}")
                logging.exception(f"[Weather2pwn] An error occurred2 {self.weather_data}")
            self.readycheck = False

    def on_wait(self, agent, t):
        if self.readycheck and self.weather_data:
            logging.info('[Weather2Pwn] skipping first check')
        else:
            current_time = time.time()
            if current_time - self.ui_update_time >= (self.fetch_interval / 4):
                logging.debug(f"[Weather2Pwn] wait check inetcount: {self.inetcount}, last: {self.last_fetch_time} current: {current_time} fetch: {self.ui_update_time} diff: {current_time - self.ui_update_time}")
                self.ui_update_time = current_time
                self._update_weather()
                self.readycheck = False
                
    def on_ui_update(self, ui):
        if self.running:
            if self._is_internet_available():
                if os.path.exists('/tmp/weather2pwn_data.json'):
                    with open('/tmp/weather2pwn_data.json', 'r') as f:
                        self.weather_data = json.load(f)
                if self.weather_data:
                    if "name" in self.weather_data:
                        city_name = self.weather_data["name"]
                        if 'city' in self.displays:
                            ui.set('city', f"{city_name}")
                    if "main" in self.weather_data and "feels_like" in self.weather_data["main"]:
                        feels_like = self.weather_data["main"]["feels_like"]
                        if 'temp' in self.displays:
                            if not self.decimal:
                                feels_like = round(feels_like)
                            if self.units == "c":
                                ui.set('feels_like', f"{feels_like}°C")
                            elif self.units == "f":
                                feels_like = (feels_like * 9/5) + 32
                                feels_like = round(feels_like)
                                ui.set('feels_like', f"{feels_like}°F")
                    if "weather" in self.weather_data and len(self.weather_data["weather"]) > 0:
                        main_weather = self.weather_data["weather"][0]["main"]
                        if 'sky' in self.displays:
                            ui.set('weather', f"{main_weather}")
            else:
                current_time = time.time()
                if current_time - self.last_fetch_time >= self.fetch_interval:
                    if 'city' in self.displays:
                        ui.set('city', 'No Network')
                    if 'temp' in self.displays:
                        ui.set('feels_like', '')
                    if 'sky' in self.displays:
                        ui.set('weather', '')

    def on_unload(self, ui):
        self.running = False
        with ui._lock:
            for element in ['city', 'feels_like', 'weather']:
                try:
                    ui.remove_element(element)
                except KeyError:
                    pass
            logging.info("[Weather2Pwn] Unloaded")