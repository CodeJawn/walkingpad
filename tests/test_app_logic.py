import importlib
import importlib.util
from pathlib import Path
import sys
from unittest.mock import patch

import pytest


def _load_app_module():
    # Import app.py without actually starting the BLE thread.
    module_name = "app"
    if module_name in sys.modules:
        del sys.modules[module_name]

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load app module spec")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    with patch("threading.Thread.start", lambda self: None):
        spec.loader.exec_module(module)

    return module


@pytest.fixture(scope="module")
def app_module():
    return _load_app_module()


@pytest.fixture(autouse=True)
def reset_runtime_state(app_module):
    app_module.belt_running = False
    app_module._auto_pause_grace_until = 0
    app_module.current_speed_kmh = 0.0
    app_module.current_distance_km = 0.0
    app_module.current_steps = 0
    app_module.current_calories = 0.0
    app_module._last_dev_dist = 0
    app_module._last_dev_steps = 0
    app_module.speed_history.clear()


def test_format_seconds_to_hms(app_module):
    assert app_module.format_seconds_to_hms(0) == "0:00:00"
    assert app_module.format_seconds_to_hms(59) == "0:00:59"
    assert app_module.format_seconds_to_hms(3661) == "1:01:01"


def test_next_speed_target_metric_steps(app_module):
    app_module.current_speed_kmh = 2.1
    with app_module.app.test_request_context("/increase_speed?units=metric"):
        assert app_module._next_speed_target_kmh(1) == pytest.approx(2.5)

    with app_module.app.test_request_context("/decrease_speed?units=metric"):
        assert app_module._next_speed_target_kmh(-1) == pytest.approx(1.5)


def test_next_speed_target_imperial_steps(app_module):
    app_module.current_speed_kmh = 4.1
    with app_module.app.test_request_context("/increase_speed?units=imperial"):
        next_kmh = app_module._next_speed_target_kmh(1)

    expected_kmh = 3.0 / app_module.KMH_TO_MPH
    assert next_kmh == pytest.approx(expected_kmh, rel=1e-6)


def test_next_speed_target_clamps_to_limits(app_module):
    app_module.current_speed_kmh = 5.9
    with app_module.app.test_request_context("/increase_speed?units=metric"):
        assert app_module._next_speed_target_kmh(1) == pytest.approx(app_module.MAX_SPEED_KMH)

    app_module.current_speed_kmh = app_module.MIN_SPEED_KMH
    with app_module.app.test_request_context("/decrease_speed?units=metric"):
        assert app_module._next_speed_target_kmh(-1) == pytest.approx(app_module.MIN_SPEED_KMH)


def test_process_status_packet_ignores_negative_distance_delta(app_module):
    app_module.process_status_packet(dev_dist=10, dev_steps=5, dev_speed=20)
    assert app_module.current_distance_km == pytest.approx(0.1)
    assert app_module._last_dev_dist == 10

    # Simulate a device distance reset/backwards jump.
    app_module.process_status_packet(dev_dist=8, dev_steps=7, dev_speed=20)

    assert app_module.current_distance_km == pytest.approx(0.1)
    assert app_module._last_dev_dist == 8
    assert app_module.current_steps == 7


def test_stats_json_reports_metric_distance(app_module):
    app_module.current_distance_km = 1.234
    app_module.current_speed_kmh = 2.5

    with app_module.app.test_request_context("/stats"):
        response = app_module.stats_json()

    payload = response.get_json()
    assert payload["distance"] == 1.23
    assert payload["speed"] == 2.5
