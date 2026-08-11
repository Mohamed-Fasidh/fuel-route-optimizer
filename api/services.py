from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt
from typing import Iterable

import requests
from django.conf import settings
from django.core.cache import cache

from .models import FuelStation


class RoutePlanningError(Exception):
    pass


@dataclass(frozen=True)
class Point:
    lat: float
    lon: float


@dataclass
class Candidate:
    station: FuelStation
    route_position_miles: float
    distance_from_route_miles: float
    distance_from_start_miles: float = 0.0


EARTH_RADIUS_MILES = 3958.7613

# Station location quality controls. Five miles is the preferred corridor;
# fifteen miles is an absolute fallback because the supplied dataset often
# contains city-level rather than exact station coordinates.
PREFERRED_ROUTE_CORRIDOR_MILES = 5.0
MAX_FALLBACK_ROUTE_CORRIDOR_MILES = 15.0


def haversine_miles(a: Point, b: Point) -> float:
    lat1, lon1, lat2, lon2 = map(radians, [a.lat, a.lon, b.lat, b.lon])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * atan2(sqrt(h), sqrt(max(0.0, 1 - h)))


def _normalize_location(value: str) -> str:
    return " ".join(value.lower().split())


def _get_json(url: str, *, params: dict, headers: dict, timeout: float = 8.0):
    response = requests.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def geocode_location(location: str) -> tuple[Point, dict]:
    key = f"fuel:geocode:v2:{_normalize_location(location)}"
    cached = cache.get(key)
    if cached:
        cached = dict(cached)
        cached["cached"] = True
        return Point(cached["lat"], cached["lon"]), cached

    base = settings.NOMINATIM_BASE_URL.rstrip("/")
    data = _get_json(
        f"{base}/search",
        params={
            "q": location,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "us",
            "addressdetails": 1,
        },
        headers={"User-Agent": settings.NOMINATIM_USER_AGENT},
    )
    if not data:
        raise RoutePlanningError(f"Could not geocode USA location: {location}")

    result = data[0]
    address = result.get("address", {})
    if address.get("country_code", "").lower() != "us":
        raise RoutePlanningError(f"Location is not in the USA: {location}")

    payload = {
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
        "display_name": result.get("display_name", location),
        "address": address,
    }
    payload["cached"] = False
    cache.set(key, payload, settings.GEOCODE_CACHE_SECONDS)
    return Point(payload["lat"], payload["lon"]), payload


def _route_cache_key(start: Point, finish: Point) -> str:
    return (
        "fuel:route:v2:"
        f"{start.lat:.5f},{start.lon:.5f}:"
        f"{finish.lat:.5f},{finish.lon:.5f}"
    )


def get_route(start: Point, finish: Point) -> tuple[dict, bool]:
    key = _route_cache_key(start, finish)
    cached = cache.get(key)
    if cached:
        return cached, True

    coordinates = f"{start.lon},{start.lat};{finish.lon},{finish.lat}"
    base = settings.OSRM_BASE_URL.rstrip("/")
    data = _get_json(
        f"{base}/route/v1/driving/{coordinates}",
        params={
            "overview": "full",
            "geometries": "geojson",
            "steps": "false",
            "alternatives": "false",
        },
        headers={"User-Agent": "fuel-route-optimizer/1.0"},
        timeout=12.0,
    )
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutePlanningError("No drivable route was found between the locations.")

    route = data["routes"][0]
    cache.set(key, route, settings.ROUTE_CACHE_SECONDS)
    return route, False


def _sample_route(coordinates: list[list[float]], sample_every_miles: float = 5.0):
    if len(coordinates) < 2:
        raise RoutePlanningError("Routing service returned an invalid geometry.")

    points = [Point(lat=p[1], lon=p[0]) for p in coordinates]
    sampled = [(0.0, points[0])]
    cumulative = 0.0
    next_sample = sample_every_miles

    for prev, cur in zip(points, points[1:]):
        segment = haversine_miles(prev, cur)
        cumulative += segment
        if cumulative >= next_sample:
            sampled.append((cumulative, cur))
            while next_sample <= cumulative:
                next_sample += sample_every_miles

    if sampled[-1][0] < cumulative:
        sampled.append((cumulative, points[-1]))

    return sampled, cumulative


