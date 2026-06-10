import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
import importlib

mod = importlib.import_module("160")
analyze_calendar = mod.analyze_calendar


def test_analyze_calendar_tracks_density_metrics():
    meetings = [
        {"start": "2026-06-08T10:00:00", "end": "2026-06-08T11:00:00"},
        {"start": "2026-06-08T11:00:00", "end": "2026-06-08T12:30:00"},
        {"start": "2026-06-08T15:00:00", "end": "2026-06-08T16:00:00"},
        {"start": "2026-06-09T09:30:00", "end": "2026-06-09T10:00:00"},
        {"start": "2026-06-09T13:00:00", "end": "2026-06-09T14:00:00"},
    ]

    result = analyze_calendar(meetings)

    assert result["meetings_per_day"] == {
        "2026-06-08": 3,
        "2026-06-09": 2,
    }
    assert result["total_meeting_hours_per_week"] == 5.0
    assert result["deep_work_block_count"] == 3
    assert result["back_to_back_meetings_count"] == 1


def test_analyze_calendar_rejects_invalid_meeting_ranges():
    meetings = [{"start": "2026-06-08T10:00:00", "end": "2026-06-08T10:00:00"}]

    try:
        analyze_calendar(meetings)
    except ValueError as exc:
        assert "meeting end must be after start" in str(exc)
    else:
        raise AssertionError("ValueError was not raised for invalid meeting range")
