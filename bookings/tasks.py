"""
Auto-release scheduler using APScheduler.
Periodically checks for expired reservations and releases the slots.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)
scheduler_started = False


def release_expired_reservations():
    """Find and release all expired reservations."""
    from .models import Reservation

    now = timezone.now()
    expired = Reservation.objects.filter(
        status='active',
        expires_at__lt=now
    ).select_related('slot')

    count = expired.count()
    if count > 0:
        for reservation in expired:
            reservation.status = 'expired'
            reservation.slot.status = 'free'
            reservation.slot.save()
            reservation.save()
            logger.info(f"Auto-released slot {reservation.slot.slot_number} "
                        f"(code: {reservation.booking_code})")
        logger.info(f"Released {count} expired reservation(s)")


def start_scheduler():
    """Start the APScheduler to run the release job every 30 seconds."""
    global scheduler_started
    import sys

    # Don't start scheduler during migrations or other management commands
    if scheduler_started:
        return

    # Only start scheduler for runserver / gunicorn
    is_running_server = (
        'runserver' in sys.argv or
        'gunicorn' in sys.argv[0] if sys.argv else False
    )
    if not is_running_server:
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            release_expired_reservations,
            trigger=IntervalTrigger(seconds=30),
            id='release_expired_reservations',
            name='Release expired parking reservations',
            replace_existing=True,
        )
        scheduler.start()
        scheduler_started = True
        logger.info("APScheduler started – checking expired reservations every 30s")
    except Exception as e:
        logger.error(f"Failed to start APScheduler: {e}")
