import json
import argparse

from config import CONFIG_DIR, DATA_DIR
from crawlers.ur import crawl_areas
from services.pipeline import enrich_and_rank

from services.alerts import (
    build_notifications,
)

from services.storage import (
    initialize_database,
    start_crawl_run,
    finish_crawl_run,
    save_observed_listings,
    enqueue_notifications,
    get_pending_notifications,
    mark_notifications_delivered,
)

CONFIG_PATH = (
    CONFIG_DIR / "search_profile.json"
)

PROPERTY_METADATA_PATH = (
    DATA_DIR / "property_metadata.json"
)


# ============================================================
# LOADERS
# ============================================================


def load_profile():
    with open(
        CONFIG_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def load_property_metadata():
    if not (
        PROPERTY_METADATA_PATH
        .exists()
    ):
        return {}

    with open(
        PROPERTY_METADATA_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


# ============================================================
# PIPELINE
# ============================================================


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--alerts-only",
        action="store_true",
        help="Print pending apartment alerts",
    )

    parser.add_argument(
        "--mark-alerts-delivered",
        nargs="+",
        type=int,
        metavar="ID",
        help="Mark specific notification IDs as delivered",
    )

    return parser.parse_args()

# ============================================================
# MAIN
# ============================================================


def main():
    args = parse_args()

    initialize_database()

    if args.mark_alerts_delivered:
        count = mark_notifications_delivered(
            args.mark_alerts_delivered
        )

        print(
            f"MARKED_DELIVERED={count}"
        )

        return

    profile = load_profile()

    property_metadata = (
        load_property_metadata()
    )

    area_codes = profile.get(
        "ur_area_codes",
        [],
    )

    run_id = start_crawl_run(len(area_codes))

    if not area_codes:
        pending_notifications = get_pending_notifications()
        if args.alerts_only:
            if not pending_notifications:
                print("NO_ALERTS")
                return

            for index, notification in enumerate(
                pending_notifications
            ):
                if index > 0:
                    print(
                        "\n"
                        "--------------------"
                        "\n"
                    )

                print(
                    notification[
                        "message"
                    ]
                )

            return


        print(json.dumps({
            "profile": profile,
            "stats": {
                "areas_requested": 0,
                "areas_failed": 0,
                "rooms_found": 0,
                "rooms_matching": 0,
                "changes": 0,
                "notifications_created": 0,
                "notifications_pending": len(pending_notifications),
            },
            "matches": [],
            "pending_notifications": pending_notifications,
        }, ensure_ascii=False, indent=2))

        return


    all_rooms, crawl_errors = crawl_areas(area_codes)

    observed_rooms, matches = enrich_and_rank(
        all_rooms,
        property_metadata,
        profile,
    )

    database_changes = (
        save_observed_listings(
            run_id,
            observed_rooms,

            # Very important:
            # don't mark listings removed when
            # part of the crawl failed.
            mark_missing_inactive=(
                len(crawl_errors) == 0
                and len(observed_rooms) > 0
            ),
        )
    )

    notifications = build_notifications(
        database_changes,
        observed_rooms,
        min_score=70,
    )

    enqueue_notifications(
        run_id,
        notifications,
    )

    pending_notifications = (
        get_pending_notifications()
    )

    finish_crawl_run(
        run_id=run_id,

        areas_failed=len(
            crawl_errors
        ),

        rooms_found=len(
            all_rooms
        ),

        rooms_matching=len(
            matches
        ),

        crawl_errors=crawl_errors,
    )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    if args.alerts_only:
        if not pending_notifications:
            print("NO_ALERTS")
            return

        for index, notification in enumerate(
            pending_notifications
        ):
            if index > 0:
                print(
                    "\n"
                    "--------------------"
                    "\n"
                )

            print(
                f"[ALERT_ID={notification['id']}]"
            )

            print(
                notification["message"]
            )

        return

    output = {
        "profile": profile,

        "stats": {
            "areas_requested":
                len(area_codes),

            "areas_failed":
                len(crawl_errors),

            "rooms_found":
                len(all_rooms),

            "rooms_matching":
                len(matches),

            "changes":
                len(database_changes),

            "notifications_created":
                len(notifications),

            "notifications_pending":
                len(pending_notifications),
        },

        "crawl_errors":
            crawl_errors,

        "changes":
            database_changes,

        "notifications":
            notifications,

        "matches":
            matches,

        "notifications":
            notifications,

        "pending_notifications":
            pending_notifications,
    }

    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
