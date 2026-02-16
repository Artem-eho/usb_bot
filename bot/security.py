import os


def is_safe_path(base_path, path):
    """Check that path is within base_path (prevents directory traversal)."""
    base_path = os.path.realpath(base_path)
    path = os.path.realpath(path)
    return os.path.commonpath([base_path]) == os.path.commonpath([base_path, path])


def is_user_allowed(user_id: int, filtered_users: list) -> bool:
    """Check if user_id is in the allowed list. Empty list means allow all."""
    if not filtered_users:
        return True
    return str(user_id) in filtered_users


def is_file_accessible(path):
    """Check that file exists and is readable."""
    return os.path.isfile(path) and os.access(path, os.R_OK)
