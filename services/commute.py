from services.transit import (
    get_local_route,
    get_transit_route,
)
from services.surroundings import geocode_query
from services.walking import walking_route

DEFAULT_DESTINATION = {
    "name": "Rakuten Crimson House",
    "address": "楽天クリムゾンハウス, 東京都世田谷区玉川1-14-1",
    "station": "Futako-Tamagawa",
    "station_walk_minutes": 4,
    "arrival_buffer_minutes": 3,
}


def destination_details(destination):
    if isinstance(destination, dict):
        return {**DEFAULT_DESTINATION, **destination}
    return {**DEFAULT_DESTINATION, "station": destination}


def office_walk_minutes(destination):
    coordinates = destination.get("coordinates")
    if not coordinates and destination.get("address"):
        coordinates = geocode_query(destination["address"])
    if not coordinates:
        return destination["station_walk_minutes"], "configured_fallback"
    # The official Rakuten access guidance says approximately four minutes.
    # Keep this route cacheable when a station coordinate is supplied later.
    return destination["station_walk_minutes"], "official_access_estimate"


def routed_station_walk(room, station, listing_walk, bus_minutes=None):
    if bus_minutes:
        return listing_walk or 0, None, "listing"
    origin = room.get("coordinates")
    if not origin:
        return listing_walk or 0, None, "listing"
    try:
        station_point = geocode_query(f"{station}駅 日本")
        route = walking_route(origin["latitude"], origin["longitude"], station_point["latitude"], station_point["longitude"])
        if route:
            return route["walking_minutes"], route["distance_m"], route["routing_source"]
    except (KeyError, TypeError):
        pass
    return listing_walk or 0, None, "listing"


def enrich_commute(
    room,
    destination="Futako-Tamagawa",
):
    destination = destination_details(destination)
    station_destination = destination["station"]
    station = room.get("primary_station")
    access = room.get("access_options") or []
    candidates = access or ([{"station": station, "walk_minutes": room.get("station_walk_minutes"), "bus_minutes": room.get("bus_minutes")}] if station else [])
    routes = []
    for option in candidates:
        route = get_local_route(option.get("station"), station_destination)
        if route:
            route = dict(route)
            route["station"] = option["station"]
            walk, distance, source = routed_station_walk(
                room, option["station"], option.get("walk_minutes"), option.get("bus_minutes")
            )
            route["listing_station_walk_minutes"] = option.get("walk_minutes")
            route["station_walk_minutes"] = walk
            route["station_walk_distance_m"] = distance
            route["station_walk_source"] = source
            route["bus_minutes"] = option.get("bus_minutes") or 0
            route["total"] = route["train_minutes"] + route["station_walk_minutes"] + route["bus_minutes"]
            routes.append(route)
    commute = min(routes, key=lambda item: item["total"]) if routes else get_transit_route(station, station_destination)

    if commute is None:
        room[
            "train_commute_minutes"
        ] = None

        room[
            "transfers"
        ] = None

        room[
            "direct_train"
        ] = None

        room["total_commute_minutes"] = None
        room["planning_commute_minutes"] = None
        room["commute_confidence"] = "unknown"

        room[
            "commute_source"
        ] = None

        return room

    train_minutes = commute[
        "train_minutes"
    ]

    walk_minutes = commute.get("station_walk_minutes", room.get("station_walk_minutes") or 0)

    bus_minutes = (
        commute.get("bus_minutes", room.get("bus_minutes") or 0)
    )

    office_walk, office_source = office_walk_minutes(destination)
    total = (
        walk_minutes
        + bus_minutes
        + train_minutes
        + office_walk
    )
    # Planning time protects rankings from best-case timetable and transfer assumptions.
    buffer = 5 if commute.get("transfers", 0) == 0 else 8 if commute.get("transfers", 0) == 1 else 12
    if bus_minutes:
        buffer += 5
    planning = total + buffer + destination.get("arrival_buffer_minutes", 0)

    room[
        "train_commute_minutes"
    ] = train_minutes

    room[
        "transfers"
    ] = commute.get(
        "transfers"
    )

    room[
        "direct_train"
    ] = commute.get(
        "direct"
    )

    room[
        "total_commute_minutes"
    ] = planning
    room["typical_commute_minutes"] = total
    room["planning_commute_minutes"] = planning

    room[
        "commute_source"
    ] = commute.get(
        "source"
    )
    room["primary_station"] = commute.get("station", station)
    room["listing_station_walk_minutes"] = commute.get("listing_station_walk_minutes", room.get("station_walk_minutes"))
    room["station_walk_minutes"] = walk_minutes
    room["station_walk_distance_m"] = commute.get("station_walk_distance_m")
    room["station_walk_source"] = commute.get("station_walk_source", "listing")
    room["destination_walk_minutes"] = office_walk
    room["destination_walk_source"] = office_source
    room["commute_destination"] = destination["name"]
    room["commute_confidence"] = "medium" if commute.get("source") == "local_station_table" else "high"

    return room
