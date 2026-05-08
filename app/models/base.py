import uuid
from datetime import datetime
from sqlalchemy import DateTime,func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped,mapped_column
from app.db.session import Base

class TimestampMixin:
    """
    Adds created_at and updated_at to any model that inherits this.
    func.now() means PostgreSQL sets the value automatically —
    you never pass these manually.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(), # auto-updates on every UPDATE query
        nullable=False
    )

# Why timezone=True? Always store timestamps in UTC. Without timezone awareness, you'll hit bugs when servers in different timezones interpret the same timestamp differently.
# Store UTC, display in local time on the frontend.
# Why server_default=func.now() and not default=datetime.utcnow? server_default lets PostgreSQL set the value — it never goes through Python. 
# default=datetime.utcnow is a Python-side default which can be wrong if the server clock and DB clock differ, and famously datetime.utcnow as a default captures the time the class is defined, not when the row is inserted.