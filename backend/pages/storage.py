"""
JSON file-based storage for data persistence.
Data is saved to a JSON file and persists across server restarts.
"""

import uuid
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import threading

# IST Timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def get_ist_now() -> str:
    """Get current time in IST (Indian Standard Time) as ISO format string"""
    return datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')

# Thread-safe lock
_lock = threading.Lock()

# JSON file path for persistent storage
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(DATA_DIR, 'data.json')

# In-memory cache (loaded from JSON file)
_tasks: Dict[str, dict] = {}
_pages: Dict[str, dict] = {}
_profiles: Dict[str, dict] = {}
_invites: Dict[str, dict] = {}


def _load_data():
    """Load data from JSON file on startup"""
    global _tasks, _pages, _profiles, _invites

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                _tasks = data.get('tasks', {})
                _pages = data.get('pages', {})
                _profiles = data.get('profiles', {})
                _invites = data.get('invites', {})
                print(f">>> STORAGE: Loaded {len(_tasks)} tasks, {len(_pages)} pages from {DATA_FILE}")
        except Exception as e:
            print(f">>> STORAGE ERROR: Failed to load data: {e}")
            _tasks = {}
            _pages = {}
            _profiles = {}
            _invites = {}
    else:
        print(f">>> STORAGE: No existing data file, starting fresh")


