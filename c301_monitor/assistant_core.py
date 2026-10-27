"""Turkish local assistant commands and live Open-Meteo weather query.

No camera account credentials are read. No audio recordings are stored.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any

import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def conditions(code: int) -> str:
    if code == 0: return "açık"
    if code in {1, 2, 3}: return "parçalı veya çok bulutlu"
    if code in {45, 48}: return "sisli"
    if code in {51, 53, 55, 56, 57}: return "çiseli"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}: return "yağmurlu"
    if code in {71, 73, 75, 77, 85, 86}: return "karlı"
    if code in {95, 96, 99}: return "gök gürültülü"
    return "değişken"


def fmt(value: Any) -> str:
    return str(round(float(value)))


def get_weather(city: str, session=None) -> str:
    """Request current conditions; throw on failed HTTP, never fabricate readings."""
    client = session if session is not None else requests
    location = client.get(
        GEOCODE_URL,
        params={"name": city, "count": 5, "language": "tr", "format": "json"},
        timeout=8,
    )
    location.raise_for_status()
    places = location.json().get("results") or []
    # Prefer Turkish city when geocoder returns multiple homonyms.
    place = next((p for p in places if p.get("country_code") == "TR"), None)
    if place is None and places:
        place = places[0]
    if not place:
        return f"{city} için konum bulunamadı. Şehri kontrol eder misin?"

    weather = client.get(
        WEATHER_URL,
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "timezone": "auto",
        },
        timeout=8,
    )
    weather.raise_for_status()
    now = weather.json().get("current") or {}
    if "temperature_2m" not in now or "weather_code" not in now:
        return "Hava durumu verisini şu an alamadım. Daha sonra tekrar deneyebilirsin."
    city_name = place.get("name", city)
    answer = (f"{city_name} için şu an hava {conditions(int(now['weather_code']))}. "
              f"Sıcaklık {fmt(now['temperature_2m'])} derece.")
    if now.get("apparent_temperature") is not None:
        answer += f" Hissedilen {fmt(now['apparent_temperature'])} derece."
    if now.get("wind_speed_10m") is not None:
        answer += f" Rüzgâr saatte {fmt(now['wind_speed_10m'])} kilometre."
    return answer


def normalize(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


def answer_question(question: str, city: str = "Ankara", session=None, clock=None) -> str:
    q = normalize(question)
    if not q:
        return "Seni duyamadım. Mikrofonu kontrol edip tekrar deneyebilirsin."
    if any(term in q for term in ("hava", "derece", "yağmur", "yağacak", "sıcaklık", "soğuk mu")):
        try:
            return get_weather(city, session)
        except (requests.RequestException, KeyError, TypeError, ValueError, OSError):
            return "Hava durumu servisine erişemedim. İnternet bağlantısını kontrol edebilir misin?"
    if "saat" in q and any(k in q for k in ("kaç", "nedir", "söyle")):
        dt = clock if clock is not None else datetime.now()
        return f"Saat {dt.strftime('%H:%M')}."
    if any(k in q for k in ("merhaba", "selam", "günaydın")):
        return "Merhaba! Hava durumunu veya saati sorabilirsin."
    if any(k in q for k in ("nesne", "kamera", "güvenlik", "kim girdi")):
        return "Kamera izleme sistemi ayrı çalışıyor. Olay geçmişini sesle sorgulama özelliği henüz geliştirilmedi."
    return "Bu soruyu henüz yanıtlayamıyorum. Şimdilik hava durumunu veya saati sorabilirsin."
