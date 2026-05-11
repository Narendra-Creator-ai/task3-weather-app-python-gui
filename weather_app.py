import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import requests
import tkinter as tk
from tkinter import messagebox, ttk


BASE_URL = "https://api.openweathermap.org/data/2.5"
UNITS = "metric"
APP_DIR = Path(__file__).resolve().parent
HISTORY_FILE = APP_DIR / "searched_cities.json"
CONFIG_FILE = APP_DIR / "weather_config.json"


class WeatherAppError(Exception):
    """Raised when a recoverable weather app error occurs."""


def get_api_key(typed_key: str) -> str:
    api_key = typed_key.strip() or os.getenv("OPENWEATHER_API_KEY", "").strip()
    if not api_key:
        raise WeatherAppError("Enter API key or set OPENWEATHER_API_KEY first.")
    return api_key


def make_api_request(endpoint: str, params: Dict[str, str]) -> Dict:
    try:
        response = requests.get(
            f"{BASE_URL}/{endpoint}",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise WeatherAppError("Request timed out. Please try again.") from exc
    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code == 404:
            raise WeatherAppError("City not found. Please check the spelling.") from exc
        if status_code == 401:
            raise WeatherAppError("Invalid API key. Please verify OPENWEATHER_API_KEY.") from exc
        raise WeatherAppError(
            f"Weather service returned an error (HTTP {status_code})."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise WeatherAppError("Network error. Please check your internet connection.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise WeatherAppError("Failed to parse weather data response.") from exc

    cod = str(payload.get("cod", ""))
    if cod and cod != "200":
        message = payload.get("message", "Unexpected API response.")
        if cod == "404":
            raise WeatherAppError("City not found. Please check the spelling.")
        raise WeatherAppError(f"Weather API error: {message}")

    return payload


def get_current_weather(api_key: str, city: str) -> Dict:
    return make_api_request(
        "weather",
        {"q": city, "appid": api_key, "units": UNITS},
    )


def get_5_day_forecast(api_key: str, city: str) -> Dict:
    return make_api_request(
        "forecast",
        {"q": city, "appid": api_key, "units": UNITS},
    )


def extract_daily_forecast(forecast_payload: Dict) -> List[Dict]:
    entries = forecast_payload.get("list", [])
    selected = []
    seen_dates = set()

    for item in entries:
        dt_txt = item.get("dt_txt", "")
        if "12:00:00" not in dt_txt:
            continue

        date_part = dt_txt.split(" ")[0]
        if date_part in seen_dates:
            continue

        selected.append(item)
        seen_dates.add(date_part)

        if len(selected) == 5:
            break

    if len(selected) < 5:
        for item in entries:
            date_part = item.get("dt_txt", "").split(" ")[0]
            if not date_part or date_part in seen_dates:
                continue
            selected.append(item)
            seen_dates.add(date_part)
            if len(selected) == 5:
                break

    return selected


def parse_current_weather(payload: Dict) -> Dict[str, str]:
    city_name = payload.get("name", "Unknown")
    country_code = payload.get("sys", {}).get("country", "")
    main = payload.get("main", {})
    weather_items = payload.get("weather", [{}])
    weather_text = weather_items[0].get("description", "N/A").title()

    return {
        "location": f"{city_name}, {country_code}".rstrip(", "),
        "temperature": f"{main.get('temp', 'N/A')} C",
        "condition": weather_text,
        "humidity": f"{main.get('humidity', 'N/A')}%",
    }


def parse_forecast_lines(forecast_payload: Dict) -> List[str]:
    daily_items = extract_daily_forecast(forecast_payload)
    lines: List[str] = []
    for item in daily_items:
        dt_txt = item.get("dt_txt", "")
        try:
            parsed_date = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
            pretty_day = parsed_date.strftime("%a, %d %b")
        except ValueError:
            pretty_day = dt_txt or "Unknown Day"
        temp = item.get("main", {}).get("temp", "N/A")
        desc = item.get("weather", [{}])[0].get("description", "N/A").title()
        humidity = item.get("main", {}).get("humidity", "N/A")
        lines.append(f"{pretty_day}: {temp} C, {desc}, Humidity {humidity}%")
    return lines


def load_city_history() -> List[str]:
    if not HISTORY_FILE.exists():
        return []

    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(item) for item in data if str(item).strip()]
    except (json.JSONDecodeError, OSError):
        return []

    return []


def load_saved_api_key() -> str:
    if not CONFIG_FILE.exists():
        return ""

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""

    saved_key = data.get("api_key", "") if isinstance(data, dict) else ""
    return str(saved_key).strip()


def save_api_key(api_key: str) -> None:
    payload = {"api_key": api_key.strip()}
    try:
        CONFIG_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        raise WeatherAppError(f"Could not save API key: {exc}") from exc


def save_city_history(cities: List[str]) -> None:
    try:
        HISTORY_FILE.write_text(json.dumps(cities, indent=2), encoding="utf-8")
    except OSError as exc:
        raise WeatherAppError(f"Could not save city history: {exc}") from exc


def add_city_to_history(city: str) -> None:
    normalized_city = city.strip()
    if not normalized_city:
        return

    history = load_city_history()
    lowered = [item.lower() for item in history]
    if normalized_city.lower() not in lowered:
        history.append(normalized_city)
        save_city_history(history)


def run_lookup(city: str, api_key: str) -> Tuple[Dict[str, str], List[str], str]:
    current_weather = get_current_weather(api_key, city)
    forecast = get_5_day_forecast(api_key, city)
    parsed_weather = parse_current_weather(current_weather)
    parsed_forecast = parse_forecast_lines(forecast)
    resolved_city = current_weather.get("name", city)
    add_city_to_history(resolved_city)
    return parsed_weather, parsed_forecast, resolved_city


class WeatherAppGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Live Weather App")
        self.root.geometry("840x620")
        self.root.minsize(760, 560)

        self.is_loading = False
        self._build_ui()
        self.refresh_saved_cities()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top_frame = ttk.Frame(self.root, padding=14)
        top_frame.grid(row=0, column=0, sticky="ew")
        top_frame.columnconfigure(1, weight=1)
        top_frame.columnconfigure(3, weight=1)

        ttk.Label(top_frame, text="OpenWeather API Key:").grid(row=0, column=0, sticky="w")
        self.api_key_entry = ttk.Entry(top_frame, show="*", width=34)
        self.api_key_entry.grid(row=0, column=1, sticky="ew", padx=(6, 10))
        self.api_key_entry.insert(0, load_saved_api_key() or os.getenv("OPENWEATHER_API_KEY", "").strip())

        ttk.Label(top_frame, text="City:").grid(row=0, column=2, sticky="e")
        self.city_entry = ttk.Entry(top_frame, width=28)
        self.city_entry.grid(row=0, column=3, sticky="ew", padx=(6, 10))
        self.city_entry.bind("<Return>", lambda _: self.search_weather())

        self.search_button = ttk.Button(
            top_frame,
            text="Get Weather",
            command=self.search_weather,
        )
        self.search_button.grid(row=0, column=4, sticky="ew")

        content_frame = ttk.Frame(self.root, padding=(14, 0, 14, 14))
        content_frame.grid(row=1, column=0, sticky="nsew")
        content_frame.columnconfigure(0, weight=3)
        content_frame.columnconfigure(1, weight=2)
        content_frame.rowconfigure(1, weight=1)

        weather_frame = ttk.LabelFrame(content_frame, text="Current Weather", padding=12)
        weather_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        weather_frame.columnconfigure(0, weight=1)

        self.location_var = tk.StringVar(value="Location: -")
        self.temp_var = tk.StringVar(value="Temperature: -")
        self.condition_var = tk.StringVar(value="Condition: -")
        self.humidity_var = tk.StringVar(value="Humidity: -")

        ttk.Label(weather_frame, textvariable=self.location_var).grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(weather_frame, textvariable=self.temp_var).grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(weather_frame, textvariable=self.condition_var).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(weather_frame, textvariable=self.humidity_var).grid(row=3, column=0, sticky="w", pady=2)

        saved_frame = ttk.LabelFrame(content_frame, text="Saved Cities", padding=12)
        saved_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")
        saved_frame.columnconfigure(0, weight=1)
        saved_frame.rowconfigure(0, weight=1)

        self.saved_listbox = tk.Listbox(saved_frame, height=16)
        self.saved_listbox.grid(row=0, column=0, sticky="nsew")
        self.saved_listbox.bind("<Double-Button-1>", lambda _: self.search_from_saved())

        saved_buttons = ttk.Frame(saved_frame)
        saved_buttons.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        saved_buttons.columnconfigure(0, weight=1)
        saved_buttons.columnconfigure(1, weight=1)

        ttk.Button(saved_buttons, text="Search Selected", command=self.search_from_saved).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(saved_buttons, text="Refresh List", command=self.refresh_saved_cities).grid(
            row=0, column=1, sticky="ew"
        )

        forecast_frame = ttk.LabelFrame(content_frame, text="5-Day Forecast", padding=12)
        forecast_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(12, 0))
        forecast_frame.columnconfigure(0, weight=1)
        forecast_frame.rowconfigure(0, weight=1)

        self.forecast_text = tk.Text(forecast_frame, wrap="word", height=12)
        self.forecast_text.grid(row=0, column=0, sticky="nsew")
        self.forecast_text.insert("1.0", "Forecast will appear here.")
        self.forecast_text.configure(state="disabled")

        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(self.root, textvariable=self.status_var, padding=(14, 0, 14, 12))
        status_label.grid(row=2, column=0, sticky="w")

    def _set_loading(self, loading: bool) -> None:
        self.is_loading = loading
        state = "disabled" if loading else "normal"
        self.search_button.configure(state=state)

    def _set_forecast_text(self, lines: List[str]) -> None:
        self.forecast_text.configure(state="normal")
        self.forecast_text.delete("1.0", "end")
        if lines:
            self.forecast_text.insert("1.0", "\n".join(lines))
        else:
            self.forecast_text.insert("1.0", "Forecast data is unavailable.")
        self.forecast_text.configure(state="disabled")

    def _update_weather_fields(self, weather_data: Dict[str, str], forecast_lines: List[str]) -> None:
        self.location_var.set(f"Location: {weather_data['location']}")
        self.temp_var.set(f"Temperature: {weather_data['temperature']}")
        self.condition_var.set(f"Condition: {weather_data['condition']}")
        self.humidity_var.set(f"Humidity: {weather_data['humidity']}")
        self._set_forecast_text(forecast_lines)

    def refresh_saved_cities(self) -> None:
        self.saved_listbox.delete(0, "end")
        for city in load_city_history():
            self.saved_listbox.insert("end", city)

    def search_from_saved(self) -> None:
        if self.is_loading:
            return
        selection = self.saved_listbox.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Select a city from the saved list.")
            return
        selected_city = self.saved_listbox.get(selection[0])
        self.city_entry.delete(0, "end")
        self.city_entry.insert(0, selected_city)
        self.search_weather()

    def search_weather(self) -> None:
        if self.is_loading:
            return

        city = self.city_entry.get().strip()
        if not city:
            messagebox.showwarning("Missing City", "Please enter a city name.")
            return

        try:
            api_key = get_api_key(self.api_key_entry.get())
        except WeatherAppError as exc:
            messagebox.showerror("API Key Error", str(exc))
            return

        try:
            save_api_key(api_key)
        except WeatherAppError as exc:
            messagebox.showwarning("Save Warning", str(exc))

        self.status_var.set(f"Fetching weather for {city}...")
        self._set_loading(True)

        thread = threading.Thread(
            target=self._fetch_weather_background,
            args=(city, api_key),
            daemon=True,
        )
        thread.start()

    def _fetch_weather_background(self, city: str, api_key: str) -> None:
        try:
            weather_data, forecast_lines, resolved_city = run_lookup(city, api_key)
        except WeatherAppError as exc:
            self.root.after(0, self._handle_error, str(exc))
            return

        self.root.after(
            0,
            self._handle_success,
            weather_data,
            forecast_lines,
            resolved_city,
        )

    def _handle_success(
        self,
        weather_data: Dict[str, str],
        forecast_lines: List[str],
        resolved_city: str,
    ) -> None:
        self._set_loading(False)
        self._update_weather_fields(weather_data, forecast_lines)
        self.refresh_saved_cities()
        self.status_var.set(f"Updated weather for {resolved_city}.")

    def _handle_error(self, error_message: str) -> None:
        self._set_loading(False)
        self.status_var.set("Request failed.")
        messagebox.showerror("Weather Error", error_message)


if __name__ == "__main__":
    app_root = tk.Tk()
    app = WeatherAppGUI(app_root)
    app_root.mainloop()