def _project_point_to_route(
    station_point: Point,
    sampled_route: list[tuple[float, Point]],
) -> tuple[float, float]:
    """Return (route_position_miles, distance_to_route_miles).

    The route geometry is sampled every few miles. Projecting onto each
    segment is more accurate than choosing the nearest sampled vertex,
    especially around bends.
    """
    if len(sampled_route) < 2:
        raise RoutePlanningError("Routing service returned an invalid geometry.")

    best_position = 0.0
    best_distance = float("inf")

    lat0 = radians(station_point.lat)
    cos_lat0 = max(0.1, cos(lat0))

    for (start_position, a), (end_position, b) in zip(
        sampled_route, sampled_route[1:]
    ):
        # Local equirectangular coordinates in miles around the station.
        ax = radians(a.lon - station_point.lon) * EARTH_RADIUS_MILES * cos_lat0
        ay = radians(a.lat - station_point.lat) * EARTH_RADIUS_MILES
        bx = radians(b.lon - station_point.lon) * EARTH_RADIUS_MILES * cos_lat0
        by = radians(b.lat - station_point.lat) * EARTH_RADIUS_MILES

        dx = bx - ax
        dy = by - ay
        denominator = dx * dx + dy * dy
        if denominator <= 1e-12:
            fraction = 0.0
        else:
            fraction = max(0.0, min(1.0, -(ax * dx + ay * dy) / denominator))

        px = ax + fraction * dx
        py = ay + fraction * dy
        distance = sqrt(px * px + py * py)

        if distance < best_distance:
            best_distance = distance
            best_position = start_position + fraction * (
                end_position - start_position
            )

    return best_position, best_distance


def _candidate_stations(
    sampled_route,
    route_distance: float,
    start_point: Point,
    max_distance_miles: float | None = None,
) -> list[Candidate]:
    route_points = [item[1] for item in sampled_route]

    min_lat = min(p.lat for p in route_points) - 0.25
    max_lat = max(p.lat for p in route_points) + 0.25
    min_lon = min(p.lon for p in route_points) - 0.25
    max_lon = max(p.lon for p in route_points) + 0.25

    qs = FuelStation.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
        latitude__gte=min_lat,
        latitude__lte=max_lat,
        longitude__gte=min_lon,
        longitude__lte=max_lon,
    ).only(
        "id", "truckstop_id", "name", "address", "city", "state",
        "retail_price", "latitude", "longitude", "location_source"
    )

    candidates: list[Candidate] = []
    configured_distance = max(
        0.1,
        float(settings.MAX_STATION_DISTANCE_MILES),
    )
    max_distance = (
        configured_distance
        if max_distance_miles is None
        else float(max_distance_miles)
    )
    max_distance = min(
        max(0.1, max_distance),
        MAX_FALLBACK_ROUTE_CORRIDOR_MILES,
    )

    for station in qs.iterator():
        station_point = Point(station.latitude, station.longitude)
        position, distance_from_route = _project_point_to_route(
            station_point, sampled_route
        )

        if distance_from_route > max_distance:
            continue

        # Do not use a station beyond the destination as a fuel stop.
        position = max(0.0, min(position, route_distance))
        distance_from_start = haversine_miles(start_point, station_point)

        candidates.append(
            Candidate(
                station=station,
                route_position_miles=position,
                distance_from_route_miles=distance_from_route,
                distance_from_start_miles=distance_from_start,
            )
        )

    candidates.sort(
        key=lambda c: (c.route_position_miles, float(c.station.retail_price))
    )
    return candidates


def _dedupe_candidates(candidates: Iterable[Candidate]) -> list[Candidate]:
    # Keep the cheapest station in each small route-position bucket.
    buckets: dict[tuple[int, str], Candidate] = {}
    for candidate in candidates:
        bucket = (round(candidate.route_position_miles / 2), candidate.station.city.upper())
        current = buckets.get(bucket)
        if current is None or candidate.station.retail_price < current.station.retail_price:
            buckets[bucket] = candidate
    return sorted(
        buckets.values(),
        key=lambda c: (c.route_position_miles, float(c.station.retail_price))
    )


def _select_start_station(candidates: list[Candidate]) -> Candidate:
    """
    Select a genuine starting fuel station.

    A station cannot become the start merely because it is cheap or because
    its distance_from_start_miles is unavailable/defaulted. It must also be
    physically near the beginning of the route.
    """
    if not candidates:
        raise RoutePlanningError(
            "No fuel stations are available for this route."
        )

    configured_radius = max(
        5.0,
        float(settings.MAX_STATION_DISTANCE_MILES),
    )

    start_route_radius = min(25.0, configured_radius)

    # Primary rule: station must actually be near route mile 0.
    near_route_start = [
        candidate
        for candidate in candidates
        if candidate.route_position_miles <= start_route_radius
    ]

    if not near_route_start:
        # Slightly wider fallback for sparse real-world data.
        near_route_start = [
            candidate
            for candidate in candidates
            if candidate.route_position_miles <= 50.0
        ]

    if not near_route_start:
        raise RoutePlanningError(
            "No fuel station from the supplied dataset is close enough "
            "to the route start."
        )

    # If actual origin distance is available, prefer stations genuinely
    # close to the origin. Route position remains the primary constraint.
    return min(
        near_route_start,
        key=lambda candidate: (
            float(candidate.station.retail_price),
            candidate.distance_from_start_miles,
            candidate.distance_from_route_miles,
            candidate.route_position_miles,
        ),
    )


