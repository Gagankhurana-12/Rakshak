import os
import time
import sys
import json
# Quiet down TensorFlow logs
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
import base64
import httpx
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlencode
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Depends, Header
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import asyncio
if sys.platform == 'win32' and sys.version_info < (3, 14):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from db.database import init_db, get_session
from db.models import User, UploadedDocument, UserVitals
from sqlmodel import select
from schemas import AnalyzeRequest
from services.analyze_service import AnalyzeService
from services.sync_service import sync_service
from services.vitals_service import VitalsService
from services.document_service import document_service
from services.llm_service import llm_service
from rag.pinecone_client import rag_service

import jwt
from datetime import datetime, timedelta, timezone

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET", "rakshak_secret_key_demo")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "refresh": True})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except:
        return None

import bcrypt

# Setup password hashing directly with bcrypt
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

class SignupRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure vectors directory exists and DB is ready
    print("Starting Rakshak Backend...")
    print(f"OAuth redirect URI: {REDIRECT_URI}")
    os.makedirs("vectors", exist_ok=True)
    await init_db()
    print("Web Server Ready (AI models will load on first query)")
    yield


app = FastAPI(title="Rakshak — Google Fit API", lifespan=lifespan)

raw_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
cors_origins = [origin.strip() for origin in raw_cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────

CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
raw_redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:8000/exchange_token")
REDIRECT_URI = "http://localhost:8000/exchange_token" if "localhost:8080" in raw_redirect_uri else raw_redirect_uri

FIT_BASE = "https://www.googleapis.com/fitness/v1/users/me"

SCOPES = " ".join([
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/fitness.sleep.read",
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.location.read",
    "https://www.googleapis.com/auth/fitness.nutrition.read",
])

# In-memory token store (same as your Strava/JS setup)
token_store = {
    "access_token":  None,
    "refresh_token": None,
    "token_expiry":  None,   # Unix timestamp (seconds)
    "user_id":       None,
}

# Activity type codes from Google Fit
ACTIVITY_TYPES = {
    7: "Walk", 8: "Run", 9: "Jog", 15: "Cycling", 17: "Swimming",
    21: "Football", 26: "Hiking", 37: "Yoga", 45: "Strength training",
    72: "Sleep", 108: "Meditation",
}

# ─── HELPERS ──────────────────────────────────────────────────────────────────

async def ensure_valid_token():
    """Refresh access token 60s before expiry; restore from DB if missing."""
    global token_store
    
    # 1. If in-memory is empty, try restoring from DB
    if not token_store["access_token"]:
        from db.database import engine
        from sqlalchemy.ext.asyncio import AsyncSession
        async with AsyncSession(engine, expire_on_commit=False) as session:
            statement = select(User)
            if token_store.get("user_id"):
                statement = statement.where(User.id == token_store["user_id"])
            else:
                statement = statement.limit(1)
            result = await session.execute(statement)
            db_user = result.scalar_one_or_none()
            if db_user and db_user.access_token:
                token_store["access_token"]  = db_user.access_token
                token_store["refresh_token"] = db_user.refresh_token
                token_store["token_expiry"]  = db_user.token_expiry.timestamp() if db_user.token_expiry else 0
                token_store["user_id"]       = db_user.id
                print(f"✅ Tokens restored from DB for: {db_user.email}")

    if not token_store["access_token"]:
        raise HTTPException(status_code=401, detail="Not authenticated. Visit /auth first.")

    # 2. Check expiry
    buffer = 60  # seconds
    if time.time() < token_store["token_expiry"] - buffer:
        return  # still valid

    # 3. Refresh if needed
    if not token_store["refresh_token"]:
         raise HTTPException(status_code=401, detail="Refresh token missing. Please re-sync.")

    async with httpx.AsyncClient() as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": token_store["refresh_token"],
            "grant_type":    "refresh_token",
        })
        
        if resp.status_code != 200:
             raise HTTPException(status_code=401, detail="Failed to refresh token")

        data = resp.json()

    # 4. Update memory and DB
    token_store["access_token"] = data["access_token"]
    token_store["token_expiry"] = time.time() + data["expires_in"]
    
    from db.database import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(engine, expire_on_commit=False) as session:
        statement = select(User).where(User.refresh_token == token_store["refresh_token"])
        result = await session.execute(statement)
        db_user = result.scalar_one_or_none()
        if db_user:
            db_user.access_token = data["access_token"]
            db_user.token_expiry = datetime.fromtimestamp(time.time() + data["expires_in"], tz=timezone.utc).replace(tzinfo=None)
            session.add(db_user)
            await session.commit()
    
    print("🔄 Access token refreshed and persisted to DB")


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {token_store['access_token']}"}


