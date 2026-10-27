from services.transit import (
    get_local_route,
    get_transit_route,
)

OFFICE_WALK_MINUTES = 5


def enrich_commute(
    room,
    destination="Futako-Tamagawa",
):
    station = room.get("primary_station")
    access = room.get("access_options") or []
    candidates = access or ([{"station": station, "walk_minutes": room.get("station_walk_minutes"), "bus_minutes": room.get("bus_minutes")}] if station else [])
    routes = []
    for option in candidates:
        route = get_local_route(option.get("station"), destination)
        if route:
            route = dict(route)
            route["station"] = option["station"]
            route["station_walk_minutes"] = option.get("walk_minutes") or 0
            route["bus_minutes"] = option.get("bus_minutes") or 0
            route["total"] = route["train_minutes"] + route["station_walk_minutes"] + route["bus_minutes"]
            routes.append(route)
    commute = min(routes, key=lambda item: item["total"]) if routes else get_transit_route(station, destination)

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

        room[
            "total_commute_minutes"
        ] = None

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

    total = (
        walk_minutes
        + bus_minutes
        + train_minutes
        + OFFICE_WALK_MINUTES
    )

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
    ] = total

    room[
        "commute_source"
    ] = commute.get(
        "source"
    )
    room["primary_station"] = commute.get("station", station)
    room["destination_walk_minutes"] = OFFICE_WALK_MINUTES
    room["commute_destination"] = "Rakuten Crimson House"

    return room
