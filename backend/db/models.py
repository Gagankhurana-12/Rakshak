from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship, JSON, Column
import uuid

class User(SQLModel, table=True):
    id: str = Field(primary_key=True)  # Google sub id or email
    email: str
    password_hash: Optional[str] = None  # For simple login
    display_name: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expiry: Optional[datetime] = None
    is_google_connected: bool = Field(default=False)
    
    # Relationships
    vitals_summaries: List["VitalsDailySummary"] = Relationship(back_populates="user")
    vitals_raw: List["VitalsRaw"] = Relationship(back_populates="user")
    anomalies: List["AnomaliesLog"] = Relationship(back_populates="user")
    uploaded_documents: List["UploadedDocument"] = Relationship(back_populates="user")
    vitals_daily: List["UserVitals"] = Relationship(back_populates="user")

class VitalsDailySummary(SQLModel, table=True):
    __tablename__ = "vitals_daily_summary"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id")
    date: datetime = Field(index=True)
    avg_steps: Optional[int] = None
    avg_hr: Optional[float] = None
    min_hr: Optional[float] = None
    max_hr: Optional[float] = None
    avg_sleep_hours: Optional[float] = None
    total_calories: Optional[float] = None
    total_distance_km: Optional[float] = None
    avg_weight_kg: Optional[float] = None
    
    user: User = Relationship(back_populates="vitals_summaries")

class VitalsRaw(SQLModel, table=True):
    __tablename__ = "vitals_raw"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id")
    metric_type: str = Field(index=True) # e.g., 'heart_rate', 'steps'
    value: float
    timestamp: datetime = Field(index=True)
    metadata_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    user: User = Relationship(back_populates="vitals_raw")

class AnomaliesLog(SQLModel, table=True):
    __tablename__ = "anomalies_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id")
    anomaly_type: str # 'heart_rate_spike', 'low_sleep', etc.
    description: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    severity: str = "critical" # low, medium, high, critical
    
    user: User = Relationship(back_populates="anomalies")


class UploadedDocument(SQLModel, table=True):
    __tablename__ = "uploaded_documents"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    doc_name: str
    chunks_processed: int = 0
    upload_date: datetime = Field(default_factory=datetime.utcnow, index=True)

    user: User = Relationship(back_populates="uploaded_documents")


class UserVitals(SQLModel, table=True):
    __tablename__ = "user_vitals"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    date: datetime = Field(index=True)
    avg_heart_rate: Optional[float] = None
    steps: Optional[int] = None
    sleep_hours: Optional[float] = None
    calories: Optional[float] = None
    distance: Optional[float] = None

    user: User = Relationship(back_populates="vitals_daily")
