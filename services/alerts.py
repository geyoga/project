from services.storage import make_listing_id


DEFAULT_MIN_SCORE = 70


def format_yen(value):
    if value is None:
        return "Unknown"

    return f"¥{value:,}"


def find_room(
    listing_id,
    rooms,
):
    for room in rooms:
        if (
            make_listing_id(room)
            == listing_id
        ):
            return room

    return None


def build_new_alert(room):
    score = room.get(
        "score"
    )

    initial_cost = (
        room.get("initial_cost")
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
            f'{room.get("property")} '
            f'{room.get("room")}'
        ),
        "",
        (
            f'{room.get("layout")} · '
            f'{room.get("area_m2")}m² · '
            f'{room.get("floor")}'
        ),
        (
            "Monthly: "
            + format_yen(
                room.get(
                    "monthly_total"
                )
            )
        ),
        (
            "Initial cost est.: "
            + format_yen(
                initial_cost.get(
                    "estimated_total"
                )
            )
        ),
        (
            "Commute: "
            f'{room.get("total_commute_minutes")} min'
        ),
        (
            "Building age: "
            f'{room.get("building_age_estimate_years")} years'
        ),
        (
            "Structure: "
            f'{room.get("structure")}'
        ),
        (
            "Foreigner friendly: "
            f'{foreigner.get("status", "unknown")}'
        ),
        "",
        f"Score: {score}/100",
    ]

    source_url = room.get(
        "source_url"
    )

    if source_url:
        lines.extend(
            [
                "",
                source_url,
            ]
        )

    return "\n".join(lines)


def build_price_alert(
    room,
    change,
):
    old_price = change.get(
        "previous_monthly_total"
    )

    new_price = change.get(
        "monthly_total"
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
            f'{room.get("property")} '
            f'{room.get("room")}'
        ),
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
                    abs(difference)
                )
            )

        elif difference > 0:
            lines.append(
                "Price increase: "
                + format_yen(
                    difference
                )
            )

    lines.extend(
        [
            f'Score: {room.get("score")}/100',
            "",
            room.get(
                "source_url"
            )
            or "",
        ]
    )

    return "\n".join(
        line
        for line in lines
        if line is not None
    )


def build_returned_alert(room):
    return "\n".join(
        [
            "🔄 APARTMENT RETURNED",
            "",
            (
                f'{room.get("property")} '
                f'{room.get("room")}'
            ),
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
            "",
            room.get(
                "source_url"
            )
            or "",
        ]
    )


def build_notifications(
    changes,
    observed_rooms,
    min_score=DEFAULT_MIN_SCORE,
):
    notifications = []

    for change in changes:
        change_type = change.get(
            "type"
        )

        listing_id = change.get(
            "listing_id"
        )

        room = find_room(
            listing_id,
            observed_rooms,
        )

        # Removed listings are not present
        # in today's observed_rooms.
        if change_type == "removed":
            continue

        if room is None:
            continue

        score = (
            room.get("score")
            or 0
        )

        if change_type == "new":
            if score < min_score:
                continue

            notifications.append(
                {
                    "type":
                        "new",

                    "listing_id":
                        listing_id,

                    "score":
                        score,

                    "message":
                        build_new_alert(
                            room
                        ),
                }
            )

        elif change_type == "price_changed":
            old_price = change.get(
                "previous_monthly_total"
            )

            new_price = change.get(
                "monthly_total"
            )

            # Notify price decreases.
            # For increases, only notify
            # strong candidates.
            is_drop = (
                old_price is not None
                and new_price is not None
                and new_price < old_price
            )

            if (
                not is_drop
                and score
                < min_score
            ):
                continue

            notifications.append(
                {
                    "type":
                        "price_changed",

                    "listing_id":
                        listing_id,

                    "score":
                        score,

                    "message":
                        build_price_alert(
                            room,
                            change,
                        ),
                }
            )

        elif change_type == "returned":
            if score < min_score:
                continue

            notifications.append(
                {
                    "type":
                        "returned",

                    "listing_id":
                        listing_id,

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