"""Data Retention Policy - GDPR Article 5(1)(e) Compliance.

Automatically cleans up old session and log files based on configurable retention periods.
"""
import os
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def cleanup_old_files(directory: str, max_age_days: int) -> dict:
    """Delete files older than max_age_days from the specified directory.

    Args:
        directory: Path to the directory to clean
        max_age_days: Maximum age in days before files are deleted

    Returns:
        dict with 'deleted' count and 'errors' count
    """
    if not os.path.exists(directory):
        logger.debug("Directory %s does not exist, skipping cleanup", directory)
        return {"deleted": 0, "errors": 0}

    cutoff_time = time.time() - (max_age_days * 86400)  # 86400 seconds per day
    deleted_count = 0
    error_count = 0

    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)

        # Skip directories
        if os.path.isdir(filepath):
            continue

        try:
            file_mtime = os.path.getmtime(filepath)
            if file_mtime < cutoff_time:
                os.remove(filepath)
                deleted_count += 1
                logger.info(
                    "Data retention: Deleted %s (age: %d days)",
                    filename,
                    int((time.time() - file_mtime) / 86400)
                )
        except OSError as e:
            error_count += 1
            logger.error("Data retention: Failed to delete %s: %s", filename, e)

    return {"deleted": deleted_count, "errors": error_count}


def run_data_retention_cleanup(
    sessions_dir: str = "data/sessions",
    logs_dir: str = "data/logs",
    sessions_retention_days: int = 30,
    logs_retention_days: int = 90
) -> dict:
    """Run data retention cleanup on sessions and logs directories.

    Args:
        sessions_dir: Path to sessions directory
        logs_dir: Path to logs directory
        sessions_retention_days: Days to keep session files
        logs_retention_days: Days to keep log files

    Returns:
        dict with cleanup results for both directories
    """
    logger.info(
        "Running data retention cleanup (sessions: %d days, logs: %d days)",
        sessions_retention_days,
        logs_retention_days
    )

    results = {
        "timestamp": datetime.now().isoformat(),
        "sessions": cleanup_old_files(sessions_dir, sessions_retention_days),
        "logs": cleanup_old_files(logs_dir, logs_retention_days)
    }

    total_deleted = results["sessions"]["deleted"] + results["logs"]["deleted"]
    if total_deleted > 0:
        logger.info(
            "Data retention cleanup complete: %d files deleted",
            total_deleted
        )
    else:
        logger.debug("Data retention cleanup: No files to delete")

    return results