def extract_google_user_id(user_info: dict) -> str | None:
    return user_info.get("sub") or user_info.get("id") or user_info.get("email")


def _decode_jwt_payload(jwt_token: str) -> dict:
    """Decode JWT payload without verification for non-sensitive profile extraction."""
    try:
        payload = jwt_token.split(".")[1]
        padding = "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload + padding)
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return {}


def time_range_ns(days: int = 7) -> dict:
    """
    Returns start/end as both milliseconds and nanoseconds.
    Aligned to IST (GMT+5:30) midnight to ensure consistent 24h bucketing.
    """
    from datetime import datetime, timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(IST)
    
    # Calculate midnight IST today
    midnight_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Go back X-1 days to get X full days
    start_ist = midnight_ist - timedelta(days=days-1)
    
    start_ms = int(start_ist.timestamp() * 1000)
    end_ms = int(now_ist.timestamp() * 1000)
    
    return {
        "start_ms": start_ms,
        "end_ms":   end_ms,
        "start_ns": str(start_ms * 1_000_000),
        "end_ns":   str(end_ms   * 1_000_000),
        "start_iso": start_ist.isoformat(),
        "end_iso":   now_ist.isoformat(),
    }


async def fetch_dataset(data_source_id: str, start_ns: str, end_ns: str) -> dict:
    """Fetch a raw dataset for a given data source over a nanosecond time range."""
    await ensure_valid_token()
    dataset_id = f"{start_ns}-{end_ns}"
    url = f"{FIT_BASE}/dataSources/{data_source_id}/datasets/{dataset_id}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=auth_headers())
        resp.raise_for_status()
    return resp.json()


async def aggregate(data_type_name: str, start_ms: int, end_ms: int,
                    data_source_id: str = None) -> dict:
    """Call the Aggregation API for daily bucketed data."""
    await ensure_valid_token()
    body = {
        "aggregateBy": [{"dataTypeName": data_type_name}],
        "bucketByTime": {"durationMillis": 86_400_000},  # 1 day
        "startTimeMillis": start_ms,
        "endTimeMillis":   end_ms,
    }
    if data_source_id:
        body["aggregateBy"][0]["dataSourceId"] = data_source_id

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{FIT_BASE}/dataset:aggregate",
            json=body,
            headers=auth_headers(),
        )
        resp.raise_for_status()
    return resp.json()


# ─── AUTH ROUTES ──────────────────────────────────────────────────────────────

