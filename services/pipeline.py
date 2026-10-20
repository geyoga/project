from domain.listings import (
    calculate_score,
    enrich_foreigner_friendly,
    enrich_initial_cost,
    enrich_room,
    passes_hard_filters,
)
from services.commute import enrich_commute
from services.ur_property import enrich_ur_property
from services.surroundings import enrich_surroundings


def enrich_and_rank(rooms, metadata, profile):
    observed = []
    matches = []

    for room in rooms:
        room = enrich_room(room, metadata)
        if room.get("source") == "ur":
            room = enrich_ur_property(room)
        room = enrich_surroundings(room)
        room = enrich_commute(room, profile["destination"])
        if room.get("source") == "ur":
            room = enrich_initial_cost(room, profile)
        room = enrich_foreigner_friendly(room)
        room["score"] = calculate_score(room, profile)
        observed.append(room)
        if passes_hard_filters(room, profile):
            matches.append(room)

    matches.sort(key=lambda room: (
        -room["score"],
        room["monthly_total"],
        -room["area_m2"],
    ))
    return observed, matches
