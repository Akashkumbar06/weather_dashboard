"""
Weather Dashboard - single-file version (virtual internship task 4)

Features: Python modules (sections below), input validation,
data processing, error handling, and built-in unit tests.

Run dashboard : python weather_dashboard_all.py
Run tests     : python weather_dashboard_all.py --test
Data source   : Open-Meteo (free, no API key)
"""
import json
import re
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch

# ======================================================================
# 1. VALIDATION
# ======================================================================
CITY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'\-]{1,59}$")


class ValidationError(ValueError):
    """Raised when user input is invalid."""


def validate_city(city):
    """Return a cleaned city name or raise ValidationError."""
    if city is None or not city.strip():
        raise ValidationError("City name cannot be empty.")
    city = " ".join(city.strip().split())
    if not CITY_PATTERN.match(city):
        raise ValidationError(
            "City name must be 2-60 characters: letters, spaces, . ' - only."
        )
    return city


def validate_days(value, minimum=1, maximum=7):
    """Return forecast days as int within [minimum, maximum]."""
    try:
        days = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Days must be a whole number.")
    if not minimum <= days <= maximum:
        raise ValidationError(f"Days must be between {minimum} and {maximum}.")
    return days


# ======================================================================
# 2. API CLIENT
# ======================================================================
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 10


class WeatherAPIError(Exception):
    """Raised for network, HTTP, or data problems."""


def _get_json(url, params):
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(full_url, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise WeatherAPIError(f"Server returned HTTP {e.code}.") from e
    except urllib.error.URLError as e:
        raise WeatherAPIError(f"Network problem: {e.reason}") from e
    except TimeoutError as e:
        raise WeatherAPIError("Request timed out.") from e
    except json.JSONDecodeError as e:
        raise WeatherAPIError("Received invalid data from server.") from e


def geocode(city):
    """Return name, country, latitude, longitude for a city."""
    data = _get_json(GEO_URL, {"name": city, "count": 1, "language": "en"})
    results = data.get("results")
    if not results:
        raise WeatherAPIError(f"City '{city}' not found.")
    r = results[0]
    return {
        "name": r["name"],
        "country": r.get("country", ""),
        "latitude": r["latitude"],
        "longitude": r["longitude"],
    }


def fetch_forecast(lat, lon, days):
    """Return raw forecast JSON for the coordinates."""
    return _get_json(FORECAST_URL, {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "forecast_days": days,
    })


# ======================================================================
# 3. DATA PROCESSING
# ======================================================================
WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Rain showers",
    81: "Heavy showers", 82: "Violent showers", 95: "Thunderstorm",
    96: "Thunderstorm with hail", 99: "Severe thunderstorm with hail",
}


def describe_code(code):
    return WEATHER_CODES.get(code, "Unknown")


def c_to_f(celsius):
    return round(celsius * 9 / 5 + 32, 1)


def process_forecast(raw):
    """Return {'current': {...}, 'daily': [...], 'summary': {...}}."""
    try:
        cur = raw["current"]
        daily = raw["daily"]
        current = {
            "temp_c": cur["temperature_2m"],
            "temp_f": c_to_f(cur["temperature_2m"]),
            "humidity": cur["relative_humidity_2m"],
            "wind_kmh": cur["wind_speed_10m"],
            "condition": describe_code(cur["weather_code"]),
        }
        days = [
            {"date": d, "max_c": hi, "min_c": lo, "rain_mm": rain or 0.0}
            for d, hi, lo, rain in zip(
                daily["time"],
                daily["temperature_2m_max"],
                daily["temperature_2m_min"],
                daily["precipitation_sum"],
            )
        ]
    except (KeyError, TypeError) as e:
        raise ValueError(f"Unexpected data format: missing {e}") from e

    if not days:
        raise ValueError("No forecast data available.")

    summary = {
        "avg_max_c": round(sum(d["max_c"] for d in days) / len(days), 1),
        "avg_min_c": round(sum(d["min_c"] for d in days) / len(days), 1),
        "total_rain_mm": round(sum(d["rain_mm"] for d in days), 1),
        "hottest_day": max(days, key=lambda d: d["max_c"])["date"],
        "wettest_day": max(days, key=lambda d: d["rain_mm"])["date"],
    }
    return {"current": current, "daily": days, "summary": summary}