@app.post("/signup")
async def signup(payload: SignupRequest, session: AsyncSession = Depends(get_session)):
    """Classic Email/Password Signup with deep diagnostics."""
    try:
        # Check if user exists
        statement = select(User).where(User.email == payload.email)
        results = await session.execute(statement)
        if results.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")
        
        user_id = payload.email
        hashed_pw = hash_password(payload.password)
        
        new_user = User(
            id=user_id,
            email=payload.email,
            display_name=payload.name or payload.email.split('@')[0],
            password_hash=hashed_pw,
            is_google_connected=False
        )
        session.add(new_user)
        await session.commit()
        
        access_token = create_access_token({"sub": user_id})
        refresh_token = create_refresh_token({"sub": user_id})
        
        token_store["user_id"] = user_id
        return {
            "status": "success", 
            "user_id": user_id,
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    except Exception as e:
        import traceback
        with open("debug_error.log", "w") as f:
            f.write(f"ERROR: {str(e)}\n")
            f.write(traceback.format_exc())
        print(f"❌ SIGNUP CRASHED: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login")
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)):
    """Classic Email/Password Login."""
    try:
        statement = select(User).where(User.email == payload.email)
        results = await session.execute(statement)
        user = results.scalar_one_or_none()
        
        if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        access_token = create_access_token({"sub": user.id})
        refresh_token = create_refresh_token({"sub": user.id})
        
        token_store["user_id"] = user.id
        # Also preserve Google tokens in store if they exist in DB
        if user.access_token:
            token_store["access_token"] = user.access_token
            token_store["refresh_token"] = user.refresh_token
            token_store["token_expiry"] = user.token_expiry.timestamp() if user.token_expiry else None
        
        return {
            "status": "success", 
            "user_id": user.id, 
            "is_google_connected": user.is_google_connected,
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    except Exception as e:
        import traceback
        with open("debug_error.log", "w") as f:
            f.write(f"ERROR_LOGIN: {str(e)}\n")
            f.write(traceback.format_exc())
        print(f"❌ LOGIN CRASHED: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/refresh")
async def refresh_session(refresh_token: str):
    """Issue a new access token using a valid refresh token."""
    payload = decode_token(refresh_token)
    if not payload or not payload.get("refresh"):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    user_id = payload.get("sub")
    new_access = create_access_token({"sub": user_id})
    return {"access_token": new_access}

@app.get("/auth")
def auth(next_url: str | None = None, link: bool = False, user_id: str | None = None):
    """Step 1 — redirect user to Google consent screen."""
    # Pass user_id in state so we know who to link to on return
    state_data = {
        "next": next_url or os.getenv("FRONTEND_URL", "http://localhost:5173"),
        "link": link,
        "uid": user_id or token_store.get("user_id")
    }
    params = urlencode({
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         json.dumps(state_data),
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@app.get("/exchange_token")
async def exchange_token(code: str = None, error: str = None, state: str | None = None):
    """Step 2 — Google redirects here with ?code=... after user consent."""
    if error:
        return HTMLResponse(f"<p>OAuth error: {error}</p>")
    if not code:
        return HTMLResponse("<p>No code received.</p>")

    # Parse state
    next_url = "http://localhost:5173"
    is_linking = False
    target_user_id = None
    
    if state:
        try:
            state_data = json.loads(state)
            next_url = state_data.get("next", next_url)
            is_linking = state_data.get("link", False)
            target_user_id = state_data.get("uid")
        except:
            next_url = state

    async with httpx.AsyncClient() as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "code":          code,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri":  REDIRECT_URI,
            "grant_type":    "authorization_code",
        })
        resp.raise_for_status()
        data = resp.json()
    
    try:
        user_info = _decode_jwt_payload(data.get("id_token", ""))
        google_id = extract_google_user_id(user_info)

        if not google_id:
            # Fallback for tokens issued without id_token payload
            async with httpx.AsyncClient() as client:
                user_info_resp = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {data['access_token']}"}
                )
                user_info_resp.raise_for_status()
                user_info = user_info_resp.json()
                google_id = extract_google_user_id(user_info)

        email = user_info.get("email") or f"{google_id}@google.local"
        display_name = user_info.get("name") or "Google User"

        from db.database import engine
        from sqlalchemy.ext.asyncio import AsyncSession
        
        async with AsyncSession(engine, expire_on_commit=False) as session:
            # Check if we should link to current session user
            if not target_user_id:
                target_user_id = token_store.get("user_id") if is_linking else None
            
            if target_user_id:
                statement = select(User).where(User.id == target_user_id)
            else:
                statement = select(User).where(User.id == google_id)
            
            result = await session.execute(statement)
            user = result.scalar_one_or_none()
            
            if not user:
                # Create new Google user
                user = User(
                    id=google_id,
                    email=email,
                    display_name=display_name
                )
            
            # Update tokens and status
            user.access_token = data["access_token"]
            user.refresh_token = data.get("refresh_token") or user.refresh_token
            user.token_expiry = datetime.fromtimestamp(time.time() + data["expires_in"], tz=timezone.utc).replace(tzinfo=None)
            user.is_google_connected = True
            
            session.add(user)
            await session.commit()
            
            token_store["user_id"] = user.id
            token_store["access_token"]  = user.access_token
            token_store["refresh_token"] = user.refresh_token
            
            # AUTO-SYNC: Trigger initial sync in background
            print(f"🔄 Auto-syncing vitals for {user.email}...")
            asyncio.create_task(sync_service.sync_vitals(user, session, days=7))

    except Exception as e:
        print(f"❌ AUTH ERROR: {e}")
        return RedirectResponse(f"{next_url}?status=error&message={str(e)}")

    return RedirectResponse(f"{next_url}?status=success&connected=true&uid={user.id}")


