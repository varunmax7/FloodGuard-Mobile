"""adminapi/audit.py — helpers to write CalibrationLog and ModerationLog."""
import logging

logger = logging.getLogger("floodguard.audit")


def log_calibration(actor: str, change_type: str, before: dict, after: dict) -> None:
    """Write a CalibrationLog entry. Call from any calibration-mutating view."""
    from apps.risk.models import CalibrationLog
    CalibrationLog.objects.create(
        actor=actor,
        change_type=change_type,
        before=before,
        after=after,
    )
    logger.info("CalibrationLog actor=%s type=%s", actor, change_type)


def log_moderation(actor, report, action: str) -> None:
    """Write a ModerationLog entry. Call from moderation action views."""
    from apps.reports.models import ModerationLog
    ModerationLog.objects.create(actor=actor, report=report, action=action)
    logger.info("ModerationLog actor=%s action=%s report=%s", actor, action, report.id)
