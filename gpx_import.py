# -*- coding: utf-8 -*-
"""
Импорт GPS-трека, экспортированного со смарт-часов (Garmin, Polar, Suunto,
Coros, Amazfit и др.) в формате GPX или TCX.

Оба формата — это XML, поэтому парсим стандартной библиотекой xml.etree,
без внешних зависимостей.

FIT-файлы (бинарный формат Garmin) нужно предварительно сконвертировать в
GPX/TCX — это можно сделать бесплатно на страницах "Export" в Garmin
Connect / Strava, либо конвертером (например, gpsbabel).
"""
import math
import xml.etree.ElementTree as ET
from datetime import datetime


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _parse_iso_time(s):
    if s is None:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _strip_ns(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag


def parse_gpx(file_bytes):
    """Парсит GPX-файл, возвращает список точек {lat, lon, t, ele}."""
    root = ET.fromstring(file_bytes)
    points = []
    for trkpt in root.iter():
        if _strip_ns(trkpt.tag) != "trkpt":
            continue
        lat = float(trkpt.attrib["lat"])
        lon = float(trkpt.attrib["lon"])
        ele, t = None, None
        for child in trkpt:
            name = _strip_ns(child.tag)
            if name == "ele":
                try:
                    ele = float(child.text)
                except (TypeError, ValueError):
                    ele = None
            elif name == "time":
                t = _parse_iso_time(child.text)
        points.append({"lat": lat, "lon": lon, "ele": ele, "time": t})
    return points


def parse_tcx(file_bytes):
    """Парсит TCX-файл, возвращает список точек {lat, lon, t, ele}."""
    root = ET.fromstring(file_bytes)
    points = []
    for trackpoint in root.iter():
        if _strip_ns(trackpoint.tag) != "Trackpoint":
            continue
        lat, lon, ele, t = None, None, None, None
        for child in trackpoint:
            name = _strip_ns(child.tag)
            if name == "Position":
                for pos_child in child:
                    pname = _strip_ns(pos_child.tag)
                    if pname == "LatitudeDegrees":
                        lat = float(pos_child.text)
                    elif pname == "LongitudeDegrees":
                        lon = float(pos_child.text)
            elif name == "AltitudeMeters":
                try:
                    ele = float(child.text)
                except (TypeError, ValueError):
                    ele = None
            elif name == "Time":
                t = _parse_iso_time(child.text)
        if lat is not None and lon is not None:
            points.append({"lat": lat, "lon": lon, "ele": ele, "time": t})
    return points


def points_to_track_summary(points):
    """
    Считает суммарную дистанцию (км) и длительность (сек) по точкам трека.
    Возвращает (distance_km, duration_sec, points_for_storage).
    """
    if not points:
        return 0.0, 0, []

    distance_km = 0.0
    for i in range(1, len(points)):
        p1, p2 = points[i - 1], points[i]
        distance_km += _haversine_km(p1["lat"], p1["lon"], p2["lat"], p2["lon"])

    times = [p["time"] for p in points if p["time"] is not None]
    duration_sec = 0
    if len(times) >= 2:
        duration_sec = int((max(times) - min(times)).total_seconds())

    points_for_storage = [
        {
            "lat": p["lat"],
            "lon": p["lon"],
            "ele": p["ele"],
            "t": p["time"].isoformat() if p["time"] else None,
        }
        for p in points
    ]
    return round(distance_km, 3), duration_sec, points_for_storage


def parse_track_file(filename, file_bytes):
    """Определяет формат по расширению и парсит файл. Возвращает summary."""
    lower = filename.lower()
    if lower.endswith(".gpx"):
        points = parse_gpx(file_bytes)
    elif lower.endswith(".tcx"):
        points = parse_tcx(file_bytes)
    elif lower.endswith(".fit"):
        raise ValueError(
            "Формат .FIT не поддерживается напрямую. Экспортируйте тренировку "
            "в формате GPX или TCX (в Garmin Connect / Strava: Export → GPX)."
        )
    else:
        raise ValueError("Неизвестный формат файла. Поддерживаются .gpx и .tcx")

    return points_to_track_summary(points)