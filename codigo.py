import random
import flet as ft
import flet_map as fm
import requests
import csv
import math
import os
import json
import asyncio
import tracemalloc
from datetime import datetime

tracemalloc.start()

# Reads countries.json
base_path = os.path.dirname(os.path.abspath(__file__))

countries_json_path = os.path.join(base_path, "countries.json")

SETTINGS_PATH = os.path.join(base_path, "settings.json")

with open("currency.json", "r", encoding="utf-8-sig") as f:
    CURRENCY = json.load(f)

with open(countries_json_path, "r", encoding="utf-8-sig") as f:
    country_translations = json.load(f)

with open("country_language.json", "r", encoding="utf-8-sig") as f:
    COUNTRY_LANGUAGES = json.load(f)

# Reads languages.json
with open("languages.json", "r", encoding="utf-8-sig") as f:
    LANGUAGES = json.load(f)
 
EPSILON = 1e-10

# Harvesine method
def haversine(lat1, lon1, lat2, lon2):
    R = 6371 # Earth radius
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R*c

def interpolate_great_circle(lat1, lon1, lat2, lon2, steps):

    if lat1 == lat2 and lon1 == lon2:
        return [(lat1, lon1)]

    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    d = 2 * math.asin(math.sqrt(
        math.sin((lat2-lat1)/2)**2 +
        math.cos(lat1) * math.cos(lat2) *
        math.sin((lon2 - lon1)/2)**2
    ))

    coordinates = []
    for i in range(steps + 1):
        f = i / steps

        if abs(d) < EPSILON:
            A = 1.0
            B = 0.0
        else:
            sin_d = math.sin(d)
            A = math.sin((1 - f) * d) * sin_d
            B = math.sin(f * d) / sin_d

        x = A * math.cos(lat1) * math.cos(lon1) + B * math.cos(lat2) * math.cos(lon2)
        y = A * math.cos(lat1) * math.sin(lon1) + B * math.cos(lat2) * math.sin(lon2)
        z = A * math.sin(lat1) + B * math.sin(lat2)

        new_lat = math.atan2(z, math.sqrt(x*x + y*y))
        new_lon = math.atan2(y, x)

        coordinates.append((math.degrees(new_lat), math.degrees(new_lon)))

    return coordinates

def calculate_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

    return math.atan2(x, y)

def get_temperature(lat, lon):
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current_weather=true"
        )

        r=requests.get(url)
        data=r.json()

        if "current_weather" in data:
            temp = data["current_weather"]["temperature"]
            weather_code = data["current_weather"]["weathercode"]
            return temp, weather_code
       
        return None, None
       
    except:
        return None, None
   
def get_local_time(lat, lon):
    try:
        url = f"https://www.timeapi.io/api/TimeZone/coordinate?latitude={lat}&longitude={lon}"
        r = requests.get(url).json()

        if "currentLocalTime" in r:
            raw_time = r["currentLocalTime"]

            dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))

            return dt.strftime("%d/%m %H:%M")
       
        return None
    except:
        return None
   
def get_usd_exchange_rate(currency_code):
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        r = requests.get(url).json()
        return r["rates"].get(currency_code)
    except:
        return None
   
def load_settings():
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings(settings):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

