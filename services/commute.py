from services.transit import (
    get_transit_route,
)


def enrich_commute(
    room,
    destination="Futako-Tamagawa",
):
    station = room.get(
        "primary_station"
    )

    commute = get_transit_route(
        station,
        destination,
    )

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

    walk_minutes = (
        room.get(
            "station_walk_minutes"
        )
        or 0
    )

    bus_minutes = (
        room.get(
            "bus_minutes"
        )
        or 0
    )

    total = (
        walk_minutes
        + bus_minutes
        + train_minutes
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

    return room