# ======================================================================
# 4. DASHBOARD DISPLAY
# ======================================================================
def render(place, data):
    c, s = data["current"], data["summary"]
    line = "=" * 56
    out = [
        line,
        f" WEATHER DASHBOARD - {place['name']}, {place['country']}",
        line,
        f" Now: {c['condition']}",
        f" Temperature: {c['temp_c']}°C / {c['temp_f']}°F",
        f" Humidity:    {c['humidity']}%",
        f" Wind:        {c['wind_kmh']} km/h",
        "-" * 56,
        f" {'Date':<12}{'Max°C':>8}{'Min°C':>8}{'Rain mm':>10}",
    ]
    for d in data["daily"]:
        out.append(f" {d['date']:<12}{d['max_c']:>8}{d['min_c']:>8}{d['rain_mm']:>10}")
    out += [
        "-" * 56,
        f" Avg high {s['avg_max_c']}°C | Avg low {s['avg_min_c']}°C | "
        f"Total rain {s['total_rain_mm']} mm",
        f" Hottest day: {s['hottest_day']} | Wettest day: {s['wettest_day']}",
        line,
    ]
    return "\n".join(out)


# ======================================================================
# 5. MAIN PROGRAM (with error handling)
# ======================================================================
def get_input(prompt, validator):
    """Keep asking until the input passes validation."""
    while True:
        try:
            return validator(input(prompt))
        except ValidationError as e:
            print(f"  Invalid input: {e}")


def run_once():
    city = get_input("Enter city name: ", validate_city)
    days = get_input("Forecast days (1-7): ", validate_days)
    try:
        place = geocode(city)
        raw = fetch_forecast(place["latitude"], place["longitude"], days)
        data = process_forecast(raw)
    except WeatherAPIError as e:
        print(f"  Could not fetch weather: {e}")
        return
    except ValueError as e:
        print(f"  Data problem: {e}")
        return
    print(render(place, data))


def main():
    print("Weather Dashboard (Ctrl+C to quit)")
    try:
        while True:
            run_once()
            if input("\nAnother city? (y/n): ").strip().lower() != "y":
                break
    except (KeyboardInterrupt, EOFError):
        pass
    print("\nGoodbye!")


# ======================================================================
# 6. UNIT TESTS  (python weather_dashboard_all.py --test)
# ======================================================================
SAMPLE = {
    "current": {"temperature_2m": 30.0, "relative_humidity_2m": 60,
                "wind_speed_10m": 12.5, "weather_code": 2},
    "daily": {"time": ["2026-10-08", "2026-10-09"],
              "temperature_2m_max": [32, 34], "temperature_2m_min": [22, 23],
              "precipitation_sum": [0.0, 5.5]},
}


class TestValidators(unittest.TestCase):
    def test_valid_city(self):
        self.assertEqual(validate_city("  New   York "), "New York")

    def test_empty_city(self):
        with self.assertRaises(ValidationError):
            validate_city("   ")

    def test_bad_city(self):
        with self.assertRaises(ValidationError):
            validate_city("12345")

    def test_days(self):
        self.assertEqual(validate_days("3"), 3)
        for bad in ("abc", "0", "8", None):
            with self.assertRaises(ValidationError):
                validate_days(bad)


class TestProcessor(unittest.TestCase):
    def test_conversion(self):
        self.assertEqual(c_to_f(0), 32.0)
        self.assertEqual(c_to_f(100), 212.0)

    def test_code(self):
        self.assertEqual(describe_code(0), "Clear sky")
        self.assertEqual(describe_code(12345), "Unknown")

    def test_process(self):
        r = process_forecast(SAMPLE)
        self.assertEqual(r["current"]["condition"], "Partly cloudy")
        self.assertEqual(r["summary"]["avg_max_c"], 33.0)
        self.assertEqual(r["summary"]["total_rain_mm"], 5.5)
        self.assertEqual(r["summary"]["wettest_day"], "2026-10-09")

    def test_bad_data(self):
        with self.assertRaises(ValueError):
            process_forecast({"current": {}})


class TestAPI(unittest.TestCase):
    @patch(f"{__name__}._get_json", return_value={})
    def test_city_not_found(self, _):
        with self.assertRaises(WeatherAPIError):
            geocode("Nowhereville")

    @patch(f"{__name__}._get_json", return_value={"results": [
        {"name": "Mudhol", "country": "India", "latitude": 16.3, "longitude": 75.3}]})
    def test_geocode_ok(self, _):
        self.assertEqual(geocode("Mudhol")["country"], "India")


if __name__ == "__main__":
    if "--test" in sys.argv:
        unittest.main(argv=[sys.argv[0], "-v"])
    else:
        main()
