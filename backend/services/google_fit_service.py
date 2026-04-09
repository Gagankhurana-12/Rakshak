import httpx
import time
import asyncio
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select
from db.models import User
from config import settings
from fastapi import HTTPException

FIT_BASE = "https://www.googleapis.com/fitness/v1/users/me"

class GoogleFitService:
    @staticmethod
    async def ensure_token(user: User, db_session: Session) -> str:
        """Ensure token is valid, refresh if expired."""
        if not user.access_token or not user.refresh_token:
             raise HTTPException(status_code=401, detail="Authentication required")
        
        # Buffer 1 min
        if user.token_expiry and datetime.now() < user.token_expiry.replace(tzinfo=None):
            return user.access_token

        # Refresh
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://oauth2.googleapis.com/token", data={
                "client_id":     settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": user.refresh_token,
                "grant_type":    "refresh_token",
            })
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Token refresh failed")
            
            data = resp.json()
            user.access_token = data["access_token"]
            user.token_expiry = datetime.fromtimestamp(time.time() + data.get("expires_in", 3600))
            db_session.add(user)
            await db_session.commit()
            return user.access_token

    @staticmethod
    async def fetch_aggregated(user: User, db_session: Session, data_type: str, start_ms: int, end_ms: int, data_source_id: str = None) -> dict:
        access_token = await GoogleFitService.ensure_token(user, db_session)
        headers = {"Authorization": f"Bearer {access_token}"}
        
        body = {
            "aggregateBy": [{"dataTypeName": data_type}],
            "bucketByTime": {"durationMillis": 86400000},
            "startTimeMillis": start_ms,
            "endTimeMillis": end_ms,
        }
        if data_source_id:
            body["aggregateBy"][0]["dataSourceId"] = data_source_id

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{FIT_BASE}/dataset:aggregate", json=body, headers=headers)
            resp.raise_for_status()
        return resp.json()

    @staticmethod
    async def fetch_raw_dataset(user: User, db_session: Session, data_source_id: str, start_ns: str, end_ns: str) -> dict:
        access_token = await GoogleFitService.ensure_token(user, db_session)
        headers = {"Authorization": f"Bearer {access_token}"}
        dataset_id = f"{start_ns}-{end_ns}"
        url = f"{FIT_BASE}/dataSources/{data_source_id}/datasets/{dataset_id}"
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        return resp.json()

    @staticmethod
    async def fetch_sessions(user: User, db_session: Session, start_iso: str, end_iso: str, activity_type: int = None) -> list:
        access_token = await GoogleFitService.ensure_token(user, db_session)
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"startTime": start_iso, "endTime": end_iso}
        if activity_type:
            params["activityType"] = activity_type

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{FIT_BASE}/sessions", headers=headers, params=params)
            resp.raise_for_status()
        return resp.json().get("session", [])