def optimize_fuel(
    candidates: list[Candidate],
    route_distance: float,
    mpg: float,
    tank_capacity: float,
    max_range_miles: float | None = None,
) -> list[dict]:
    if route_distance <= 0.01:
        return []
    if mpg <= 0 or tank_capacity <= 0:
        raise RoutePlanningError("MPG and tank capacity must be positive.")

    capacity_range = tank_capacity * mpg
    effective_range = (
        capacity_range
        if max_range_miles is None
        else min(capacity_range, float(max_range_miles))
    )

    start_candidate = _select_start_station(candidates)

    # Fuel is purchased before entering the route at the start station.
    # The first station is therefore represented at route position zero.
    nodes = [{
        "position": 0.0,
        "price": float(start_candidate.station.retail_price),
        "candidate": start_candidate,
        "is_start": True,
    }]

    for candidate in candidates:
        if candidate.station.id == start_candidate.station.id:
            continue
        if candidate.route_position_miles <= 0.5:
            continue

        nodes.append({
            "position": candidate.route_position_miles,
            "price": float(candidate.station.retail_price),
            "candidate": candidate,
            "is_start": False,
        })

    nodes.sort(key=lambda n: n["position"])

    nodes.append({
        "position": route_distance,
        "price": -1.0,
        "candidate": None,
        "is_finish": True,
    })

    fuel = 0.0
    stops: list[dict] = []
    current_index = 0

    while current_index < len(nodes) - 1:
        current = nodes[current_index]
        current_pos = current["position"]

        reachable = []
        for idx in range(current_index + 1, len(nodes)):
            distance = nodes[idx]["position"] - current_pos
            if distance <= effective_range + 1e-9:
                reachable.append((idx, distance))
            else:
                break

        if not reachable:
            remaining = route_distance - current_pos
            raise RoutePlanningError(
                "No feasible fuel station within the "
                f"{effective_range:.0f}-mile vehicle range from route mile "
                f"{current_pos:.1f}. Remaining route distance: {remaining:.1f} miles. "
                "The supplied fuel dataset does not contain a sufficiently "
                "route-accessible station for this segment."
            )

        # Classic minimum-cost fuel strategy:
        # - If a cheaper reachable station exists, buy only enough to reach it.
        # - Otherwise fill enough to reach the farthest reachable point.
        cheaper = next(
            (
                item
                for item in reachable
                if not nodes[item[0]].get("is_finish")
                and nodes[item[0]]["price"] < current["price"] - 1e-9
            ),
            None,
        )

        if cheaper:
            target_index, target_distance = cheaper
            desired_fuel = target_distance / mpg
        else:
            target_index, target_distance = reachable[-1]
            desired_fuel = min(tank_capacity, target_distance / mpg)

        purchase = max(0.0, desired_fuel - fuel)

        if purchase > 1e-8:
            station = current["candidate"].station
            cost = purchase * current["price"]
            stops.append({
                "truckstop_id": station.truckstop_id,
                "station_name": station.name,
                "address": station.address,
                "city": station.city,
                "state": station.state,
                "fuel_price_per_gallon": round(current["price"], 4),
                "purchase_gallons": round(purchase, 3),
                "fuel_cost": round(cost, 2),
                "route_position_miles": round(current_pos, 1),
                "distance_from_route_miles": round(
                    current["candidate"].distance_from_route_miles, 2
                ),
                "location": {
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "source": station.location_source,
                },
            })
            fuel += purchase

        fuel -= target_distance / mpg
        fuel = max(0.0, fuel)
        current_index = target_index

        if nodes[current_index].get("is_finish"):
            break

    # A final safety check prevents an invalid plan from being returned.
    if not stops:
        raise RoutePlanningError("No feasible fuel-stop plan was found.")

    return stops