@app.get("/logout")
async def logout(authorization: str | None = Header(None)):
    """Clear active session tokens from memory and current user DB row."""
    previous_user_id = token_store.get("user_id")
    previous_refresh_token = token_store.get("refresh_token")

    # For email/password sessions, derive user id from JWT if available.
    if authorization and authorization.startswith("Bearer "):
        payload = decode_token(authorization.split(" ", 1)[1])
        if payload and payload.get("sub"):
            previous_user_id = payload.get("sub")

    # 1. Clear in-memory session state immediately.
    token_store["access_token"] = None
    token_store["refresh_token"] = None
    token_store["token_expiry"] = None
    token_store["user_id"] = None

    # 2. Clear tokens for only the active user record.
    if not previous_user_id and not previous_refresh_token:
        return {"status": "logged_out"}

    async for session in get_session():
        user = None
        if previous_user_id:
            user = (
                await session.execute(select(User).where(User.id == previous_user_id))
            ).scalar_one_or_none()

        if not user and previous_refresh_token:
            user = (
                await session.execute(
                    select(User).where(User.refresh_token == previous_refresh_token)
                )
            ).scalar_one_or_none()

        if user:
            user.access_token = None
            user.refresh_token = None
            user.token_expiry = None
            session.add(user)
            await session.commit()
        break

    return {"status": "logged_out"}


# ─── DATA ROUTES ──────────────────────────────────────────────────────────────


class DiagnoseRequest(BaseModel):
    user_id: str
    symptoms: str


def _vitals_summary_text(summary_data: dict) -> str:
    """Convert dashboard summary payload into prompt-friendly text."""
    heart_rate = summary_data.get("heart_rate") or {}
    return (
        f"Steps today: {summary_data.get('today_steps', 'N/A')}. "
        f"Daily average steps: {summary_data.get('avg_steps_daily', 'N/A')}. "
        f"Average sleep: {summary_data.get('avg_sleep_hours', 'N/A')} hours. "
        f"Average calories: {summary_data.get('avg_calories_daily', 'N/A')} kcal. "
        f"Heart rate avg/min/max: "
        f"{heart_rate.get('avg', 'N/A')}/{heart_rate.get('min', 'N/A')}/{heart_rate.get('max', 'N/A')} bpm."
    )


@app.post("/upload-doc")
async def upload_doc(user_id: str, file: UploadFile = File(...)):
    """Upload a user medical document and store chunks in Pinecone."""
    session = None
    user = None
    async for db_session in get_session():
        session = db_session
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        break

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await document_service.process_upload(user_id=user_id, file=file)

    if session:
        session.add(
            UploadedDocument(
                user_id=user_id,
                doc_name=result.get("doc_name", file.filename),
                chunks_processed=int(result.get("chunks_processed", 0) or 0),
            )
        )
        await session.commit()

    return {"user_id": user_id, **result}


@app.get("/documents")
async def documents(user_id: str):
    """Get most recent uploaded document metadata for a user."""
    async for session in get_session():
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        rows = (
            await session.execute(
                select(UploadedDocument)
                .where(UploadedDocument.user_id == user_id)
                .order_by(UploadedDocument.upload_date.desc())
                .limit(20)
            )
        ).scalars().all()
        break

    return {
        "user_id": user_id,
        "documents": [
            {
                "id": row.id,
                "doc_name": row.doc_name,
                "chunks_processed": row.chunks_processed,
                "upload_date": row.upload_date.isoformat(),
            }
            for row in rows
        ],
    }


@app.post("/diagnose")
async def diagnose(payload: DiagnoseRequest):
    """Generate diagnosis from symptoms using vitals context and RAG context."""
    symptoms = (payload.symptoms or "").strip()
    if not symptoms:
        raise HTTPException(status_code=400, detail="Symptoms are required")

    async for session in get_session():
        user = (await session.execute(select(User).where(User.id == payload.user_id))).scalar_one_or_none()
        break

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    vitals_summary = "No recent vitals could be fetched."
    try:
        vitals_summary = await VitalsService.build_vitals_context(
            user_id=payload.user_id,
            db_session=session,
            user_name=user.display_name or "You"
        )
    except Exception as exc:
        print(f"⚠️ Could not fetch vitals summary for diagnosis: {exc}")

    rag_context = {
        "disease_context": [],
        "user_docs_context": [],
        "vitals_history_context": [],
    }
    try:
        rag_context = await rag_service.retrieve_context(symptoms, payload.user_id)
    except Exception as exc:
        print(f"⚠️ Could not fetch RAG context: {exc}")

    diagnosis = await llm_service.get_diagnosis(symptoms, vitals_summary, rag_context)

    return diagnosis


