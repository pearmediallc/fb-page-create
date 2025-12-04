"""
MongoDB connection and operations for Facebook Pages storage.
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure
from django.conf import settings
from datetime import datetime
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)

# MongoDB client singleton
_client = None
_db = None
_indexes_created = False


def get_db():
    """Get MongoDB database connection"""
    global _client, _db

    if _db is None:
        try:
            _client = MongoClient(settings.MONGO_URI)
            # Test connection
            _client.admin.command('ping')
            _db = _client[settings.MONGO_DB_NAME]
            logger.info(f"Connected to MongoDB: {settings.MONGO_DB_NAME}")
            # Create indexes after connection
            ensure_indexes()
        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise

    return _db


def ensure_indexes():
    """
    Create indexes for commonly queried fields.
    This improves query performance significantly.
    """
    global _indexes_created
    if _indexes_created:
        return

    try:
        db = _db

        # ===========================================
        # TASKS Collection Indexes
        # ===========================================
        tasks = db['tasks']
        # Index for sorting by created_at (used in get_all_tasks)
        tasks.create_index([("created_at", DESCENDING)], name="idx_tasks_created_at")
        # Index for filtering by status (used in get_efficiency_report)
        tasks.create_index([("status", ASCENDING)], name="idx_tasks_status")
        # Compound index for status + created_at (common query pattern)
        tasks.create_index([("status", ASCENDING), ("created_at", DESCENDING)], name="idx_tasks_status_created")
        logger.info("Created indexes for 'tasks' collection")

        # ===========================================
        # PAGES Collection Indexes
        # ===========================================
        pages = db['pages']
        # Index for filtering by task_id (used in get_pages_by_task)
        pages.create_index([("task_id", ASCENDING)], name="idx_pages_task_id")
        # Index for sorting by creation_time (used in get_all_pages)
        pages.create_index([("creation_time", DESCENDING)], name="idx_pages_creation_time")
        # Index for filtering by page_id (used in get_page_by_id)
        pages.create_index([("page_id", ASCENDING)], name="idx_pages_page_id")
        # Compound index for task_id + sequence_num (used in get_pages_by_task with sort)
        pages.create_index([("task_id", ASCENDING), ("sequence_num", ASCENDING)], name="idx_pages_task_seq")
        logger.info("Created indexes for 'pages' collection")

        # ===========================================
        # PROFILES Collection Indexes
        # ===========================================
        profiles = db['profiles']
        # Index for filtering by is_active (used in get_all_profiles)
        profiles.create_index([("is_active", ASCENDING)], name="idx_profiles_is_active")
        # Index for email (unique constraint for login)
        profiles.create_index([("email", ASCENDING)], name="idx_profiles_email", unique=True)
        logger.info("Created indexes for 'profiles' collection")

        # ===========================================
        # INVITES Collection Indexes
        # ===========================================
        invites = db['invites']
        # Index for filtering by page_id (used in get_invites_by_page)
        invites.create_index([("page_id", ASCENDING)], name="idx_invites_page_id")
        # Index for sorting by created_at (used in get_all_invites)
        invites.create_index([("created_at", DESCENDING)], name="idx_invites_created_at")
        # Compound index for page_id + created_at
        invites.create_index([("page_id", ASCENDING), ("created_at", DESCENDING)], name="idx_invites_page_created")
        # Index for filtering by status
        invites.create_index([("status", ASCENDING)], name="idx_invites_status")
        logger.info("Created indexes for 'invites' collection")

        _indexes_created = True
        logger.info("All MongoDB indexes created successfully")

    except Exception as e:
        logger.error(f"Error creating MongoDB indexes: {e}")
        # Don't fail - indexes are optimization, not required


def get_pages_collection():
    """Get the pages collection"""
    return get_db()['pages']


def get_tasks_collection():
    """Get the tasks collection"""
    return get_db()['tasks']


def get_profiles_collection():
    """Get the profiles collection (Facebook credentials)"""
    return get_db()['profiles']


# ===========================================
# Task Operations
# ===========================================

def create_task(profile_id: str, num_pages: int, page_name: str, public_profile_url: str = "") -> str:
    """Create a new page generation task"""
    tasks = get_tasks_collection()

    task_doc = {
        "profile_id": profile_id,
        "num_pages": num_pages,
        "base_page_name": page_name,
        "public_profile_url": public_profile_url,
        "status": "pending",
        "celery_task_id": None,
        "pages_created": 0,
        "pages_failed": 0,
        "shares_sent": 0,
        "shares_failed": 0,
        "created_at": datetime.utcnow(),
        "started_at": None,
        "completed_at": None,
        "error_message": None,
    }

    result = tasks.insert_one(task_doc)
    return str(result.inserted_id)


def update_task_status(task_id: str, status: str, celery_task_id: str = None,
                       error_message: str = None):
    """Update task status"""
    tasks = get_tasks_collection()

    update_doc = {"status": status}

    if celery_task_id:
        update_doc["celery_task_id"] = celery_task_id

    if status == "running":
        update_doc["started_at"] = datetime.utcnow()
    elif status in ["completed", "failed", "cancelled"]:
        update_doc["completed_at"] = datetime.utcnow()

    if error_message:
        update_doc["error_message"] = error_message

    tasks.update_one(
        {"_id": ObjectId(task_id)},
        {"$set": update_doc}
    )


def increment_task_counter(task_id: str, field: str):
    """Increment pages_created or pages_failed counter"""
    tasks = get_tasks_collection()
    tasks.update_one(
        {"_id": ObjectId(task_id)},
        {"$inc": {field: 1}}
    )


def get_task(task_id: str) -> dict:
    """Get task by ID"""
    tasks = get_tasks_collection()
    task = tasks.find_one({"_id": ObjectId(task_id)})
    if task:
        task["_id"] = str(task["_id"])
    return task


def get_all_tasks(limit: int = 50) -> list:
    """Get all tasks, newest first"""
    tasks = get_tasks_collection()
    cursor = tasks.find().sort("created_at", -1).limit(limit)
    result = []
    for task in cursor:
        task["_id"] = str(task["_id"])
        result.append(task)
    return result


def delete_task(task_id: str) -> bool:
    """Permanently delete a task and its associated pages/invites"""
    try:
        tasks = get_tasks_collection()
        pages = get_pages_collection()
        invites = get_invites_collection()

        # Get all pages for this task
        task_pages = list(pages.find({"task_id": task_id}))
        page_ids = [p.get("page_id", "") for p in task_pages]

        # Delete invites for these pages
        if page_ids:
            invites.delete_many({"page_id": {"$in": page_ids}})

        # Delete pages for this task
        pages.delete_many({"task_id": task_id})

        # Delete the task
        result = tasks.delete_one({"_id": ObjectId(task_id)})

        if result.deleted_count > 0:
            logger.info(f"Permanently deleted task {task_id} and {len(task_pages)} associated pages")
            return True
        return False

    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {e}")
        return False


# ===========================================
# Page Operations
# ===========================================

def store_page_details(task_id: str, page_id: str, page_name: str, page_url: str,
                       sequence_num: int, gender: str = None) -> str:
    """Store created page details in MongoDB"""
    pages = get_pages_collection()

    page_doc = {
        "task_id": task_id,
        "page_id": page_id,
        "page_name": page_name,
        "page_url": page_url,
        "sequence_num": sequence_num,
        "gender": gender or "unknown",
        "status": "created",
        "creation_time": datetime.utcnow(),
    }

    result = pages.insert_one(page_doc)
    return str(result.inserted_id)


def get_pages_by_task(task_id: str) -> list:
    """Get all pages for a task"""
    pages = get_pages_collection()
    cursor = pages.find({"task_id": task_id}).sort("sequence_num", 1)
    result = []
    for page in cursor:
        page["_id"] = str(page["_id"])
        result.append(page)
    return result


def get_all_pages(limit: int = 100) -> list:
    """Get all pages, newest first"""
    pages = get_pages_collection()
    cursor = pages.find().sort("creation_time", -1).limit(limit)
    result = []
    for page in cursor:
        page["_id"] = str(page["_id"])
        result.append(page)
    return result


# ===========================================
# Profile Operations (Facebook credentials)
# ===========================================

def store_profile(email: str, password: str, name: str = None) -> str:
    """Store Facebook profile credentials"""
    profiles = get_profiles_collection()

    profile_doc = {
        "email": email,
        "password": password,  # In production, encrypt this!
        "name": name or email,
        "created_at": datetime.utcnow(),
        "is_active": True,
    }

    result = profiles.insert_one(profile_doc)
    return str(result.inserted_id)


def get_profile(profile_id: str) -> dict:
    """Get profile by ID"""
    profiles = get_profiles_collection()
    profile = profiles.find_one({"_id": ObjectId(profile_id)})
    if profile:
        profile["_id"] = str(profile["_id"])
    return profile


def get_all_profiles() -> list:
    """Get all profiles"""
    profiles = get_profiles_collection()
    cursor = profiles.find({"is_active": True})
    result = []
    for profile in cursor:
        profile["_id"] = str(profile["_id"])
        # Don't expose password in list view
        profile.pop("password", None)
        result.append(profile)
    return result


# ===========================================
# Efficiency Metrics
# ===========================================

def get_efficiency_report() -> dict:
    """Calculate efficiency metrics from all tasks"""
    tasks = get_tasks_collection()
    pages = get_pages_collection()

    completed_tasks = list(tasks.find({"status": "completed"}))
    all_pages = list(pages.find())

    total_pages = len(all_pages)
    total_tasks = len(completed_tasks)

    if total_tasks == 0:
        return {
            "total_tasks": 0,
            "total_pages": 0,
            "success_rate": 0,
            "avg_pages_per_task": 0,
        }

    total_created = sum(t.get("pages_created", 0) for t in completed_tasks)
    total_failed = sum(t.get("pages_failed", 0) for t in completed_tasks)

    return {
        "total_tasks": total_tasks,
        "total_pages": total_pages,
        "pages_created": total_created,
        "pages_failed": total_failed,
        "success_rate": (total_created / (total_created + total_failed) * 100)
        if (total_created + total_failed) > 0 else 0,
        "avg_pages_per_task": total_created / total_tasks if total_tasks > 0 else 0,
    }


# ===========================================
# Invite Operations
# ===========================================

def get_invites_collection():
    """Get the invites collection"""
    return get_db()['invites']


def store_invite(page_id: str, page_name: str, invitee_email: str,
                 invite_link: str, role: str, invited_by: str = None) -> str:
    """Store a page invite"""
    invites = get_invites_collection()

    invite_doc = {
        "page_id": page_id,
        "page_name": page_name,
        "invitee_email": invitee_email,
        "invite_link": invite_link,
        "role": role,
        "invited_by": invited_by or "",
        "status": "pending",
        "created_at": datetime.utcnow(),
        "accepted_at": None,
    }

    result = invites.insert_one(invite_doc)
    return str(result.inserted_id)


def get_invites_by_page(page_id: str) -> list:
    """Get all invites for a page"""
    invites = get_invites_collection()
    cursor = invites.find({"page_id": page_id}).sort("created_at", -1)
    result = []
    for invite in cursor:
        invite["_id"] = str(invite["_id"])
        result.append(invite)
    return result


def get_invite(invite_id: str) -> dict:
    """Get invite by ID"""
    invites = get_invites_collection()
    invite = invites.find_one({"_id": ObjectId(invite_id)})
    if invite:
        invite["_id"] = str(invite["_id"])
    return invite


def update_invite_status(invite_id: str, status: str):
    """Update invite status"""
    invites = get_invites_collection()
    update_doc = {"status": status}
    if status == "accepted":
        update_doc["accepted_at"] = datetime.utcnow()

    invites.update_one(
        {"_id": ObjectId(invite_id)},
        {"$set": update_doc}
    )


def get_all_invites(limit: int = 100) -> list:
    """Get all invites, newest first"""
    invites = get_invites_collection()
    cursor = invites.find().sort("created_at", -1).limit(limit)
    result = []
    for invite in cursor:
        invite["_id"] = str(invite["_id"])
        result.append(invite)
    return result


def get_page_by_id(page_id: str) -> dict:
    """Get page by its Facebook page_id"""
    pages = get_pages_collection()
    page = pages.find_one({"page_id": page_id})
    if page:
        page["_id"] = str(page["_id"])
    return page
