"""Project Settings: Analyze in UTM (saved with the project, used by the terrain tools)."""
API = "/api/v1"

from tests.conftest import make_hill
from shared.layer_store import add_raster_layer


def _layer(client_hill=None):
    return add_raster_layer(make_hill(), "hill").id


def test_defaults_and_partial_update(client):
    s = client.get(f"{API}/file/project/settings").json()
    assert (s["analyze_in_utm"], s["utm_zone"], s["resampling"]) == (False, "auto", "bilinear")
    r = client.put(f"{API}/file/project/settings", json={"analyze_in_utm": True})
    assert r.json()["analyze_in_utm"] is True and r.json()["resampling"] == "bilinear"    # others unchanged


def test_bad_zone_and_resampling_rejected(client):
    assert client.put(f"{API}/file/project/settings", json={"utm_zone": "99N"}).status_code == 422
    assert client.put(f"{API}/file/project/settings", json={"utm_zone": "43X"}).status_code == 422
    assert client.put(f"{API}/file/project/settings", json={"resampling": "lanczos"}).status_code == 422


def test_changing_a_setting_marks_project_unsaved(client):
    client.post(f"{API}/file/project/new", json={"name": "p"})
    assert client.get(f"{API}/file/project").json()["dirty"] is False
    client.put(f"{API}/file/project/settings", json={"analyze_in_utm": True})
    assert client.get(f"{API}/file/project").json()["dirty"] is True


def test_utm_preview_picks_zone_from_the_data(client):
    lid = _layer()                                  # hill at lon 73, lat 33.5 -> UTM 43N
    p = client.get(f"{API}/file/project/settings/utm-preview", params={"layer_id": lid}).json()
    assert p == {"applies": True, "zone": "43N", "epsg": 32643, "reason": None}
    client.put(f"{API}/file/project/settings", json={"utm_zone": "42N"})
    assert client.get(f"{API}/file/project/settings/utm-preview", params={"layer_id": lid}).json()["zone"] == "42N"


def test_slope_runs_in_utm_when_switched_on(client):
    lid = _layer()
    off = client.post(f"{API}/analysis/surface-analysis/slope", json={"layer_id": lid, "units": "degrees"})
    client.put(f"{API}/file/project/settings", json={"analyze_in_utm": True})
    on = client.post(f"{API}/analysis/surface-analysis/slope", json={"layer_id": lid, "units": "degrees"})
    assert off.status_code == 200 and on.status_code == 200, on.text
    assert off.json()["layer"]["crs"] == "EPSG:4326"
    lay = on.json()["layer"]
    assert lay["crs"] == "EPSG:32643" and lay["meta"]["analysis_utm"]["zone"] == "43N"
    assert "UTM 43N" in lay["name"]
    # same terrain, so the two slopes agree closely on average (different grids, so not cell for cell)
    a, b = off.json()["statistics"]["mean"], on.json()["statistics"]["mean"]
    assert abs(a - b) < 0.15 * a


def test_projected_layer_is_left_alone(client):
    lid = add_raster_layer(make_hill(geographic=False), "utm hill").id
    client.put(f"{API}/file/project/settings", json={"analyze_in_utm": True})
    p = client.get(f"{API}/file/project/settings/utm-preview", params={"layer_id": lid}).json()
    assert p["applies"] is False
    r = client.post(f"{API}/analysis/surface-analysis/slope", json={"layer_id": lid, "units": "degrees"}).json()
    assert r["layer"]["crs"] == "EPSG:32643" and "analysis_utm" not in r["layer"]["meta"]


def test_settings_are_saved_and_reopened(client, tmp_path):
    client.put(f"{API}/file/project/settings", json={"analyze_in_utm": True, "utm_zone": "43n", "resampling": "cubic"})
    path = str(tmp_path / "p.gtm")
    assert client.post(f"{API}/file/project/save-as", json={"path": path}).status_code == 200
    client.post(f"{API}/file/project/new", json={"name": "other"})
    assert client.get(f"{API}/file/project/settings").json()["analyze_in_utm"] is False       # a new project starts at defaults
    client.post(f"{API}/file/project/open", json={"path": path})
    back = client.get(f"{API}/file/project/settings").json()
    assert (back["analyze_in_utm"], back["utm_zone"], back["resampling"]) == (True, "43N", "cubic")


def test_no_utm_beyond_84_north(client):
    r = make_hill(origin=(10.0, 86.0))
    lid = add_raster_layer(r, "arctic").id
    client.put(f"{API}/file/project/settings", json={"analyze_in_utm": True})
    resp = client.post(f"{API}/analysis/surface-analysis/slope", json={"layer_id": lid, "units": "degrees"})
    assert resp.status_code == 400 and "84" in resp.text


def test_all_setting_groups_have_defaults_and_validate(client):
    s = client.get(f"{API}/file/project/settings").json()
    assert s["distance_unit"] == "metres" and s["slope_unit"] == "degrees" and s["decimal_places"] == 4
    assert s["hillshade_azimuth"] == 315 and s["contour_interval"] == 100 and s["auto_save_minutes"] == 0
    r = client.put(f"{API}/file/project/settings",
                   json={"slope_unit": "percent", "area_unit": "acres", "decimal_places": 2, "author": "Asif"})
    assert r.status_code == 200 and r.json()["slope_unit"] == "percent" and r.json()["decimal_places"] == 2
    assert client.get(f"{API}/file/project/settings").json()["author"] == "Asif"
    for bad in ({"decimal_places": 9}, {"slope_unit": "radians"}, {"hillshade_altitude": 95},
                {"contour_interval": 0}, {"auto_save_minutes": 7}):
        assert client.put(f"{API}/file/project/settings", json=bad).status_code == 422
