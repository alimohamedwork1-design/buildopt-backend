from scripts.onprem_preflight import inspect_settings

SAFE = {
    "APP_ENV": "production",
    "DEMO_MODE": "false",
    "SECRET_KEY": "l8_q75U2xHT5_V5kD3Az9fMT2KtzW7vvcLxMx0H",
    "INFLUX_ADMIN_PASSWORD": "g7K-YA8nhmV9a5B8DsWj",
    "INFLUX_TOKEN": "Zwj3gR7xYt9D5-WqeAT6bNlArQHtk7VtzV4K",
    "ALLOWED_ORIGINS": "https://build-opt.site",
    "CONTROL_WRITEBACK_ENABLED": "false",
}

def test_production_preflight_safe_configuration_is_not_site_certification():
    result = inspect_settings(SAFE)
    assert result["configuration_safe_to_attempt"] is True
    assert result["production_site_accepted"] is False
    assert result["manual_acceptance_required"]


def test_demo_and_default_weak_credentials_are_rejected():
    env = {**SAFE, "DEMO_MODE": "true", "SECRET_KEY": "change-me-in-production"}
    result = inspect_settings(env)
    assert not result["configuration_safe_to_attempt"]
    assert any("DEMO_MODE" in x for x in result["blockers"])
    assert any("SECRET_KEY" in x for x in result["blockers"])


def test_wildcard_and_insecure_origin_refused():
    assert not inspect_settings({**SAFE,"ALLOWED_ORIGINS":"*"})["configuration_safe_to_attempt"]
    assert not inspect_settings({**SAFE,"ALLOWED_ORIGINS":"http://site.local"})["configuration_safe_to_attempt"]


def test_control_writeback_cannot_be_enabled_by_preflight():
    result = inspect_settings({**SAFE, "CONTROL_WRITEBACK_ENABLED": "true"})
    assert not result["configuration_safe_to_attempt"]


def test_no_secret_values_leak_in_report():
    result = inspect_settings({**SAFE, "INFLUX_ADMIN_PASSWORD": "password"})
    assert not result["configuration_safe_to_attempt"]
    assert SAFE["SECRET_KEY"] not in str(result)
    assert SAFE["INFLUX_TOKEN"] not in str(result)
