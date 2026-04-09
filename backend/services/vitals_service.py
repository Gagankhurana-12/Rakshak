from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from db.models import UserVitals


@dataclass
class VitalsPoint:
    date: datetime
    avg_heart_rate: float | None = None
    steps: int | None = None
    sleep_hours: float | None = None
    calories: float | None = None
    distance: float | None = None


class VitalsService:
    """Builds personalized vitals context for Rakshak."""

    @staticmethod
    def _average(values: list[float | int | None]) -> float | None:
        clean = [float(value) for value in values if value is not None]
        if not clean:
            return None
        return round(sum(clean) / len(clean), 2)

    @staticmethod
    def _normalize_rows(rows: list[UserVitals]) -> list[VitalsPoint]:
        return [
            VitalsPoint(
                date=row.date,
                avg_heart_rate=row.avg_heart_rate,
                steps=row.steps,
                sleep_hours=row.sleep_hours,
                calories=row.calories,
                distance=row.distance,
            )
            for row in rows
        ]

    @staticmethod
    def _build_summary(user_name: str, recent_points: list[VitalsPoint], baseline_points: list[VitalsPoint]) -> tuple[str, dict[str, Any]]:
        recent_hr = [point.avg_heart_rate for point in recent_points]
        recent_sleep = [point.sleep_hours for point in recent_points]
        recent_steps = [point.steps for point in recent_points]
        recent_calories = [point.calories for point in recent_points]
        recent_distance = [point.distance for point in recent_points]

        baseline_hr = [point.avg_heart_rate for point in baseline_points]
        baseline_sleep = [point.sleep_hours for point in baseline_points]
        baseline_steps = [point.steps for point in baseline_points]
        baseline_calories = [point.calories for point in baseline_points]

        averages = {
            "heart_rate": VitalsService._average(recent_hr),
            "sleep_hours": VitalsService._average(recent_sleep),
            "steps": VitalsService._average(recent_steps),
            "calories": VitalsService._average(recent_calories),
            "distance": VitalsService._average(recent_distance),
        }

        baseline = {
            "heart_rate": VitalsService._average(baseline_hr),
            "sleep_hours": VitalsService._average(baseline_sleep),
            "steps": VitalsService._average(baseline_steps),
            "calories": VitalsService._average(baseline_calories),
        }

        anomalies: list[dict[str, str]] = []

        max_hr = max([value for value in recent_hr if value is not None], default=None)
        if max_hr is not None and max_hr > 120:
            anomalies.append({
                "type": "high_heart_rate",
                "severity": "alert",
                "message": f"Heart rate peaked at {round(max_hr)} bpm, above the 120 bpm alert threshold.",
            })

        low_sleep_days = len([value for value in recent_sleep if value is not None and value < 5])
        if low_sleep_days > 0:
            anomalies.append({
                "type": "low_sleep",
                "severity": "warning",
                "message": f"Sleep was below 5 hours on {low_sleep_days} day(s) in the recent period.",
            })

        hr_sentence = ""
        if averages["heart_rate"] is not None:
            if baseline["heart_rate"] is not None and averages["heart_rate"] > baseline["heart_rate"]:
                hr_sentence = (
                    f"Your average heart rate is {round(averages['heart_rate'])} bpm, "
                    f"which is higher than your usual {round(baseline['heart_rate'])} bpm."
                )
            elif baseline["heart_rate"] is not None:
                hr_sentence = (
                    f"Your average heart rate is {round(averages['heart_rate'])} bpm, "
                    f"which is within your usual range."
                )

        sleep_sentence = ""
        if averages["sleep_hours"] is not None:
            if low_sleep_days >= 3:
                sleep_sentence = (
                    f"You have been sleeping {averages['sleep_hours']} hours/night, below your normal {round(baseline['sleep_hours']) if baseline['sleep_hours'] else 'baseline'} hours. "
                    f"This has been consistent for {low_sleep_days} days."
                )
            else:
                sleep_sentence = f"Your average sleep is {averages['sleep_hours']} hours/night."

        activity_sentence = ""
        if averages["steps"] is not None:
            activity_sentence = f"You are averaging {int(averages['steps'])} steps per day."

        if averages["calories"] is not None:
            activity_sentence = f"{activity_sentence} You are burning about {int(averages['calories'])} calories per day.".strip()

        summary_parts = [part for part in [hr_sentence, sleep_sentence, activity_sentence] if part]
        if anomalies:
            summary_parts.append(" ".join([item["message"] for item in anomalies]))

        summary = " ".join(summary_parts).strip()
        if not summary:
            summary = f"{user_name}, I do not have enough data to generate a personalized vitals summary yet."

        return summary, {
            "averages": averages,
            "baseline": baseline,
            "anomalies": anomalies,
            "low_sleep_days": low_sleep_days,
        }

    @staticmethod
    async def build_vitals_context(user_id: str, db_session: AsyncSession, user_name: str = "You") -> str:
        """Return a natural-language summary of the last 7 days compared to a 30-day baseline."""
        stmt = (
            select(UserVitals)
            .where(UserVitals.user_id == user_id)
            .order_by(UserVitals.date.desc())
            .limit(30)
        )
        rows = (await db_session.execute(stmt)).scalars().all()

        if rows:
            points = list(reversed(VitalsService._normalize_rows(rows)))
        else:
            return (
                f"{user_name}, no vitals data is available yet. Sync Google Fit to personalize the analysis."
            )

        recent_points = points[-7:]
        baseline_points = points[-30:]
        summary, _ = VitalsService._build_summary(user_name, recent_points, baseline_points)
        return summary

    @staticmethod
    async def build_vitals_bundle(user_id: str, db_session: AsyncSession, user_name: str = "You") -> dict[str, Any]:
        """Return structured vitals data for the analyze pipeline."""
        stmt = (
            select(UserVitals)
            .where(UserVitals.user_id == user_id)
            .order_by(UserVitals.date.desc())
            .limit(30)
        )
        rows = (await db_session.execute(stmt)).scalars().all()

        if rows:
            points = list(reversed(VitalsService._normalize_rows(rows)))
            source = "database"
        else:
            points = []
            source = "none"

        recent_points = points[-7:]
        baseline_points = points[-30:]
        summary, metrics = VitalsService._build_summary(user_name, recent_points, baseline_points)

        return {
            "user_id": user_id,
            "user_name": user_name,
            "source": source,
            "summary": summary,
            "metrics": metrics,
            "recent_points": [point.__dict__ for point in recent_points],
            "baseline_points": [point.__dict__ for point in baseline_points],
        }
