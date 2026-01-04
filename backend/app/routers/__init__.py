from .admin import router as admin
from .conditions import router as conditions
from .days import router as days
from .goals import router as goals
from .health import router as health
from .notifications import router as notifications
from .review import router as review
from .tags import router as tags
from .trends import router as trends

__all__ = [
    "admin",
    "conditions",
    "days",
    "goals",
    "health",
    "notifications",
    "review",
    "tags",
    "trends",
]
