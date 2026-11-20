import json
from pathlib import Path


def test_manifest_is_phase_one_domain():
    manifest = json.loads(Path("custom_components/smart_notification_manager/manifest.json").read_text())
    assert manifest["domain"] == "smart_notification_manager"
    assert manifest["version"] == "0.1.0-beta.5"
    assert manifest["config_flow"] is True


def test_all_json_files_are_valid():
    for path in Path("custom_components/smart_notification_manager").rglob("*.json"):
        json.loads(path.read_text())
