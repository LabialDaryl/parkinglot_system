from django.apps import AppConfig


class BookingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bookings'
    verbose_name = 'Parking Bookings'

    def ready(self):
        """Start the APScheduler when the app is ready."""
        from . import tasks  # noqa: F401
        tasks.start_scheduler()
