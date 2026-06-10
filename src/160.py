from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, List, Dict, Any


@dataclass(frozen=True)
class Meeting:
    start: datetime
    end: datetime

    @property
    def duration_hours(self) -> float:
        delta = self.end - self.start
        return delta.total_seconds() / 3600.0


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def normalize_meetings(meetings: Iterable[Dict[str, str]]) -> List[Meeting]:
    normalized = []
    for item in meetings:
        start = _parse_dt(item["start"])
        end = _parse_dt(item["end"])
        if end <= start:
            raise ValueError("meeting end must be after start")
        normalized.append(Meeting(start=start, end=end))
    return sorted(normalized, key=lambda m: m.start)


def analyze_calendar(
    meetings: Iterable[Dict[str, str]],
    deep_work_threshold_hours: float = 2.0,
    back_to_back_gap_minutes: int = 0,
    workday_start_hour: int = 9,
    workday_end_hour: int = 17,
) -> Dict[str, Any]:
    items = normalize_meetings(meetings)
    by_day: Dict[str, List[Meeting]] = {}

    for meeting in items:
        day = meeting.start.date().isoformat()
        by_day.setdefault(day, []).append(meeting)

    meetings_per_day = {day: len(day_meetings) for day, day_meetings in by_day.items()}
    total_meeting_hours_per_week = round(sum(m.duration_hours for m in items), 2)

    deep_work_block_count = 0
    back_to_back_meetings_count = 0
    gap_limit = timedelta(minutes=back_to_back_gap_minutes)

    for day, day_meetings in by_day.items():
        day_meetings.sort(key=lambda m: m.start)

        work_start = datetime.combine(day_meetings[0].start.date(), datetime.min.time()).replace(
            hour=workday_start_hour
        )
        work_end = datetime.combine(day_meetings[0].start.date(), datetime.min.time()).replace(
            hour=workday_end_hour
        )

        cursor = work_start
        for idx, meeting in enumerate(day_meetings):
            if meeting.start > cursor:
                gap_hours = (meeting.start - cursor).total_seconds() / 3600.0
                if gap_hours >= deep_work_threshold_hours:
                    deep_work_block_count += 1

            cursor = max(cursor, meeting.end)

            if idx < len(day_meetings) - 1:
                gap = day_meetings[idx + 1].start - meeting.end
                if gap <= gap_limit:
                    back_to_back_meetings_count += 1

        if work_end > cursor:
            gap_hours = (work_end - cursor).total_seconds() / 3600.0
            if gap_hours >= deep_work_threshold_hours:
                deep_work_block_count += 1

    return {
        "meetings_per_day": meetings_per_day,
        "total_meeting_hours_per_week": total_meeting_hours_per_week,
        "deep_work_block_count": deep_work_block_count,
        "back_to_back_meetings_count": back_to_back_meetings_count,
    }
# [CRUX-MK]
