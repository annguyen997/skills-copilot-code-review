"""
Announcement endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from datetime import date, datetime, timezone
from bson import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def serialize_announcement(announcement: dict) -> dict:
    """Convert MongoDB document to a JSON-serializable dict"""
    result = dict(announcement)
    result["id"] = str(result.pop("_id"))
    return result


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """
    Get all currently active announcements (no authentication required).

    An announcement is active when today's date is within its start/expiration range:
    - expiration_date >= today
    - start_date is absent/null OR start_date <= today
    """
    today = date.today().isoformat()

    query = {
        "expiration_date": {"$gte": today},
        "$or": [
            {"start_date": None},
            {"start_date": {"$lte": today}}
        ]
    }

    announcements = []
    for announcement in announcements_collection.find(query).sort("created_at", -1):
        announcements.append(serialize_announcement(announcement))

    return announcements


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """
    Get all announcements including expired and upcoming ones.
    Requires teacher authentication.
    """
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    announcements = []
    for announcement in announcements_collection.find().sort("created_at", -1):
        announcements.append(serialize_announcement(announcement))

    return announcements


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    message: str,
    expiration_date: str,
    teacher_username: Optional[str] = Query(None),
    start_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new announcement. Requires teacher authentication.

    - message: The announcement text (required)
    - expiration_date: Last day the announcement is visible, YYYY-MM-DD (required)
    - start_date: First day the announcement is visible, YYYY-MM-DD (optional)
    """
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    try:
        date.fromisoformat(expiration_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expiration_date format. Use YYYY-MM-DD.")

    # Normalize empty string to None
    start_date = start_date or None
    if start_date:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")

    announcement = {
        "message": message,
        "start_date": start_date,
        "expiration_date": expiration_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": teacher_username
    }

    result = announcements_collection.insert_one(announcement)
    announcement["id"] = str(result.inserted_id)
    announcement.pop("_id", None)

    return announcement


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: str,
    expiration_date: str,
    teacher_username: Optional[str] = Query(None),
    start_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update an existing announcement. Requires teacher authentication.

    - announcement_id: MongoDB ObjectId string of the announcement
    - message: Updated announcement text (required)
    - expiration_date: Updated expiration date, YYYY-MM-DD (required)
    - start_date: Updated start date, YYYY-MM-DD (optional)
    """
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    try:
        date.fromisoformat(expiration_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expiration_date format. Use YYYY-MM-DD.")

    start_date = start_date or None
    if start_date:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")

    result = announcements_collection.update_one(
        {"_id": obj_id},
        {"$set": {"message": message, "start_date": start_date, "expiration_date": expiration_date}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updated = announcements_collection.find_one({"_id": obj_id})
    return serialize_announcement(updated)


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Delete an announcement. Requires teacher authentication.

    - announcement_id: MongoDB ObjectId string of the announcement
    """
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    result = announcements_collection.delete_one({"_id": obj_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
