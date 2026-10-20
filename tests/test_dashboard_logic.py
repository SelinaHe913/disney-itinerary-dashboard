from __future__ import annotations

from datetime import date
import unittest

import numpy as np
import pandas as pd

import dashboard


class QueueSenseLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reference, cls.rides = dashboard.load_data()

    def test_default_four_day_route_is_generated(self) -> None:
        dates = [pd.Timestamp(date(2026, 11, 2)) + pd.Timedelta(days=offset) for offset in range(4)]
        route = dashboard.propose_route(
            self.reference,
            dates,
            dashboard.PARKS,
            set(),
            "One Park Per Day",
        )
        self.assertIsNotNone(route)
        self.assertEqual(len(route), 4)
        self.assertEqual({park for _, _, park in route}, set(dashboard.PARKS))

    def test_infeasible_must_do_park_combination_is_rejected(self) -> None:
        route = dashboard.propose_route(
            self.reference,
            [pd.Timestamp("2026-11-02")],
            dashboard.PARKS,
            {"Magic Kingdom", "Epcot"},
            "One Park Per Day",
        )
        self.assertIsNone(route)

    def test_park_day_and_ticket_changes_rebuild_route_without_hopper_duplicates(self) -> None:
        dates = [pd.Timestamp("2026-11-02")]
        one_park = dashboard.propose_route(
            self.reference,
            dates,
            ["Magic Kingdom", "Epcot"],
            set(),
            "One Park Per Day",
        )
        self.assertIsNotNone(one_park)
        self.assertEqual(len(one_park), 1)

        hopper = dashboard.propose_route(
            self.reference,
            dates,
            ["Magic Kingdom", "Epcot"],
            {"Magic Kingdom", "Epcot"},
            "Park Hopper",
        )
        self.assertIsNotNone(hopper)
        self.assertEqual(len(hopper), 2)
        self.assertFalse(dashboard.has_duplicate_hopper_parks(hopper))
        self.assertTrue(
            dashboard.has_duplicate_hopper_parks(
                [(1, dates[0], "Epcot"), (1, dates[0], "Epcot")]
            )
        )

    def test_coverage_is_explicitly_park_level_and_updates_after_edit(self) -> None:
        lookup = {
            "Ride A": {"park_name": "Magic Kingdom"},
            "Ride B": {"park_name": "Epcot"},
        }
        route = pd.DataFrame({"park": ["Magic Kingdom"]})
        self.assertEqual(dashboard.must_do_coverage(route, ["Ride A", "Ride B"], lookup), (1, "1 / 2"))
        edited = pd.DataFrame({"park": ["Magic Kingdom", "Epcot"]})
        self.assertEqual(dashboard.must_do_coverage(edited, ["Ride A", "Ride B"], lookup), (2, "2 / 2"))
        self.assertEqual(dashboard.must_do_coverage(edited, [], lookup), (0, "None selected"))

    def test_relaxed_pace_never_truncates_must_dos(self) -> None:
        rows = []
        for index in range(5):
            rows.append(
                {
                    "park_name": "Magic Kingdom",
                    "ride_name": f"Must {index}",
                    "option": f"Must {index} · Magic Kingdom",
                    "minutes": 60 - index,
                    "ll_class": "multi_pass",
                }
            )
        for index in range(4):
            rows.append(
                {
                    "park_name": "Magic Kingdom",
                    "ride_name": f"Extra {index}",
                    "option": f"Extra {index} · Magic Kingdom",
                    "minutes": 40 - index,
                    "ll_class": "none",
                }
            )
        rides = pd.DataFrame(rows)
        must_options = [row["option"] for row in rows[:5]]

        priorities, backup = dashboard.attraction_priorities(
            rides,
            "Magic Kingdom",
            must_options,
            "Relaxed",
        )

        self.assertEqual(sum(bool(item["is_must"]) for item in priorities), 5)
        self.assertEqual(sum(not bool(item["is_must"]) for item in priorities), 2)
        names = [str(item["ride_name"]) for item in priorities]
        self.assertEqual(len(names), len(set(names)))
        self.assertIsNotNone(backup)
        self.assertNotIn(str(backup["ride_name"]), names)

        next_priorities, next_backup = dashboard.attraction_priorities(
            rides,
            "Magic Kingdom",
            must_options,
            "Relaxed",
            excluded_names=set(names) | {str(backup["ride_name"])},
            include_must=False,
        )
        next_names = [str(item["ride_name"]) for item in next_priorities]
        if next_backup:
            next_names.append(str(next_backup["ride_name"]))
        self.assertTrue(set(names).isdisjoint(next_names))
        self.assertNotIn(str(backup["ride_name"]), next_names)

    def test_live_summary_distinguishes_missing_zero_partial_and_no_open(self) -> None:
        now = pd.Timestamp("2026-10-20T16:00:00Z")
        partial = pd.DataFrame(
            {
                "park": ["Magic Kingdom", "Magic Kingdom", "Epcot"],
                "ride": ["Missing", "Walk-on", "Closed"],
                "is_open": [True, True, False],
                "wait_minutes": [np.nan, 0.0, np.nan],
                "updated": pd.to_datetime(["2026-10-20T15:58:00Z"] * 3, utc=True),
            }
        )
        summary = dashboard.summarise_live_snapshot(partial, now=now)
        self.assertEqual(summary["status"], "partial")
        self.assertIn("0 min median", summary["title"])
        self.assertIn("1/2 open attractions with reported waits", summary["note"])

        no_open = partial.assign(is_open=False)
        no_open_summary = dashboard.summarise_live_snapshot(no_open, now=now)
        self.assertIn("No open attractions reported", no_open_summary["title"])
        self.assertNotIn("0 min median", no_open_summary["title"])

        unavailable = dashboard.summarise_live_snapshot(pd.DataFrame(), now=now)
        self.assertEqual(unavailable["status"], "unavailable")
        self.assertIn("Historical planning remains available", unavailable["note"])

        full = pd.DataFrame(
            {
                "park": dashboard.PARKS,
                "ride": [f"Ride {index}" for index in range(4)],
                "is_open": [True] * 4,
                "wait_minutes": [0.0, 10.0, 20.0, 30.0],
                "updated": pd.to_datetime(["2026-10-20T15:59:00Z"] * 4, utc=True),
            }
        )
        full_summary = dashboard.summarise_live_snapshot(full, now=now)
        self.assertEqual(full_summary["status"], "fresh")
        self.assertIn("4/4 parks", full_summary["note"])

        stale = full.assign(updated=pd.to_datetime(["2026-10-20T15:40:00Z"] * 4, utc=True))
        stale_summary = dashboard.summarise_live_snapshot(stale, now=now)
        self.assertEqual(stale_summary["status"], "stale")
        self.assertIn("Stale (>15 min)", stale_summary["note"])


if __name__ == "__main__":
    unittest.main()
