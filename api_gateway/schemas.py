from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from enum import Enum

class UserBase(BaseModel):
    """Base user schema."""
    username: str
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    """User creation schema."""
    password: str

class UserUpdate(BaseModel):
    """User update schema."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None

class User(UserBase):
    """User schema."""
    id: int
    disabled: bool = False
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True

class Token(BaseModel):
    """Token schema."""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Token data schema."""
    username: Optional[str] = None

class AgentBase(BaseModel):
    """Base agent schema."""
    name: str
    agent_type: str
    status: str = "inactive"
    config: dict = Field(default_factory=dict)

class AgentCreate(AgentBase):
    """Agent creation schema."""
    pass

class AgentUpdate(BaseModel):
    """Agent update schema."""
    status: Optional[str] = None
    config: Optional[dict] = None

class Agent(AgentBase):
    """Agent schema."""
    id: int
    created_at: str
    updated_at: str

    class Config:
        orm_mode = True

class TaskBase(BaseModel):
    """Base task schema."""
    name: str
    description: Optional[str] = None
    priority: int = 1
    status: str = "pending"
    agent_id: int

class TaskCreate(TaskBase):
    """Task creation schema."""
    pass

class TaskUpdate(BaseModel):
    """Task update schema."""
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None

class Task(TaskBase):
    """Task schema."""
    id: int
    created_at: str
    updated_at: str

    class Config:
        orm_mode = True

class MessageBase(BaseModel):
    """Base message schema."""
    content: str
    sender_id: int
    receiver_id: int
    message_type: str = "text"

class MessageCreate(MessageBase):
    """Message creation schema."""
    pass

class Message(MessageBase):
    """Message schema."""
    id: int
    created_at: str
    read: bool = False

    class Config:
        orm_mode = True

class SystemStatus(BaseModel):
    """System status schema."""
    status: str
    version: str
    services: dict
    metrics: Optional[dict] = None

class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str
    code: Optional[str] = None
    timestamp: str

class PaginatedResponse(BaseModel):
    """Paginated response schema."""
    items: List[BaseModel]
    total: int
    page: int
    size: int
    pages: int

class AgentRequest(BaseModel):
    """Request model for agent execution."""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=1, ge=1, le=10)
    timeout: Optional[int] = Field(default=None, ge=1)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)

class AgentResponse(BaseModel):
    """Response model for agent execution."""
    status: str
    agent_name: str
    result: Dict[str, Any]
    execution_time: Optional[float] = None
    error: Optional[str] = None

class TaskStatus(str, Enum):
    """Task status enumeration."""
    CREATED = "created"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskRequest(BaseModel):
    """Request model for task creation."""
    name: str
    description: Optional[str] = None
    agent_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=1, ge=1, le=10)
    dependencies: Optional[List[str]] = Field(default_factory=list)
    timeout: Optional[int] = Field(default=None, ge=1)

class TaskResponse(BaseModel):
    """Response model for task operations."""
    task_id: str
    status: TaskStatus
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ComponentStatus(str, Enum):
    """Component status enumeration."""
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    ERROR = "error"

class SystemStatus(BaseModel):
    """System status model."""
    status: ComponentStatus
    components: Dict[str, Any]
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0.0"

class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
    code: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class HealthCheck(BaseModel):
    """Health check response model."""
    status: str
    version: str
    components: Dict[str, str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AgentStatus(BaseModel):
    name: str
    status: str
    type: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class AgentConfig(BaseModel):
    name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    priority: int = Field(default=1, ge=1, le=10)
    timeout: Optional[int] = Field(default=None, ge=1)
    max_concurrent_tasks: int = Field(default=1, ge=1)
    retry_count: int = Field(default=3, ge=0)
    retry_delay: int = Field(default=5, ge=1)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat()) 