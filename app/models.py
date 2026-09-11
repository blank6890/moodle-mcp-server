from typing import Optional
from pydantic import BaseModel, Field

class Course(BaseModel):
    id: str
    name: str
    url: str

class Assignment(BaseModel):
    course: str
    name: str
    due_date: Optional[str] = None  # ISO 8601
    due_date_raw: str
    status: str  # "not_submitted", "submitted", "graded"
    url: str

class CalendarEvent(BaseModel):
    title: str
    date: Optional[str] = None  # ISO 8601
    date_raw: str
    course: Optional[str] = None
    event_type: str  # "assignment_due", "workshop_submission", "workshop_assessment", "course_event"
    url: Optional[str] = None

class Announcement(BaseModel):
    course: str
    title: str
    content_preview: str
    author: str
    date: Optional[str] = None  # ISO 8601
    date_raw: str
    url: str

class Resource(BaseModel):
    name: str
    url: Optional[str] = None
    resource_type: Optional[str] = None  # "pdf", "link", "file", "folder"

class Section(BaseModel):
    title: str
    resources: list[Resource] = Field(default_factory=list)

class CourseDetail(BaseModel):
    id: str
    name: str
    url: str
    sections: list[Section] = Field(default_factory=list)

class Participant(BaseModel):
    name: str
    role: str  # "student", "teacher", "admin"
    profile_url: Optional[str] = None

class Grade(BaseModel):
    course: str
    item_name: str
    max_points: Optional[float] = None
    earned_points: Optional[float] = None
    percentage: Optional[float] = None
    status: str  # "completed", "pending", "not_graded"

class Workshop(BaseModel):
    name: str
    course: str
    phase: str  # "setup", "submission", "assessment", "closed"
    submission_deadline: Optional[str] = None
    assessment_deadline: Optional[str] = None
    status: str
    url: str

class SessionStatus(BaseModel):
    authenticated: bool
    detail: str

class HealthStatus(BaseModel):
    status: str
    authenticated: bool
    uptime_seconds: float
