"""End-to-end tests on a tiny synthetic transit network (no internet needed).

Network: B --07:30--> A --08:00--> S(site) 08:40     (t1, weekday)
         S 17:10 --> A 17:40 --> B 18:10             (t3, weekday)
         S 23:50 --> A 24:20                         (t2, weekday, after midnight)
Tract 1 sits at stop A, tract 2 at stop B, tract 3 has no stop.
"""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_index  # noqa: E402
from app import granite  # noqa: E402
from app.engine import Network, Rules, fmt_time  # noqa: E402

SITE = (42.33, -83.05)
FIX = ROOT / "tests" / "fixtures"


@pytest.fixture(scope="module")
def net(tmp_path_factory):
    raw = tmp_path_factory.mktemp("raw")
    build = tmp_path_factory.mktemp("build")
    shutil.copytree(FIX / "mini_gtfs", raw / "mini_gtfs")
    shutil.copy(FIX / "tracts.geojson", raw / "tracts.geojson")
    shutil.copy(FIX / "acs_b25044.json", raw / "acs_b25044.json")
    build_index.build(raw, build, feeds=[("TEST", "mini_gtfs")])
    return Network(build)


def status(net, reach, tract_idx, start, end):
    a, b = net.tract_status(reach["tracts"].get(tract_idx, {}), start, end, Rules())
    return bool(a), bool(b)


def test_build_counts(net):
    assert len(net.tracts) == 3
    assert net.zero_car_total == 100 + 50 + 30
    assert set(net.stop_tract["tract_idx"]) == {0, 1}  # tract 3 has no stop within walking distance


def test_day_shift_round_trip(net):
    r = net.reach(*SITE, "weekday")
    assert status(net, r, 0, 9 * 60, 17 * 60) == (True, True)
    assert status(net, r, 1, 9 * 60, 17 * 60) == (True, True)
    ev = net.evaluate(r, 9 * 60, 17 * 60)
    assert ev["zero_car_hh_round_trip"] == 150
    assert ev["pct_round_trip"] == round(100 * 150 / 180, 1)


def test_late_shift_strands_tract_2(net):
    r = net.reach(*SITE, "weekday")
    # 9:00-23:30: tract 1 has the 23:50 bus home, tract 2 does not
    assert status(net, r, 0, 540, 1410) == (True, True)
    assert status(net, r, 1, 540, 1410) == (True, False)
    ev = net.evaluate(r, 540, 1410)
    assert ev["stranded_hh"] == 50
    assert ev["last_bus_home"]["leave_min"] == 23 * 60 + 49  # 23:50 minus the ~1 min walk to the stop


def test_no_bus_home_at_nine_pm(net):
    r = net.reach(*SITE, "weekday")
    ev = net.evaluate(r, 540, 21 * 60)
    assert ev["zero_car_hh_round_trip"] == 0
    best = net.best_end_time(r, 540, 21 * 60, window_min=240)  # 17:00 end catches the 17:10 bus
    assert best is not None and best["zero_car_hh_round_trip"] > 0


def test_arrival_window(net):
    r = net.reach(*SITE, "weekday")
    # bus arrives ~8:40; a 12:00 start is more than 60 min after arrival -> not usable
    assert status(net, r, 0, 12 * 60, 20 * 60)[0] is False


def test_interpolated_saturday_times(net):
    r = net.reach(*SITE, "saturday")
    # s1 has a blank time at B that must be interpolated (10:30) so tract 2 can ride to the site
    assert r["tracts"].get(1, {}).get("in")


def test_overnight_wrap(net):
    r = net.reach(*SITE, "weekday")
    ev = net.evaluate(r, 16 * 60, 30)  # 4 PM to 12:30 AM: end wraps to next day
    assert ev["end_min"] == 1440 + 30
    assert fmt_time(1440 + 30) == "12:30 AM"


def test_number_verifier():
    facts = {"pct_round_trip": "38.5%", "zero_car_hh_round_trip": "1,204", "last_bus_home": "DDOT 16 leaving 11:42 PM"}
    ok, bad = granite.verify_numbers("1,204 households (38.5%) can ride; last bus 11:42 PM.", facts)
    assert ok and not bad
    ok, bad = granite.verify_numbers("About 1,300 households can ride.", facts)
    assert not ok and bad == ["1300"]


def test_mock_parser():
    p = granite.mock_parse("Location: Van Born Rd & Middlebelt Rd, Romulus, MI\n2nd shift: 3:00 PM - 11:30 PM, rotating Saturdays")
    assert p.address.startswith("Van Born")
    assert p.shifts[0].start == "15:00" and p.shifts[0].end == "23:30"
    assert any("rotating" in n for n in p.notes)