def _save_data():
    """Save data to JSON file"""
    try:
        data = {
            'tasks': _tasks,
            'pages': _pages,
            'profiles': _profiles,
            'invites': _invites,
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        # Uncomment for debugging:
        # print(f">>> STORAGE: Saved {len(_tasks)} tasks, {len(_pages)} pages to {DATA_FILE}")
    except Exception as e:
        print(f">>> STORAGE ERROR: Failed to save data: {e}")


# Load data on module import
_load_data()


def _generate_id() -> str:
    return str(uuid.uuid4().hex[:24])


# ===========================================
# Task Operations
# ===========================================

def create_task(profile_id: str, num_pages: int, page_name: str, public_profile_url: str = "") -> str:
    """Create a new page generation task"""
    with _lock:
        task_id = _generate_id()
        _tasks[task_id] = {
            "_id": task_id,
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
            "created_at": get_ist_now(),
            "started_at": None,
            "completed_at": None,
            "error_message": None,
        }
        _save_data()
        return task_id


def update_task_status(task_id: str, status: str, celery_task_id: str = None,
                       error_message: str = None):
    """Update task status"""
    with _lock:
        if task_id in _tasks:
            _tasks[task_id]["status"] = status
            if celery_task_id:
                _tasks[task_id]["celery_task_id"] = celery_task_id
            if status == "running":
                _tasks[task_id]["started_at"] = get_ist_now()
            elif status in ["completed", "failed", "cancelled"]:
                _tasks[task_id]["completed_at"] = get_ist_now()
            if error_message:
                _tasks[task_id]["error_message"] = error_message
            _save_data()


def increment_task_counter(task_id: str, field: str):
    """Increment pages_created or pages_failed counter"""
    with _lock:
        if task_id in _tasks:
            _tasks[task_id][field] = _tasks[task_id].get(field, 0) + 1
            _save_data()


def get_task(task_id: str) -> Optional[dict]:
    """Get task by ID"""
    with _lock:
        task = _tasks.get(task_id)
        if task:
            return dict(task)
        return None


def get_all_tasks(limit: int = 50) -> List[dict]:
    """Get all tasks, newest first"""
    with _lock:
        tasks = list(_tasks.values())
        tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return [dict(t) for t in tasks[:limit]]


def delete_task(task_id: str) -> bool:
    """Permanently delete a task and its associated pages/invites"""
    with _lock:
        if task_id not in _tasks:
            return False

        # Delete the task
        del _tasks[task_id]

        # Delete associated pages
        pages_to_delete = [pid for pid, page in _pages.items() if page.get("task_id") == task_id]
        for pid in pages_to_delete:
            # Delete invites for this page
            page_id = _pages[pid].get("page_id", "")
            invites_to_delete = [iid for iid, inv in _invites.items() if inv.get("page_id") == page_id]
            for iid in invites_to_delete:
                del _invites[iid]
            del _pages[pid]

        _save_data()
        print(f">>> STORAGE: Permanently deleted task {task_id} and {len(pages_to_delete)} associated pages")
        return True


# ===========================================
# Page Operations
# ===========================================

def store_page_details(task_id: str, page_id: str, page_name: str, page_url: str,
                       sequence_num: int, gender: str = None) -> str:
    """Store created page details"""
    with _lock:
        doc_id = _generate_id()
        _pages[doc_id] = {
            "_id": doc_id,
            "task_id": task_id,
            "page_id": page_id,
            "page_name": page_name,
            "page_url": page_url,
            "sequence_num": sequence_num,
            "gender": gender or "unknown",
            "status": "created",
            "creation_time": get_ist_now(),
        }
        _save_data()
        print(f">>> STORAGE: Saved page '{page_name}' to database")
        return doc_id


def get_pages_by_task(task_id: str) -> List[dict]:
    """Get all pages for a task"""
    with _lock:
        pages = [dict(p) for p in _pages.values() if p.get("task_id") == task_id]
        pages.sort(key=lambda x: x.get("sequence_num", 0))
        return pages


def get_all_pages(limit: int = 100) -> List[dict]:
    """Get all pages, newest first"""
    with _lock:
        pages = list(_pages.values())
        pages.sort(key=lambda x: x.get("creation_time", ""), reverse=True)
        return [dict(p) for p in pages[:limit]]


# ===========================================
# Profile Operations
# ===========================================

def store_profile(email: str, password: str, name: str = None) -> str:
    """Store Facebook profile credentials"""
    with _lock:
        profile_id = _generate_id()
        _profiles[profile_id] = {
            "_id": profile_id,
            "email": email,
            "password": password,
            "name": name or email,
            "created_at": get_ist_now(),
            "is_active": True,
        }
        _save_data()
        return profile_id


def get_profile(profile_id: str) -> Optional[dict]:
    """Get profile by ID"""
    with _lock:
        profile = _profiles.get(profile_id)
        if profile:
            return dict(profile)
        return None


def get_all_profiles() -> List[dict]:
    """Get all profiles (without passwords)"""
    with _lock:
        result = []
        for profile in _profiles.values():
            p = dict(profile)
            p.pop("password", None)
            result.append(p)
        return result


# ===========================================
# Efficiency Metrics
# ===========================================

def get_efficiency_report() -> dict:
    """Calculate efficiency metrics from all tasks"""
    with _lock:
        completed_tasks = [t for t in _tasks.values() if t.get("status") == "completed"]
        all_pages = list(_pages.values())

        total_pages = len(all_pages)
        total_tasks = len(completed_tasks)

        if total_tasks == 0:
            return {
                "total_tasks": 0,
                "total_pages": 0,
                "pages_created": 0,
                "pages_failed": 0,
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

def store_invite(page_id: str, page_name: str, invitee_email: str,
                 invite_link: str, role: str, invited_by: str = None) -> str:
    """Store a page invite"""
    with _lock:
        invite_id = _generate_id()
        _invites[invite_id] = {
            "_id": invite_id,
            "page_id": page_id,
            "page_name": page_name,
            "invitee_email": invitee_email,
            "invite_link": invite_link,
            "role": role,
            "invited_by": invited_by or "",
            "status": "pending",  # pending, accepted, declined, expired
            "created_at": get_ist_now(),
            "accepted_at": None,
        }
        _save_data()
        return invite_id


def get_invites_by_page(page_id: str) -> List[dict]:
    """Get all invites for a page"""
    with _lock:
        invites = [dict(i) for i in _invites.values() if i.get("page_id") == page_id]
        invites.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return invites


def get_invite(invite_id: str) -> Optional[dict]:
    """Get invite by ID"""
    with _lock:
        invite = _invites.get(invite_id)
        if invite:
            return dict(invite)
        return None


def update_invite_status(invite_id: str, status: str):
    """Update invite status"""
    with _lock:
        if invite_id in _invites:
            _invites[invite_id]["status"] = status
            if status == "accepted":
                _invites[invite_id]["accepted_at"] = get_ist_now()
            _save_data()


def get_all_invites(limit: int = 100) -> List[dict]:
    """Get all invites, newest first"""
    with _lock:
        invites = list(_invites.values())
        invites.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return [dict(i) for i in invites[:limit]]


def get_page_by_id(page_id: str) -> Optional[dict]:
    """Get page by its Facebook page_id"""
    with _lock:
        for page in _pages.values():
            if page.get("page_id") == page_id:
                return dict(page)
        return None