@app.post("/analyze")
async def analyze(payload: AnalyzeRequest):
    """Core hackathon endpoint: combine personal vitals, history, and RAG for personalized analysis."""
    async for session in get_session():
        result = await AnalyzeService.analyze(
            query=payload.query,
            user_id=payload.user_id,
            db_session=session,
        )
        return result


@app.post("/sync-vitals")
async def sync_vitals(user_id: str, days: int = 7):
    try:
        async for session in get_session():
            user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            synced_days = await sync_service.sync_vitals(user, session, days=days)
            return {
                "user_id": user_id,
                "synced_days": synced_days,
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }
    except HTTPException:
        raise
    except (SQLAlchemyError, OSError) as exc:
        print(f"❌ DB sync error: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please retry sync in a few seconds.",
        ) from exc


@app.get("/vitals/history")
async def vitals_history(user_id: str, days: int = 7):
    async for session in get_session():
        rows = (
            await session.execute(
                select(UserVitals)
                .where(UserVitals.user_id == user_id)
                .order_by(UserVitals.date.desc())
                .limit(days)
            )
        ).scalars().all()
        break

    return {
        "user_id": user_id,
        "days": days,
        "data": [
            {
                "date": row.date.isoformat(),
                "heart_rate": row.avg_heart_rate,
                "steps": row.steps,
                "sleep_hours": row.sleep_hours,
                "calories": row.calories,
                "distance": row.distance,
            }
            for row in list(reversed(rows))
        ],
    }

@app.get("/profile")
async def profile(user_id: str | None = None, authorization: str | None = Header(None)):
    """Confirms who is authenticated and returns user info from DB."""
    try:
        uid = user_id
        
        # 1. Priority: Try to get UID from JWT Header
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            payload = decode_token(token)
            if payload:
                uid = payload.get("sub")
                print(f"✅ Authenticated via JWT: {uid}")

        # 2. Fallback: Check global token store (for existing Google sessions)
        if not uid:
            uid = token_store.get("user_id")
        
        if not uid:
             raise HTTPException(status_code=401, detail="No session found. Please login.")

        async for session in get_session():
            statement = select(User).where(User.id == uid)
            result = await session.execute(statement)
            user = result.scalar_one_or_none()

            if user:
                # Sync Google tokens to memory for this session
                if user.access_token:
                    token_store["access_token"] = user.access_token
                    token_store["refresh_token"] = user.refresh_token
                    token_store["user_id"] = user.id
                    token_store["token_expiry"] = user.token_expiry.timestamp() if user.token_expiry else None

                return {
                    "id": user.id,
                    "email": user.email,
                    "display_name": user.display_name,
                    "is_google_connected": user.is_google_connected
                }
        
        raise HTTPException(status_code=401, detail="User not found in database")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        print(f"❌ PROFILE ERROR: {e}")
        raise HTTPException(status_code=401, detail=str(e))


@app.get("/datasources")
async def datasources():
    """List all Google Fit data sources available for this user."""
    await ensure_valid_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{FIT_BASE}/dataSources", headers=auth_headers())
        resp.raise_for_status()
    return resp.json()


