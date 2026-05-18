
# K16: Concurrent-Spawn-Mutex (fcntl-based, Trinity-CONSERVATIVE 2026-05-17)
def k16_lock_or_exit(df_name: str):
    """Acquire exclusive lock or exit(3). Prevents concurrent DF runs."""
    import fcntl, os, sys
    lock_path = f"/tmp/df-trinity-{df_name}.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        sys.exit(3)


# K13: External-Anchor-Mock-RFC3161 (Trinity-CONSERVATIVE 2026-05-17)
def k13_anchor(payload_hash: str) -> dict:
    """Mock RFC3161-style timestamp anchor."""
    from datetime import datetime, timezone
    return {
        "anchor_type": "rfc3161-mock",
        "iso_ts": datetime.now(timezone.utc).isoformat(),
        "payload_hash": payload_hash,
    }


# K12: HMAC-SHA256-Provenance (Trinity-CONSERVATIVE 2026-05-17)
def k12_provenance(payload: bytes, key: bytes = b"df-trinity-conservative-v1") -> dict:
    """Returns payload_hash + HMAC-SHA256 signature."""
    import hashlib, hmac
    return {
        "payload_hash": hashlib.sha256(payload).hexdigest(),
        "hmac_sha256": hmac.new(key, payload, hashlib.sha256).hexdigest(),
    }

"""DF-160 OPS-Calendar-Density-Monitor engine."""

import re
import os
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime, timezone

DF_DIR = Path(__file__).parent
LOCK_DIR = Path("/tmp/df-160.lock")
DF_ID = "160"
DECISION_KEYWORDS_REGEX = re.compile(
    r"\b(entscheid[a-z]*|empfehl(?:e|en|t|st)|sollt(?:e|en|est)|recommend[a-z]*|decid[a-z]*|advis[a-z]*|propos[a-z]*)\b",
    re.IGNORECASE,
)


@dataclass
class TrackerOutput:
    welle: str = "25"
    df: str = "DF-160"
    iso_timestamp: str = ""
    source: str = "mock"
    meetings_per_day_avg: float = 0
    total_meeting_hours_per_week: float = 0
    focus_time_pct: float = 0
    back_to_back_meetings: int = 0
    declined_meetings: int = 0
    _meta: dict = field(default_factory=dict, repr=False)


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _file_stable(path, min_age_sec=300) -> bool:
    p = Path(path)
    if not p.exists():
        return False
    try:
        return (time.time() - p.stat().st_mtime) >= min_age_sec
    except OSError:
        return False


def acquire_lock_with_identity() -> bool:
    stale_after_sec = 6 * 60 * 60
    now = time.time()

    try:
        LOCK_DIR.mkdir(mode=0o700)
        _write_lock_identity()
        return True
    except FileExistsError:
        pass
    except OSError:
        return False

    try:
        age = now - LOCK_DIR.stat().st_mtime
        if age > stale_after_sec:
            for child in LOCK_DIR.iterdir():
                if child.is_file() or child.is_symlink():
                    child.unlink()
            LOCK_DIR.rmdir()
            LOCK_DIR.mkdir(mode=0o700)
            _write_lock_identity()
            return True
    except OSError:
        return False

    return False


def _write_lock_identity() -> None:
    identity = {
        "df": f"DF-{DF_ID}",
        "pid": os.getpid(),
        "created_at": iso_now(),
        "cwd": os.getcwd(),
    }
    path = LOCK_DIR / "identity.json"
    path.write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")


def release_lock() -> None:
    try:
        if LOCK_DIR.exists():
            for child in LOCK_DIR.iterdir():
                if child.is_file() or child.is_symlink():
                    child.unlink()
            LOCK_DIR.rmdir()
    except OSError:
        return


def k17_pre_action_verification(anchors) -> dict:
    missing = []
    for anchor in anchors or []:
        if anchor is None:
            missing.append("<none>")
            continue
        value = str(anchor)
        if value.startswith("env:"):
            name = value.split(":", 1)[1]
            if not os.getenv(name):
                missing.append(value)
            continue
        if not Path(value).exists():
            missing.append(value)

    env_tag = os.getenv("DF_160_ENV_TAG", "local")
    return {
        "ok": len(missing) == 0,
        "missing_anchors": missing,
        "env_tag": env_tag,
    }


def _is_real_api_enabled() -> bool:
    value = os.getenv("DF_160_REAL_API_ENABLED", "false").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def scan_output_for_decision_keywords(text) -> list:
    if text is None:
        return []
    seen = []
    for match in DECISION_KEYWORDS_REGEX.finditer(str(text)):
        token = match.group(0)
        if token.lower() not in {item.lower() for item in seen}:
            seen.append(token)
    return seen


def assert_no_decision_keywords(output) -> None:
    hits = scan_output_for_decision_keywords(output)
    if hits:
        raise ValueError("Q_0/K_0 keyword lock violation: " + ", ".join(hits))


def collect_tracker_output() -> TrackerOutput:
    output = TrackerOutput()
    output.iso_timestamp = iso_now()

    if _is_real_api_enabled():
        output.source = "real_api_unconfigured"
        output._meta = {
            "real_api_enabled": True,
            "status": "no_connector_configured",
        }
        return output

    output.source = "mock"
    output.meetings_per_day_avg = _env_float("DF_160_MOCK_MEETINGS_PER_DAY_AVG", 3.2)
    output.total_meeting_hours_per_week = _env_float("DF_160_MOCK_TOTAL_MEETING_HOURS_PER_WEEK", 16.0)
    output.focus_time_pct = _env_float("DF_160_MOCK_FOCUS_TIME_PCT", 42.5)
    output.back_to_back_meetings = _env_int("DF_160_MOCK_BACK_TO_BACK_MEETINGS", 5)
    output.declined_meetings = _env_int("DF_160_MOCK_DECLINED_MEETINGS", 2)
    output._meta = {"mock_default": True}
    return output


def _env_float(name, default) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return float(default)
    try:
        return float(raw)
    except ValueError:
        return float(default)


def _env_int(name, default) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return int(default)
    try:
        return int(raw)
    except ValueError:
        return int(default)


def _report_payload(tracker: TrackerOutput, pav: dict) -> dict:
    payload = asdict(tracker)
    meta = payload.pop("_meta", {}) or {}
    payload["k17_pre_action_verification"] = pav
    payload["meta"] = meta
    return payload


def main() -> int:
    if not acquire_lock_with_identity():
        return 3

    try:
        pav = k17_pre_action_verification([DF_DIR])
        if not pav.get("ok"):
            return 3

        tracker = collect_tracker_output()
        payload = _report_payload(tracker, pav)
        rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        assert_no_decision_keywords(rendered)

        reports_dir = DF_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        date_part = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report_path = reports_dir / f"df-160-{date_part}.json"
        report_path.write_text(rendered + "\n", encoding="utf-8")
        return 0
    except Exception as exc:
        sys.stderr.write(f"DF-160 failed: {exc}\n")
        return 3
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())