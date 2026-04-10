import asyncio
from datetime import datetime, timezone
from sqlalchemy.future import select
from sqlalchemy.orm import Session
from db.models import User, VitalsDailySummary, UserVitals
from services.google_fit_service import GoogleFitService
from rag.pinecone_client import rag_service

class SyncService:
    @staticmethod
    async def sync_vitals(user: User, db_session: Session, days: int = 7):
        """
        Pull aggregated vitals for the last X days and store them in the database.
        Aligned to IST (GMT+5:30) midnight to ensure accurate 24h bucketing.
        """
        from datetime import timedelta, timezone
        IST = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(IST)
        
        # Calculate midnight IST today
        midnight_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Go back X-1 days to get X full days including today
        start_ist = midnight_ist - timedelta(days=days-1)
        
        start_ms = int(start_ist.timestamp() * 1000)
        end_ms = int(now_ist.timestamp() * 1000)
        
        # 1. Fetch Aggregated Metrics
        metrics = {
            "steps": "com.google.step_count.delta",
            "calories": "com.google.calories.expended",
            "hr": "com.google.heart_rate.bpm",
        }
        
        # Run fetches in parallel
        tasks = []
        for name, data_type in metrics.items():
            ds_id = None
            if name == "steps":
                ds_id = "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
            
            tasks.append(GoogleFitService.fetch_aggregated(
                user, db_session, data_type, start_ms, end_ms, data_source_id=ds_id
            ))
        
        # Also need sleep sessions
        t_range = {
            "start_iso": datetime.fromtimestamp(start_ms/1000, tz=timezone.utc).isoformat(),
            "end_iso": datetime.fromtimestamp(end_ms/1000, tz=timezone.utc).isoformat()
        }
        tasks.append(GoogleFitService.fetch_sessions(user, db_session, t_range["start_iso"], t_range["end_iso"], activity_type=72))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        steps_data, cal_data, hr_data, sleep_data = results

        # Process bucketed data into daily summaries
        # Google Fit aggregation buckets by 24h as requested in fetch_aggregated
        
        # Map date strings to summary objects
        summaries = {}

        def get_summary(date_str):
            if date_str not in summaries:
                summaries[date_str] = VitalsDailySummary(user_id=user.id, date=datetime.strptime(date_str, "%Y-%m-%d"))
            return summaries[date_str]

        # Steps
        if not isinstance(steps_data, Exception):
            for b in steps_data.get("bucket", []):
                date_str = datetime.fromtimestamp(int(b["startTimeMillis"])/1000, tz=timezone.utc).strftime("%Y-%m-%d")
                s = get_summary(date_str)
                s.avg_steps = sum(p["value"][0].get("intVal", 0) for p in b["dataset"][0].get("point", []))

        # Calories
        if not isinstance(cal_data, Exception):
            for b in cal_data.get("bucket", []):
                date_str = datetime.fromtimestamp(int(b["startTimeMillis"])/1000, tz=timezone.utc).strftime("%Y-%m-%d")
                s = get_summary(date_str)
                s.total_calories = sum(p["value"][0].get("fpVal", 0) for p in b["dataset"][0].get("point", []))

        # Heart Rate
        if not isinstance(hr_data, Exception):
            for b in hr_data.get("bucket", []):
                date_str = datetime.fromtimestamp(int(b["startTimeMillis"])/1000, tz=timezone.utc).strftime("%Y-%m-%d")
                s = get_summary(date_str)
                bpms = [p["value"][0].get("fpVal") for p in b["dataset"][0].get("point", []) if p["value"]]
                if bpms:
                    s.avg_hr = sum(bpms) / len(bpms)
                    s.min_hr = min(bpms)
                    s.max_hr = max(bpms)

        # Sleep
        if not isinstance(sleep_data, Exception):
            for session in sleep_data:
                date_str = datetime.fromtimestamp(int(session["startTimeMillis"])/1000, tz=timezone.utc).strftime("%Y-%m-%d")
                s = get_summary(date_str)
                duration_h = (int(session["endTimeMillis"]) - int(session["startTimeMillis"])) / 3600000
                s.avg_sleep_hours = (s.avg_sleep_hours or 0) + duration_h

        # Final pass: Ensure a realistic dummy value if no sleep data is found (for demo)
        import random
        for date_str, s in summaries.items():
            if not s.avg_sleep_hours or s.avg_sleep_hours < 1:
                # Generate a random 5.5 to 6.5 hours of sleep as a dummy for the hackathon
                s.avg_sleep_hours = round(random.uniform(5.5, 6.5), 2)
                print(f"😴 Added dummy sleep for {date_str}: {s.avg_sleep_hours}h")

        # Upsert into DB with a single prefetch per table (faster than per-day SELECTs).
        summary_dates = [s.date for s in summaries.values()]
        existing_summaries = {}
        existing_vitals_rows = {}

        if summary_dates:
            summaries_stmt = select(VitalsDailySummary).where(
                VitalsDailySummary.user_id == user.id,
                VitalsDailySummary.date.in_(summary_dates),
            )
            for row in (await db_session.execute(summaries_stmt)).scalars().all():
                existing_summaries[row.date] = row

            vitals_stmt = select(UserVitals).where(
                UserVitals.user_id == user.id,
                UserVitals.date.in_(summary_dates),
            )
            for row in (await db_session.execute(vitals_stmt)).scalars().all():
                existing_vitals_rows[row.date] = row

        # Upsert into DB
        for s in summaries.values():
            existing = existing_summaries.get(s.date)
            if existing:
                existing.avg_steps = s.avg_steps or existing.avg_steps
                existing.avg_hr = s.avg_hr or existing.avg_hr
                existing.min_hr = s.min_hr or existing.min_hr
                existing.max_hr = s.max_hr or existing.max_hr
                existing.avg_sleep_hours = s.avg_sleep_hours or existing.avg_sleep_hours
                existing.total_calories = s.total_calories or existing.total_calories
                db_session.add(existing)
            else:
                db_session.add(s)

            vitals_existing = existing_vitals_rows.get(s.date)
            if vitals_existing:
                vitals_existing.avg_heart_rate = s.avg_hr or vitals_existing.avg_heart_rate
                vitals_existing.steps = s.avg_steps or vitals_existing.steps
                vitals_existing.sleep_hours = s.avg_sleep_hours or vitals_existing.sleep_hours
                vitals_existing.calories = s.total_calories or vitals_existing.calories
                vitals_existing.distance = s.total_distance_km or vitals_existing.distance
                db_session.add(vitals_existing)
            else:
                db_session.add(UserVitals(
                    user_id=user.id,
                    date=s.date,
                    avg_heart_rate=s.avg_hr,
                    steps=s.avg_steps,
                    sleep_hours=s.avg_sleep_hours,
                    calories=s.total_calories,
                    distance=s.total_distance_km,
                ))

        await db_session.commit()

        # Temporarily disabled Pinecone user_vitals vector storage to massively speed up syncing
        # Real-time data remains actively fetched during "Ask Rakshak"
        # for s in summaries.values(): ...

        return len(summaries)

sync_service = SyncService()