@app.get("/steps")
async def steps(days: int = 7):
    """Daily step counts. ?days=7 (default)"""
    t = time_range_ns(days)
    data = await aggregate(
        "com.google.step_count.delta",
        t["start_ms"], t["end_ms"],
        data_source_id="derived:com.google.step_count.delta:com.google.android.gms:estimated_steps",
    )

    result = []
    for bucket in data.get("bucket", []):
        points = bucket["dataset"][0].get("point", [])
        total  = sum(p["value"][0].get("intVal", 0) for p in points)
        result.append({
            "date":  datetime.fromtimestamp(
                int(bucket["startTimeMillis"]) / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%d"),
            "steps": total,
        })

    return {
        "days":  days,
        "data":  result,
        "total": sum(d["steps"] for d in result),
    }


@app.get("/heart-rate")
async def heart_rate(days: int = 7):
    """Raw heart rate BPM readings. ?days=7 (default)"""
    t = time_range_ns(days)
    dataset = await fetch_dataset(
        "derived:com.google.heart_rate.bpm:com.google.android.gms:merge_heart_rate_bpm",
        t["start_ns"], t["end_ns"],
    )

    readings = [
        {
            "timestamp": datetime.fromtimestamp(
                int(p["startTimeNanos"]) / 1_000_000_000, tz=timezone.utc
            ).isoformat(),
            "bpm": p["value"][0].get("fpVal"),
        }
        for p in dataset.get("point", [])
    ]

    bpms = [r["bpm"] for r in readings if r["bpm"] is not None]
    stats = None
    if bpms:
        stats = {
            "count": len(bpms),
            "avg":   round(sum(bpms) / len(bpms)),
            "min":   round(min(bpms)),
            "max":   round(max(bpms)),
        }

    return {"days": days, "stats": stats, "readings": readings}


@app.get("/sleep")
async def sleep(days: int = 7):
    """Sleep sessions. ?days=7 (default)"""
    await ensure_valid_token()
    t = time_range_ns(days)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FIT_BASE}/sessions",
            headers=auth_headers(),
            params={
                "startTime":    t["start_iso"],
                "endTime":      t["end_iso"],
                "activityType": 72,
            },
        )
        resp.raise_for_status()

    sessions = []
    for s in resp.json().get("session", []):
        duration_ms = int(s["endTimeMillis"]) - int(s["startTimeMillis"])
        sessions.append({
            "date":           datetime.fromtimestamp(
                int(s["startTimeMillis"]) / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%d"),
            "start_time":     datetime.fromtimestamp(
                int(s["startTimeMillis"]) / 1000, tz=timezone.utc
            ).isoformat(),
            "end_time":       datetime.fromtimestamp(
                int(s["endTimeMillis"]) / 1000, tz=timezone.utc
            ).isoformat(),
            "duration_hours": round(duration_ms / 3_600_000, 2),
            "name":           s.get("name"),
        })

    total_hours = sum(s["duration_hours"] for s in sessions)
    return {
        "days":                 days,
        "avg_hours_per_night":  round(total_hours / days, 2) if days else None,
        "sessions":             sessions,
    }


@app.get("/calories")
async def calories(days: int = 7):
    """Daily calories burned. ?days=7 (default)"""
    t = time_range_ns(days)
    data = await aggregate("com.google.calories.expended", t["start_ms"], t["end_ms"])

    result = [
        {
            "date": datetime.fromtimestamp(
                int(b["startTimeMillis"]) / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%d"),
            "calories": round(sum(
                p["value"][0].get("fpVal", 0)
                for p in b["dataset"][0].get("point", [])
            )),
        }
        for b in data.get("bucket", [])
    ]

    return {"days": days, "data": result}


@app.get("/distance")
async def distance(days: int = 7):
    """Daily distance in metres + km. ?days=7 (default)"""
    t = time_range_ns(days)
    data = await aggregate("com.google.distance.delta", t["start_ms"], t["end_ms"])

    result = []
    for b in data.get("bucket", []):
        metres = sum(
            p["value"][0].get("fpVal", 0)
            for p in b["dataset"][0].get("point", [])
        )
        result.append({
            "date":   datetime.fromtimestamp(
                int(b["startTimeMillis"]) / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%d"),
            "metres": round(metres),
            "km":     round(metres / 1000, 2),
        })

    return {"days": days, "data": result}


@app.get("/weight")
async def weight(days: int = 30):
    """Body weight readings in kg. ?days=30 (default)"""
    t = time_range_ns(days)
    dataset = await fetch_dataset(
        "derived:com.google.weight:com.google.android.gms:merge_weight",
        t["start_ns"], t["end_ns"],
    )

    readings = [
        {
            "timestamp": datetime.fromtimestamp(
                int(p["startTimeNanos"]) / 1_000_000_000, tz=timezone.utc
            ).isoformat(),
            "kg": round(p["value"][0].get("fpVal", 0), 1),
        }
        for p in dataset.get("point", [])
    ]

    return {"days": days, "readings": readings}


@app.get("/sessions")
async def sessions(days: int = 30):
    """All workout sessions. ?days=30 (default)"""
    await ensure_valid_token()
    t = time_range_ns(days)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FIT_BASE}/sessions",
            headers=auth_headers(),
            params={"startTime": t["start_iso"], "endTime": t["end_iso"]},
        )
        resp.raise_for_status()

    result = []
    for s in resp.json().get("session", []):
        duration_ms = int(s["endTimeMillis"]) - int(s["startTimeMillis"])
        result.append({
            "id":               s["id"],
            "name":             s.get("name"),
            "activity_type":    ACTIVITY_TYPES.get(s.get("activityType"), f"Type {s.get('activityType')}"),
            "activity_type_id": s.get("activityType"),
            "date":             datetime.fromtimestamp(
                int(s["startTimeMillis"]) / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%d"),
            "start_time":       datetime.fromtimestamp(
                int(s["startTimeMillis"]) / 1000, tz=timezone.utc
            ).isoformat(),
            "end_time":         datetime.fromtimestamp(
                int(s["endTimeMillis"]) / 1000, tz=timezone.utc
            ).isoformat(),
            "duration_minutes": round(duration_ms / 60_000),
        })

    return {"days": days, "count": len(result), "sessions": result}


@app.get("/summary")
async def summary(days: int = 7):
    """
    Fetches real-time and historical data from Google Fit for the dashboard.
    """
    await ensure_valid_token()
    t = time_range_ns(days)

    # 1. Broad aggregation (no specific dataSourceId to catch all devices)
    results = await asyncio.gather(
        aggregate("com.google.step_count.delta", t["start_ms"], t["end_ms"]),
        aggregate("com.google.calories.expended", t["start_ms"], t["end_ms"]),
        aggregate("com.google.distance.delta", t["start_ms"], t["end_ms"]),
        # Heart rate usually needs at least one valid source; we'll try raw BPM then fallback
        fetch_dataset(
            "derived:com.google.heart_rate.bpm:com.google.android.gms:merge_heart_rate_bpm",
            t["start_ns"], t["end_ns"],
        ),
        _fetch_sleep_sessions(t),
        return_exceptions=True,
    )

    steps_data, cal_data, dist_data, hr_data, sleep_data = results

    # Helper to calculate daily average from buckets
    def get_avg_val(agg_resp, field="intVal"):
        if isinstance(agg_resp, Exception) or not agg_resp: return None
        daily = [
            sum(p["value"][0].get(field, 0) for p in b["dataset"][0].get("point", []))
            for b in agg_resp.get("bucket", [])
        ]
        return round(sum(daily) / len(daily)) if daily else 0

    avg_steps = get_avg_val(steps_data, "intVal")
    avg_calories = get_avg_val(cal_data, "fpVal")
    avg_distance_km = round((get_avg_val(dist_data, "fpVal") or 0) / 1000, 2)

    # Today's steps (last bucket)
    today_steps = 0
    if not isinstance(steps_data, Exception) and steps_data.get("bucket"):
        last_bucket = steps_data["bucket"][-1]
        today_steps = sum(p["value"][0].get("intVal", 0) for p in last_bucket["dataset"][0].get("point", []))

    # Heart rate processing
    hr_stats = None
    if not isinstance(hr_data, Exception) and hr_data:
        bpms = [p["value"][0].get("fpVal") for p in hr_data.get("point", []) if p.get("value")]
        if bpms:
            hr_stats = {
                "avg": round(sum(bpms) / len(bpms)),
                "min": round(min(bpms)),
                "max": round(max(bpms)),
                "latest": round(bpms[-1])
            }

    # Sleep processing
    avg_sleep_hours = 0
    if not isinstance(sleep_data, Exception) and sleep_data:
        total = sum((int(s["endTimeMillis"]) - int(s["startTimeMillis"])) / 3_600_000 for s in sleep_data)
        avg_sleep_hours = round(total / days, 1)

    return {
        "period_days": days,
        "avg_steps_daily": avg_steps,
        "today_steps": today_steps,
        "avg_calories_daily": avg_calories,
        "avg_distance_km": avg_distance_km,
        "heart_rate": hr_stats,
        "avg_sleep_hours": avg_sleep_hours,
        "rakshak_context": f"Steps Today: {today_steps}, Avg HR: {hr_stats['avg'] if hr_stats else 'N/A'}, Sleep: {avg_sleep_hours}h"
    }


async def _fetch_sleep_sessions(t: dict) -> list:
    """Helper used inside summary() to fetch sleep sessions."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FIT_BASE}/sessions",
            headers=auth_headers(),
            params={
                "startTime":    t["start_iso"],
                "endTime":      t["end_iso"],
                "activityType": 72,
            },
        )
        resp.raise_for_status()
    return resp.json().get("session", [])


# ─── START ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import socket
    import uvicorn

    host = "0.0.0.0"
    port = 8000

    # Avoid Windows bind errors when a previous backend instance is already running.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            print(f"Rakshak backend already running on http://127.0.0.1:{port}")
            sys.exit(0)

    uvicorn.run("main:app", host=host, port=port, reload=False)