def main(page: ft.Page):
    page.title = "Fly World - Flight calculator"
    page.bgcolor = ft.Colors.ORANGE_300

    # Loading screen
    def show_splash():
        page.controls.clear()

        splash_image = ft.Image(src="Fly_World_plane.png", width=300, height=300)
        start_button = ft.Button(
            "Start button", on_click=lambda e: show_home()
        )
        splash_content = ft.Column(
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                splash_image,
                ft.Text("Welcome", size=24),
                start_button
            ]
        )
        page.add(splash_content)
        page.update()

    # Reads the csv archive
    base_path = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_path, "coordinates-Sheet.csv")
   
    countries = {}

    with open(csv_path, encoding="utf-8-sig") as csvfile:
        reader = csv.reader(csvfile)

        headers = next(reader)
        headers = [h.replace('"', '').replace(',', '').strip().lower() for h in headers]

        for row in reader:
            if len(row) != len(headers):
                continue

            data = dict(zip(headers, row))
            data = {k: v.strip() for k, v in data.items()}

            country = data.get("country")
            lat = data.get("lat")
            lon = data.get("lon")

            if country and lat and lon:
                try:
                    countries[country] = (float(lat), float(lon))
                except ValueError:
                    pass

    selected_origin = {"value" : None}

    selected_destiny = {"value" : None}

    selected_class = {"value" : None}

    selected_season = {"value" : None}
   
    selected_airline = {"value": None}

    settings = load_settings()

    #Main temperature
    current_temperature = {"value": settings.get("temperature_unit", "°C")}

    # Main language
    current_language = {"value": settings.get("language", "en")}

    # Main currency
    current_currency = {"value": settings.get("currency", "USD")}

    # Main distance unit
    current_distance_unit = {"value": settings.get("distance_unit", "km")}

    current_weather = {"value": None}

    current_temp = {"value": None}

    current_index = {"value": 0}

    airlines = {
        "low-cost": {
            "label": {
                "en": "Low-cost",
                "es": "Bajo costo",
                "fr": "Faible coût",
                "it": "Basso costo",
                "de": "Niedrige Kosten",
                "ja": "低コスト",
                "ch": "低成本",
                "ar": "تكلفة منخفضة"
            },
            "price_multiplier": 0.8,
            "speed": 850
        },
        "standard": {
            "label": {
                "en": "Standard",
                "es": "Estándar",
                "fr": "Standard",
                "it": "Standard",
                "de": "Standard",
                "ja": "標準",
                "ch": "标准",
                "ar": "معيار"
            },
            "price_multiplier": 1,
            "speed": 900
        },
        "premium": {
            "label": {
                "en": "Premium",
                "es": "Premium",
                "fr": "Premium",
                "it": "Premium",
                "de": "Prämie",
                "ja": "プレミアム",
                "ch": "优质的",
                "ar": "غالي"
            },
            "price_multiplier": 1.3,
            "speed": 950
        }
    }
   
    pending_search = {"origin": None, "destiny": None, "class":None, "season": None, "airline": None}
    search_history = []
    MAX_HISTORY = 10

    # Def translated words
    def get_translated_country(key):
        lang = current_language["value"]
        return country_translations.get(lang, {}).get(key, key)
   
    def translate_class(value):
        lang = LANGUAGES[current_language["value"]]
        mapping = {
            "Economic": lang["economic"],
            "First class": lang["first_class"]
        }
        return mapping.get(value, value)
   
    def translate_season(value):
        lang = LANGUAGES[current_language["value"]]
        mapping = {
            "Low season": lang["low_season"],
            "High season": lang["high_season"]
        }
        return mapping.get(value, value)

    
    def get_tourist_places(lat, lon, api_key, limit=5):
        url = f"https://api.geoapify.com/v2/places?categories=tourism.sights&filter=circle:{lon},{lat},10000&limit=5&apiKey=51b26f734313447fa787b92fedd9ee1a"
        params = {
            "categories": "tourism.sights",
            "filter": f"circle:{lon},{lat},10000",
            5: "limit",
            "51b26f734313447fa787b92fedd9ee1a": api_key
        }


        r = requests.get(url, params=params)
        print(r.json())
        if r.status_code != 200:
            return []
        
        data = r.json()
        places = []

        for f in data.get("features", []):
            name = f["properties"].get("name")
            if name:
                places.append(name)

        return places

     # Change language
    def change_language(e):
        current_language["value"] = e.control.value
        settings["language"] = e.control.value
        save_settings(settings)
        update_navigation_labels()
        page.snack_bar = ft.SnackBar(
            ft.Text(f"Language changed to {e.control.value.upper()}")
        )
        page.snack_bar.open = True
        page.update()

    # Change currency
    def change_currency(e):
        current_currency["value"] = e.control.value
        settings["currency"] = e.control.value
        save_settings(settings)
        page.snack_bar = ft.SnackBar(ft.Text(f"Currency changed to {e.control.value}"))
        page.snack_bar.open = True
        page.update()
       
    def change_distance_unit(e):
        current_distance_unit["value"] = e.control.value
        settings["distance_unit"] = e.control.value
        save_settings(settings)
        page.snack_bar = ft.SnackBar(
            ft.Text(f"Distance unit changed to {e.control.value}")
        )
        page.snack_bar.open = True
        page.update()

    # Change the distance accordind to the selected unit
    def convert_distance(distance_km):
        if current_distance_unit["value"] == "miles":
            return distance_km * 0.621371, "mi"
        return distance_km, "km"

    def change_temperature(e):
        current_temperature["value"] = e.control.value
        settings["temperature_unit"] = e.control.value
        save_settings(settings)
        page.snack_bar = ft.SnackBar(
            ft.Text(f"Temperature unit changed to {e.control.value}")
        )
        page.snack_bar.open = True
        page.update()
   
    def show_search_history():
        page.controls.clear()
       
        back_button = ft.IconButton(
            ft.Icons.CLOSE,
            tooltip=LANGUAGES[current_language["value"]]["search_history"],
            on_click=lambda e: show_home()
        )
       
        history_buttons = []
        for item in search_history:
            btn = ft.Button(
                f"{item['origin']} → {item['destiny']}",
                on_click=lambda e, orig=item["origin"], dest=item["destiny"], cla=item["class"], sea=item["season"], air=item["airline"]: load_search(orig, dest, cla, sea, air)
            )
            history_buttons.append(btn)

        page.add(
            ft.Row([back_button, ft.Text(
                f"{LANGUAGES[current_language['value']]['search_history']}", size=22, weight=ft.FontWeight.BOLD)]),
                ft.Column(history_buttons, scroll="AUTO")
        )
        page.update()
       
        def load_search(origin_val, destiny_val, class_val, season_val, airline_val):
            pending_search["origin"] = origin_val
            pending_search["destiny"] = destiny_val
            pending_search["class"] = class_val
            pending_search["season"] = season_val
            pending_search["airline"] = airline_val

            show_home()
            if calculate_fn["fn"]:
                calculate_fn["fn"](None)

    # Resources of the map
    marker_layer_ref = ft.Ref[fm.MarkerLayer]()
    circle_layer_ref = ft.Ref[fm.CircleLayer]()
    map = ft.Ref[fm.Map]()
    buscador = ft.Ref[ft.TextField]()
    navigation_bar_ref = ft.Ref[ft.NavigationBar]()
    mini_map_ref = ft.Ref[fm.Map]()
    mini_marker_layer_ref = ft.Ref[fm.MarkerLayer]()
    mini_polyline_layer_ref = ft.Ref[fm.PolylineLayer]()
    origin_ref = ft.Ref[ft.Dropdown]()
    destiny_ref = ft.Ref[ft.Dropdown]()
    class_ref = ft.Ref[ft.Dropdown]()
    season_ref = ft.Ref[ft.Dropdown]()
    airline_ref = ft.Ref[ft.Dropdown]()
    calculate_fn = {"fn": None}

    # Search place
    def buscar_lugar(e):
        query = buscador.current.value.strip()
        if not query:
            return
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {"q": query, "format": "json", "limit": 1}
            headers = {"User-Agent": "WorldAirApp"}
            response = requests.get(url, params=params, headers=headers)
            data = response.json()

            if not data:
                page.snack_bar = ft.SnackBar(
                    ft.Text(LANGUAGES[current_language["value"]]["place_not_found"])
                )
                page.snack_bar.open = True
                page.update()
                return
                       
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])

            map.current.center = fm.MapLatitudeLongitude(lat, lon)
            map.current.zoom = 10

            marker_layer_ref.current.markers.append(
                fm.Marker(
                    content=ft.Icon(ft.Icons.LOCATION_ON, color=ft.Colors.RED),
                    coordinates=fm.MapLatitudeLongitude(lat, lon),
                )
            )

            page.update()

        except Exception as ex:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"{LANGUAGES[current_language['value']]['error_search']}: {ex}")
            )
            page.snack_bar.open = True
            page.update()

    # Clean map
    def limpiar_mapa(e):
        marker_layer_ref.current.markers.clear()
        circle_layer_ref.current.circles.clear()
        page.snack_bar = ft.SnackBar(
            ft.Text(LANGUAGES[current_language["value"]]["cleaned_map"])
        )
        page.snack_bar.open = True
        page.update()

    # Tap and hold markers
    def handle_tap(e: fm.MapEvent):
        if e.name == "tap":
            marker = fm.Marker(
                content=ft.Icon(ft.Icons.LOCATION_ON, color=ft.Colors.random()),
                coordinates=e.coordinates,
            )

            marker_layer_ref.current.markers.append(marker)
            page.update()

        elif e.name == "long_press":
            circle_layer_ref.current.circles.append(
                fm.CircleMarker(
                    radius=random.randint(5, 10),
                    coordinates=e.coordinates,
                    color=ft.Colors.random(),
                    border_color=ft.Colors.random(),
                    border_stroke_width=4,
                )
            )

        page.update()

    # Index
    def on_navigation_change(e):
        if e.control.selected_index == 0:
            show_home()
        elif e.control.selected_index == 1:
            show_map()
        elif e.control.selected_index == 2:
            show_destiny_info()
        elif e.control.selected_index == 3:
            show_settings()

    # Update index language
    def update_navigation_labels():
        lang = LANGUAGES[current_language["value"]]
        navigation_bar_ref.current.destinations = [
            ft.NavigationBarDestination(icon=ft.Icons.HOME, label=lang["nav_home"]),
            ft.NavigationBarDestination(icon=ft.Icons.MAP, label=lang["nav_map"]),
            ft.NavigationBarDestination(icon=ft.Icons.VIDEOGAME_ASSET, label=lang["nav_destiny_info"]),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS, label=lang["nav_settings"]),
        ]
        page.update()

    # Navigation bar
    navigation_bar = ft.NavigationBar(
        ref=navigation_bar_ref,
        selected_index=0,
        on_change=on_navigation_change,
        bgcolor=ft.Colors.ORANGE_200,
        indicator_color=ft.Colors.AMBER,
    )

    # Destinations of navigation
    def show_home():
        current_index["value"] = 0
        global last_width
        last_width = page.width
        _build_home_layout()

    def _build_home_layout():
        page.controls.clear()
        page.add(navigation_bar)

        # Mini map
        mini_map = fm.Map(
            ref=mini_map_ref,
            height=250 if page.width < 700 else 300,
            width=page.width if page.width < 700 else 500,
            initial_center=fm.MapLatitudeLongitude(20, 0),
            initial_zoom=2,
            interaction_configuration=fm.InteractionConfiguration(
                flags=fm.InteractionFlag.ALL
            ),
            layers=[
                fm.TileLayer(url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png"),
                fm.MarkerLayer(ref=mini_marker_layer_ref, markers=[]),
                fm.PolylineLayer(ref=mini_polyline_layer_ref, polylines=[])
            ],
        )
        lang=LANGUAGES[current_language["value"]]

        # Dropdowns
        class1 = ft.Dropdown(
            ref=class_ref,
            label=lang["flight_class"],
            value = selected_class["value"],
            options=[
                ft.dropdown.Option("Economic", lang["economic"]),
                ft.dropdown.Option("First class", lang["first_class"])
            ],
            width=250,
        )
        class1.on_change=lambda e: selected_class.update({"value": e.control.value})

        season = ft.Dropdown(
            ref=season_ref,
            label=lang["season"],
            value = selected_season["value"],
            options=[
                ft.dropdown.Option("Low season", lang["low_season"]),
                ft.dropdown.Option("High season", lang["high_season"])
            ],
            width=250,
        )
        season.on_change=lambda e: selected_season.update({"value": e.control.value})

        origin = ft.Dropdown(
            ref = origin_ref,
            label=lang["origin_country"],
            value = selected_origin["value"],
            options=[ft.dropdown.Option(key=c, text=get_translated_country(c))
                     for c in countries.keys()
            ],
            width=250,
        )
        origin.on_change=lambda e: selected_origin.update({"value": e.control.value})

        destiny = ft.Dropdown(
            ref = destiny_ref,
            label=lang["destiny_country"],
            value = selected_destiny["value"],
            options=[ft.dropdown.Option(key=c, text=get_translated_country(c))
                     for c in countries.keys()
            ],
            width=250,
        )
        destiny.on_change=lambda e: selected_destiny.update({"value": e.control.value})

        airline = ft.Dropdown(
            ref=airline_ref,
            label = lang["airline"],
            value = selected_airline["value"],
            options=[
                ft.dropdown.Option(
                    key=k,
                    text=airlines[k]["label"].get(current_language["value"], k)
                )
                for k in airlines.keys()  
            ],
            width=250,
        )
        airline.on_change=lambda e: selected_airline.update({"value": e.control.value})

        result = ft.Text(value="", size=18, weight=ft.FontWeight.BOLD)
       
        history_button = ft.Button(
            f"{lang['search_history']}",
            on_click=lambda e: show_search_history()
        )

        # Flight calculation
        def calcular(e=None):
            origin_value = origin_ref.current.value
            destiny_value = destiny_ref.current.value
            class_value = class_ref.current.value
            season_value = season_ref.current.value
            airline_value = airline_ref.current.value
            if not (
                origin_value
                and  destiny_value
                and class_value
                and season_value
                and airline_value
            ):
                result.value = lang["please"]
                page.update()
                return
           
            selected_origin["value"] = origin_value
            selected_destiny["value"] = destiny_value
            selected_class["value"] = class_value
            selected_season["value"] = season_value
            selected_airline["value"] = airline_value
                   
            lat1, lon1 = countries[origin_value]
            lat2, lon2 = countries[destiny_value]
            distance = haversine(lat1, lon1, lat2, lon2)

            # Base price per km
            price_km = 0.15
            price = distance * price_km
               
            # Adjust per class
            if class1.value == "First class":
                price *= 2
               
            # Adjust per season
            if season.value == "High season":
                price *= 1.5

            airline_data = airlines[airline_value]
            price *= airline_data["price_multiplier"]
            # Currency changes
            currency_rates = {
                "USD": 1,
                "EUR": 0.93,
                "GBP": 0.79,
                "CHF": 0.90,
                "JPY": 150
            }

            currency_symbols = {
                "USD": "$",
                "EUR": "€",
                "GBP": "£",
                "CHF": "Fr.",
                "JPY": "¥"
            }

            selected_currency = current_currency["value"]
            rate = currency_rates[selected_currency]
            symbol = currency_symbols[selected_currency]
            converted_price = price * rate

            # Determine type of flight and duration
            airline = airlines[airline_value]
            airplane_speed = airline["speed"]
            flight_time = distance / airplane_speed
            extra_time = 0
            flight_type = ""

            if distance < 5000:
                flight_type = lang["direct_flight"]
            elif distance < 10000:
                flight_type = lang["flight_with_stopover"]
                extra_time = 2 # Extra time for waiting the next flight
            else:
                flight_type = lang["flight_with_many_stopovers"]
                extra_time = 4 # Extra time for waiting multiple stopovers

            total_duration = flight_time + extra_time

            # Duration in hours and minutes
            hours = int(total_duration)
            minutes = int((total_duration-hours) * 60)

            dist, unit = convert_distance(distance)

            result.value = (
                f"{lang['flight_from'].format(origin=origin.value, destiny=destiny.value)}\n"
                f"{flight_type}\n"
                f"{lang['airline']}: {airlines[airline_value]['label'][current_language['value']]}\n"
                f"{lang['distance'].format(distance=f'{dist:1,.1f} {unit}')}\n"
                f"{lang['estimated_duration'].format(hours=hours, minutes=minutes)}\n"
                f"{lang['estimated_price']} {symbol}{converted_price:,.2f} {selected_currency}"
            )
            page.update()

            mini_marker_layer_ref.current.markers.clear()
            mini_polyline_layer_ref.current.polylines.clear()
           
            # Mini map resources
            mini_marker_layer_ref.current.markers.append(
                fm.Marker(
                    content=ft.Icon(ft.Icons.LOCATION_ON, color=ft.Colors.GREEN),
                    coordinates=fm.MapLatitudeLongitude(lat1, lon1),
                )
            )
            mini_marker_layer_ref.current.markers.append(
                fm.Marker(
                    content=ft.Icon(ft.Icons.FLAG, color=ft.Colors.RED),
                    coordinates=fm.MapLatitudeLongitude(lat2, lon2),
                )
            )

            curve_coordinates = interpolate_great_circle(lat1, lon1, lat2, lon2, 150)

            poly_coordinates = [
                fm.MapLatitudeLongitude(lat, lon) for lat, lon in curve_coordinates
            ]

            mini_polyline_layer_ref.current.polylines.clear()
            mini_polyline_layer_ref.current.polylines.append(
                fm.PolylineMarker(
                    coordinates=poly_coordinates,
                    color=ft.Colors.BLUE,
                    stroke_width=3,
                )
            )

            mid_index = len(curve_coordinates) // 2
            mid_lat, mid_lon = curve_coordinates[mid_index]

            mini_map_ref.current.center_on = fm.MapLatitudeLongitude(mid_lat, mid_lon)
            mini_map_ref.current.zoom_in = 2.5

            mini_map_ref.current.update()
            page.update()
           
            new_search = {
                "origin": origin_value,
                "destiny": destiny_value,
                "class": class_value,
                "season": season_value,
                "airline": airline_value
                }

            if new_search in search_history:
                search_history.remove(new_search)
            search_history.insert(0, new_search)

            if len(search_history) > MAX_HISTORY:
                search_history.pop()
       
            async def animate_airplane(lat1, lon1, lat2, lon2):

                    steps = 150
                    delay = 0.04

                    path = interpolate_great_circle(lat1, lon1, lat2, lon2, steps)

                    airplane_image = ft.Image(
                        src="airplane.png" if selected_airline["value"] == "premium" else "airplane(normal).png",
                        width=40,
                        height=40,
                        rotate=0,
                    )

                    airplane_marker = fm.Marker(
                        coordinates=fm.MapLatitudeLongitude(lat1, lon1),
                        content=airplane_image
                    )
           
                    mini_marker_layer_ref.current.markers.append(airplane_marker)
                    mini_map_ref.current.update()

                    await asyncio.sleep(delay)

                    for i in range(len(path) - 1):
                        lat, lon = path[i]
                        lat_next, lon_next = path[i + 1]

                        angle = calculate_bearing(lat, lon, lat_next, lon_next)
                        airplane_image.rotate = angle
                        if not mini_map_ref.current or mini_map_ref.current.page is None:
                            return
                        airplane_marker = fm.Marker(
                            coordinates=fm.MapLatitudeLongitude(lat, lon),
                            content=airplane_image
                        )
                        mini_marker_layer_ref.current.markers[-1] = airplane_marker
                        mini_marker_layer_ref.current.update()

                        await asyncio.sleep(delay)
           
            page.run_task(animate_airplane, lat1, lon1, lat2, lon2)

            page.update()
           
        button = ft.Button(
            LANGUAGES[current_language["value"]]["calculate"],
            on_click=calcular,
            icon=ft.Icons.FLIGHT_TAKEOFF
        )

        if page.width < 700:
            home_content = ft.Column(
                expand=True,
                spacing=20,
                scroll="AUTO",
                controls=[
                    ft.Text(lang["home_title"], size=26),
                    ft.Text(lang["calculator"], size=20, weight=ft.FontWeight.BOLD),
                    class1,
                    season,
                    origin,
                    destiny,
                    airline,
                    button,
                    result,
                    history_button,
                    mini_map
                ]
            )
       
        else:
            home_content = ft.Row(
                expand=True,
                spacing=20,
                controls=[
                    ft.Column(
                        scroll="AUTO",
                        expand=1,
                        controls=[
                            ft.Text(LANGUAGES[current_language["value"]]["home_title"], size=30),
                            ft.Text(LANGUAGES[current_language["value"]]["calculator"], size=22, weight=ft.FontWeight.BOLD),
                            origin,
                            destiny,
                            class1,
                            season,
                            airline,
                            button,
                            result,
                            history_button
                        ]    
                    ),
                    mini_map
                ]    
            )
        calculate_fn["fn"] = calcular
        page.add(home_content)

        if pending_search["origin"] and pending_search["destiny"] and pending_search["class"] and pending_search["season"] and pending_search["airline"]:
            origin_ref.current.value = pending_search["origin"]
            destiny_ref.current.value = pending_search["destiny"]
            class_ref.current.value = pending_search["class"]
            season_ref.current.value = pending_search["season"]
            airline_ref.current.value = pending_search["airline"]

            pending_search["origin"] = None
            pending_search["destiny"] = None
            pending_search["class"] = None
            pending_search["season"] = None
            pending_search["airline"] = None

            if calculate_fn["fn"]:
                calculate_fn["fn"](None)
        page.update()
     
    def handle_resize(e):
        global last_width
        if current_index["value"] != 0:
            return
       
        if abs(page.width - last_width) > 20:
            last_width = page.width
            _build_home_layout()
    page.on_resized = handle_resize

    def show_map():
        current_index["value"] = 1
        page.controls.clear()
        page.add(navigation_bar)

        # Seach bar
        search_bar = ft.Row(
            controls=[
                ft.TextField(
                    ref=buscador,
                    label=LANGUAGES[current_language["value"]]["search_label"],
                    expand=True,
                    on_submit=buscar_lugar,
                ),
                ft.IconButton(
                    ft.Icons.SEARCH,
                    on_click=buscar_lugar,
                    tooltip=LANGUAGES[current_language["value"]]["search_tooltip"],
                ),
                ft.IconButton(
                    ft.Icons.CLEANING_SERVICES_ROUNDED,
                    tooltip=LANGUAGES[current_language["value"]]["clean_tooltip"],
                    on_click=limpiar_mapa,
                ),
            ]
        )

        map_control = fm.Map(
            ref=map,
            expand=True,
            initial_center=fm.MapLatitudeLongitude(15, 10),
            initial_zoom=4.2,
            interaction_configuration=fm.InteractionConfiguration(
                flags=(
                    fm.InteractionFlag.DRAG,
                        fm.InteractionFlag.SCROLL_WHEEL_ZOOM,
                        fm.InteractionFlag.PINCH_ZOOM,
                ),
            ),
            on_tap=handle_tap,
            on_long_press=handle_tap,
            layers=[
                fm.TileLayer(
                    url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                ),
                fm.MarkerLayer(ref=marker_layer_ref, markers=[]),
                fm.CircleLayer(ref=circle_layer_ref, circles=[]),
            ],
        )

        page.add(
            ft.Text(LANGUAGES[current_language["value"]]["map_instructions"]),
            ft.Column([search_bar]),
            map_control,  
        )
        page.update()

    def show_destiny_info():
        current_index["value"] = 2
        page.controls.clear()
        page.add(navigation_bar)
        
        lang = LANGUAGES[current_language["value"]]

        places_column = ft.Column(
            scroll="AUTO",
            controls=[
                ft.Column([ft.Text(lang["popular_places"], size=18, weight=ft.FontWeight.BOLD)]),
                ft.Column([ft.Text("Loading places...")])
            ]
        )

        tips_column = ft.Column(
            scroll="AUTO",
            controls=[
                ft.Column([ft.Text(lang["travel_tips"], size=18, weight=ft.FontWeight.BOLD)]),
                ft.Column([ft.Text("Loading tips...")])
            ]
        )

        temp_text = ft.Text("Loading temperature...")
        weather_text_ui = ft.Text("Loading weather...")
        time_text = ft.Text("Loading local time...")
        currency_column = ft.Column([ft.Text("Loading currency...")])

        dest_language = COUNTRY_LANGUAGES.get(selected_destiny["value"], ["Unknown"])
       
        if ( selected_origin["value"] is None
            or selected_destiny["value"] is None
            or selected_class["value"] is None
            or selected_season["value"] is None
            or selected_airline["value"] is None
           
        ):
            page.add(
                ft.Column(
                    expand=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(
                            lang["do_home_calculation"],
                            size=20,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.RED
                        )
                    ]
                )
            )
            page.update()
            return

        left_column = ft.Column(
            expand=True,
            spacing=10,
            controls=[
                ft.Text(lang["left_title"], size=22, weight=ft.FontWeight.BOLD),
                ft.Text(f"{lang['origin_country']}: {get_translated_country(selected_origin['value'])}"),
                ft.Text(f"{lang['destiny_country']}: {get_translated_country(selected_destiny['value'])}"),
                ft.Text(f"{lang['flight_class']}: {translate_class(selected_class['value'])}"),
                ft.Text(f"{lang['season']}: {translate_season(selected_season['value'])}"),
                ft.Text(f"{lang['airline']}: {airlines[selected_airline['value']]['label'][current_language['value']]}"),
                ft.Divider(),
                temp_text,
                weather_text_ui,
                time_text,
                currency_column,
            ]
        )
        right_column = ft.Column(
            expand=True,
            spacing=10,
            controls=[
                ft.Text(lang["right_title"], size=22, weight=ft.FontWeight.BOLD),
                places_column,
                tips_column
            ]
        )
       
        page.add(ft.Row(expand=True, controls=[left_column, right_column]))
        page.update()

        async def load_destiny_data(
                temp_text,
                weather_text_ui,
                time_text,
                currency_column,
                lang,
        ):
            lat, lon = countries[selected_destiny["value"]]
            dest_key = selected_destiny["value"].lower()
            currency_code = CURRENCY.get(dest_key, {}).get("currency")

            temp, weather_code = await asyncio.to_thread(get_temperature, lat, lon)
            local_time = await asyncio.to_thread(get_local_time, lat, lon)

            current_temp["value"] = temp
            current_weather["value"] = weather_code

            rate = None
            if currency_code:
                rate = await asyncio.to_thread(get_usd_exchange_rate, currency_code)

            if temp is not None:
                if current_temperature["value"] == "°F":
                    temp_text.value = f"{lang['temperature']}: {(temp * 9/5 + 32):.1f}°F"
                else:
                    temp_text.value = f"{lang['temperature']}: {temp:.1f}°C"
            else:
                temp_text.value = f"{lang['temperature']}: Not available"

            weather_dict = {
                0: lang["clear_sky"],
                1: lang["mainly_clear"],
                2: lang["partly_cloudy"],
                3: lang["overcast"],
                45: lang["foggy"],
                48: lang["depositing_rime_fog"],
                51: lang["light_drizzle"],
                53: lang["moderate_drizzle"],
                55: lang["dense_drizzle"],
                61: lang["slight_rain"],
                63: lang["moderate_rain"],
                65: lang["heavy_rain"],
                71: lang["slight_snowfall"],
                73: lang["heavy_snowfall"],
                95: lang["thunderstorm"]    
            }
            weather_text_ui.value = f"{lang['weather_condition']}: {weather_dict.get(weather_code, 'Unknown')}"

            time_text.value = f"{lang['local_time']}: {local_time or 'Unknown'}"

            currency_column.controls.clear()
            if currency_code and rate:
                currency_column.controls.extend([
                    ft.Text(f"{lang['currency_label']}: {currency_code}"),
                    ft.Text(f"1 USD = {rate:.2f} {currency_code}"),
                    ft.Text(f"1 {currency_code} = {1/rate:.2f} USD"),
                ])
            else:
                currency_column.controls.append("Exchange rate unavailable")

            page.update()
           
        page.run_task(
            load_destiny_data,
            temp_text,
            weather_text_ui,
            time_text,
            currency_column,
            lang
        )

        async def load_destiny_tips(places_column, tips_column):

            lat, lon = countries[selected_destiny["value"]]
            dest_key = selected_destiny["value"].lower()

            currency_code = CURRENCY.get(dest_key, {}).get("currency")

            temp, weather_code = await asyncio.to_thread(get_temperature, lat, lon)

            def generate_travel_tips():
                tips = []

                # 🌡 Temperature tip
                if temp is not None:
                    if temp >= 30:
                        tips.append("wear a shirt")
                    elif temp <= 10:
                        tips.append("wear a coat")

                # 🌧 Weather tips
                if weather_code in [61, 63, 65]:
                    tips.append("use umbrella")

                if weather_code in [95]:
                    tips.append("be careful with storms")

                # 💱 Currency tip
                if currency_code != "USD":
                      tips.append("exchange dollars")

                if not tips:
                    tips.append("no tips")

                return tips


            places = await asyncio.to_thread(
                get_tourist_places,
                lat,
                lon,
                "5ae2e3f221c38a28845f05b69199742ec5381eb0e7d6915ec281f9a5"
            )

            tips = generate_travel_tips()

    # 🔹 PLACES
            places_column.controls.clear()
            places_column.controls.append(
                ft.Text(lang["popular_places"], size=18, weight=ft.FontWeight.BOLD)
            )   

            for place in places:
                places_column.controls.append(
                    ft.Row([
                        ft.Icon(ft.Icons.LOCATION_ON),
                        ft.Text(place)
                    ])
                )

    # 🔹 TIPS
            tips_column.controls.clear()
            tips_column.controls.append(
                ft.Text(lang["travel_tips"], size=18, weight=ft.FontWeight.BOLD)
            )

            for tip in tips:
                tips_column.controls.append(
                    ft.Row([
                        ft.Icon(ft.Icons.LIGHTBULB),
                        ft.Text(tip)
                    ])
                )

        page.update()
        page.run_task(load_destiny_tips, places_column, tips_column)

    def show_settings():
        current_index["value"] = 3
        page.controls.clear()
        page.add(navigation_bar)
        page.add(ft.Text(LANGUAGES[current_language["value"]]["settings_title"], size=22))

        # Main dropdowns of settings
        language_dropdown = ft.Dropdown(
            label=LANGUAGES[current_language["value"]]["language_label"],
            value=current_language["value"],
            options=[
                ft.dropdown.Option("es", "Español"),
                ft.dropdown.Option("en", "English"),
                ft.dropdown.Option("fr", "Français"),
                ft.dropdown.Option("it", "Italiano"),
                ft.dropdown.Option("de", "Deutsch"),
                ft.dropdown.Option("ch", "中国人"),
                ft.dropdown.Option("ja", "日本語"),
                ft.dropdown.Option("ar", "عربي")
            ],
        )
        language_dropdown.on_text_change=change_language
       
        currency_dropdown = ft.Dropdown(
            label = LANGUAGES[current_language["value"]]["currency_label"],
            value=current_currency["value"],
            options=[
                ft.dropdown.Option("USD", "USD - $"),
                ft.dropdown.Option("EUR", "EUR - €"),
                ft.dropdown.Option("GBP", "GBP - £"),
                ft.dropdown.Option("CHF", "CHF -Fr."),
                ft.dropdown.Option("JPY", "JPY - ¥"),
            ],
        )
        currency_dropdown.on_text_change=change_currency

        distance_dropdown = ft.Dropdown(
            label=LANGUAGES[current_language["value"]]["distance_label"],
            value=current_distance_unit["value"],
            options=[
                ft.dropdown.Option("km", LANGUAGES[current_language["value"]]["kilometers"]),
                ft.dropdown.Option("miles", LANGUAGES[current_language["value"]]["miles"])
            ],
        )
        distance_dropdown.on_text_change=lambda e: change_distance_unit(e)

        temperature_dropdown = ft.Dropdown(
            label = LANGUAGES[current_language["value"]]["temperature"],
            value=current_temperature["value"],
            options = [
                ft.dropdown.Option("°C", LANGUAGES[current_language["value"]]["celsius"]),
                ft.dropdown.Option("°F", LANGUAGES[current_language["value"]]["fahrenheit"])
            ],
        )
        temperature_dropdown.on_text_change=change_temperature

        page.add(language_dropdown, currency_dropdown, distance_dropdown, temperature_dropdown)
        page.update()

    update_navigation_labels()
    show_splash()
ft.app(main, view=ft.AppView.WEB_BROWSER, assets_dir="assets", web_renderer="html")