def _feature_collection(route_geometry, stops):
    features = [{
        "type": "Feature",
        "properties": {"type": "route"},
        "geometry": {
            "type": "LineString",
            "coordinates": route_geometry,
        },
    }]

    for stop in stops:
        features.append({
            "type": "Feature",
            "properties": {
                "type": "fuel_stop",
                "station_name": stop["station_name"],
                "fuel_price_per_gallon": stop["fuel_price_per_gallon"],
                "fuel_cost": stop["fuel_cost"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [
                    stop["location"]["longitude"],
                    stop["location"]["latitude"],
                ],
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def plan_route(
    start_location: str,
    finish_location: str,
    vehicle_mpg: float = 10,
    tank_capacity_gallons: float = 50,
    max_range_miles: float = 500,
):
    with ThreadPoolExecutor(max_workers=2) as pool:
        start_future = pool.submit(geocode_location, start_location)
        finish_future = pool.submit(geocode_location, finish_location)
        start_point, start_meta = start_future.result()
        finish_point, finish_meta = finish_future.result()

    route, route_cache_hit = get_route(start_point, finish_point)
    route_geometry = route["geometry"]["coordinates"]
    sampled, geometry_distance = _sample_route(route_geometry)

    # OSRM's route distance is authoritative for driving-distance reporting.
    # Geometry-derived haversine distance is used only to position candidates.
    route_distance = float(route.get("distance", 0.0)) / 1609.344
    if route_distance <= 0.01:
        route_distance = geometry_distance

    capacity_range = tank_capacity_gallons * vehicle_mpg
    effective_range = min(capacity_range, max_range_miles)

    if effective_range <= 0:
        raise RoutePlanningError("Vehicle range must be greater than zero.")

    # First attempt the preferred 5-mile corridor. If the supplied dataset
    # cannot provide a continuous feasible plan, retry with the documented
    # 15-mile fallback corridor. The 500-mile vehicle range remains a hard
    # constraint in both attempts.
    preferred_candidates = _dedupe_candidates(
        _candidate_stations(
            sampled,
            route_distance,
            start_point,
            max_distance_miles=PREFERRED_ROUTE_CORRIDOR_MILES,
        )
    )

    try:
        stops = optimize_fuel(
            preferred_candidates,
            route_distance=route_distance,
            mpg=vehicle_mpg,
            tank_capacity=tank_capacity_gallons,
            max_range_miles=max_range_miles,
        )
        corridor_used = PREFERRED_ROUTE_CORRIDOR_MILES
    except RoutePlanningError as preferred_error:
        fallback_candidates = _dedupe_candidates(
            _candidate_stations(
                sampled,
                route_distance,
                start_point,
                max_distance_miles=MAX_FALLBACK_ROUTE_CORRIDOR_MILES,
            )
        )
        try:
            stops = optimize_fuel(
                fallback_candidates,
                route_distance=route_distance,
                mpg=vehicle_mpg,
                tank_capacity=tank_capacity_gallons,
                max_range_miles=max_range_miles,
            )
            corridor_used = MAX_FALLBACK_ROUTE_CORRIDOR_MILES
        except RoutePlanningError as fallback_error:
            raise RoutePlanningError(
                "No feasible fuel plan was found. "
                f"Tried {PREFERRED_ROUTE_CORRIDOR_MILES:.0f}-mile and "
                f"{MAX_FALLBACK_ROUTE_CORRIDOR_MILES:.0f}-mile route corridors "
                f"while enforcing the {effective_range:.0f}-mile vehicle range. "
                f"Fallback reason: {fallback_error}"
            ) from preferred_error

    total_gallons = route_distance / vehicle_mpg
    total_cost = sum(stop["fuel_cost"] for stop in stops)

    return {
        "request": {
            "start_location": start_location,
            "finish_location": finish_location,
            "vehicle_mpg": vehicle_mpg,
            "tank_capacity_gallons": tank_capacity_gallons,
            "max_range_miles": max_range_miles,
        },
        "start": {
            "latitude": start_point.lat,
            "longitude": start_point.lon,
            "display_name": start_meta["display_name"],
        },
        "finish": {
            "latitude": finish_point.lat,
            "longitude": finish_point.lon,
            "display_name": finish_meta["display_name"],
        },
        "summary": {
            "route_miles": round(route_distance, 1),
            "duration_minutes": round(route["duration"] / 60, 1),
            "total_gallons": round(total_gallons, 2),
            "total_fuel_cost": round(total_cost, 2),
            "fuel_stops": len(stops),
            "effective_vehicle_range_miles": round(effective_range, 1),
            "preferred_route_corridor_miles": PREFERRED_ROUTE_CORRIDOR_MILES,
            "route_corridor_used_miles": corridor_used,
        },
        "fuel_stops": stops,
        "map": _feature_collection(route_geometry, stops),
        "performance": {
            "geocoding_api_calls": 0 if (
                start_meta.get("cached") and finish_meta.get("cached")
            ) else 2,
            "routing_api_calls": 0 if route_cache_hit else 1,
            "cache_hits": {
                "start": bool(start_meta.get("cached")),
                "finish": bool(finish_meta.get("cached")),
                "route": route_cache_hit,
            },
        },
    }