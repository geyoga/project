from services.storage import (
    make_listing_id,
)


DEFAULT_MIN_SCORE = 70


def format_yen(value):
    if value is None:
        return "Unknown"

    return (
        f"¥{value:,}"
    )


def build_new_alert(room):
    score = (
        room.get(
            "score"
        )
    )

    initial_cost = (
        room.get(
            "initial_cost"
        )
        or {}
    )

    foreigner = (
        room.get(
            "foreigner_friendly"
        )
        or {}
    )

    lines = [
        "🏠 NEW APARTMENT",
        "",
        (
            f'{room.get("property") or "Unknown property"} '
            f'{room.get("room") or ""}'
        ).strip(),
        "",
        (
            f'{room.get("layout") or "?"} · '
            f'{room.get("area_m2") or "?"}m² · '
            f'{room.get("floor") or "?"}'
        ),
        (
            "Monthly: "
            + format_yen(
                room.get(
                    "monthly_total"
                )
            )
        ),
    ]

    estimated_initial = (
        initial_cost.get(
            "estimated_total"
        )
    )

    if estimated_initial is not None:
        lines.append(
            "Initial cost est.: "
            + format_yen(
                estimated_initial
            )
        )

    commute = (
        room.get(
            "total_commute_minutes"
        )
    )

    if commute is not None:
        lines.append(
            f"Commute: {commute} min"
        )

    building_age = (
        room.get(
            "building_age_estimate_years"
        )
    )

    if building_age is not None:
        lines.append(
            f"Building age: {building_age} years"
        )

    structure = (
        room.get(
            "structure"
        )
    )

    if structure:
        lines.append(
            f"Structure: {structure}"
        )

    foreigner_status = (
        foreigner.get(
            "status"
        )
    )

    if foreigner_status:
        lines.append(
            "Foreigner friendly: "
            f"{foreigner_status}"
        )

    lines.extend(
        [
            "",
            f"Score: {score}/100",
        ]
    )

    source_url = (
        room.get(
            "source_url"
        )
    )

    if source_url:
        lines.extend(
            [
                "",
                source_url,
            ]
        )

    return "\n".join(
        lines
    )


def build_price_alert(
    room,
    change,
):
    old_price = (
        change.get(
            "previous_monthly_total"
        )
    )

    new_price = (
        change.get(
            "monthly_total"
        )
    )

    difference = None

    if (
        old_price is not None
        and new_price is not None
    ):
        difference = (
            new_price
            - old_price
        )

    lines = [
        "💴 PRICE CHANGE",
        "",
        (
            f'{room.get("property") or "Unknown property"} '
            f'{room.get("room") or ""}'
        ).strip(),
        "",
        (
            f"{format_yen(old_price)} "
            "→ "
            f"{format_yen(new_price)}"
        ),
    ]

    if difference is not None:
        if difference < 0:
            lines.append(
                "Price drop: "
                + format_yen(
                    abs(
                        difference
                    )
                )
            )

        elif difference > 0:
            lines.append(
                "Price increase: "
                + format_yen(
                    difference
                )
            )

    lines.append(
        f'Score: {room.get("score")}/100'
    )

    source_url = (
        room.get(
            "source_url"
        )
    )

    if source_url:
        lines.extend(
            [
                "",
                source_url,
            ]
        )

    return "\n".join(
        lines
    )


def build_returned_alert(room):
    lines = [
        "🔄 APARTMENT RETURNED",
        "",
        (
            f'{room.get("property") or "Unknown property"} '
            f'{room.get("room") or ""}'
        ).strip(),
        (
            "Monthly: "
            + format_yen(
                room.get(
                    "monthly_total"
                )
            )
        ),
        (
            f'Score: '
            f'{room.get("score")}/100'
        ),
    ]

    source_url = (
        room.get(
            "source_url"
        )
    )

    if source_url:
        lines.extend(
            [
                "",
                source_url,
            ]
        )

    return "\n".join(
        lines
    )


def build_notifications(
    changes,
    observed_rooms,
    min_score=DEFAULT_MIN_SCORE,
):
    notifications = []

    # --------------------------------------------------------
    # Build room lookup
    # --------------------------------------------------------

    sorted_rooms = sorted(
        observed_rooms,
        key=lambda room: (
            -(
                room.get(
                    "score"
                )
                or 0
            )
        ),
    )

    rooms_by_id = {
        make_listing_id(
            room
        ): room

        for room in sorted_rooms
    }

    # Keep only one "new listing" notification per probable
    # physical apartment.
    seen_new_fingerprints = set()

    # --------------------------------------------------------
    # Process changes
    # --------------------------------------------------------

    for change in changes:
        change_type = (
            change.get(
                "type"
            )
        )

        listing_id = (
            change.get(
                "listing_id"
            )
        )

        # Removed listings are not currently part of the
        # observed room set.
        if change_type == "removed":
            continue

        room = (
            rooms_by_id.get(
                listing_id
            )
        )

        if room is None:
            continue

        score = (
            room.get(
                "score"
            )
            or 0
        )

        fingerprint = (
            change.get(
                "listing_fingerprint"
            )
            or room.get(
                "listing_fingerprint"
            )
        )

        # ----------------------------------------------------
        # New
        # ----------------------------------------------------

        if change_type == "new":
            if score < min_score:
                continue

            if fingerprint:
                if (
                    fingerprint
                    in seen_new_fingerprints
                ):
                    continue

                seen_new_fingerprints.add(
                    fingerprint
                )

            notifications.append(
                {
                    "type":
                        "new",

                    "listing_id":
                        listing_id,

                    "listing_fingerprint":
                        fingerprint,

                    "score":
                        score,

                    "message":
                        build_new_alert(
                            room
                        ),
                }
            )

        # ----------------------------------------------------
        # Price change
        # ----------------------------------------------------

        elif (
            change_type
            == "price_changed"
        ):
            old_price = (
                change.get(
                    "previous_monthly_total"
                )
            )

            new_price = (
                change.get(
                    "monthly_total"
                )
            )

            is_drop = (
                old_price is not None
                and new_price is not None
                and new_price < old_price
            )

            if (
                not is_drop
                and score < min_score
            ):
                continue

            notifications.append(
                {
                    "type":
                        "price_changed",

                    "listing_id":
                        listing_id,

                    "listing_fingerprint":
                        fingerprint,

                    "score":
                        score,

                    "message":
                        build_price_alert(
                            room,
                            change,
                        ),
                }
            )

        # ----------------------------------------------------
        # Returned
        # ----------------------------------------------------

        elif (
            change_type
            == "returned"
        ):
            if score < min_score:
                continue

            notifications.append(
                {
                    "type":
                        "returned",

                    "listing_id":
                        listing_id,

                    "listing_fingerprint":
                        fingerprint,

                    "score":
                        score,

                    "message":
                        build_returned_alert(
                            room
                        ),
                }
            )

    notifications.sort(
        key=lambda item: (
            -item.get(
                "score",
                0,
            )
        )
    )

    return notifications