from django.db import models
from django.utils import timezone
from datetime import timedelta


class ParkingSlot(models.Model):
    """Represents a physical parking slot."""

    STATUS_CHOICES = [
        ('free', 'Free'),
        ('reserved', 'Reserved'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Maintenance'),
    ]

    slot_number = models.CharField(max_length=10, unique=True, help_text="e.g. A-01, B-05")
    location = models.CharField(max_length=100, help_text="e.g. Ground Floor, Level 2")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='free')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['slot_number']

    def __str__(self):
        return f"{self.slot_number} ({self.location}) - {self.get_status_display()}"

    @property
    def status_color(self):
        """Return Bootstrap color class for the status."""
        colors = {
            'free': 'success',
            'reserved': 'warning',
            'occupied': 'danger',
            'maintenance': 'secondary',
        }
        return colors.get(self.status, 'secondary')

    @property
    def status_icon(self):
        """Return icon for the status."""
        icons = {
            'free': '🟢',
            'reserved': '🟡',
            'occupied': '🔴',
            'maintenance': '⚪',
        }
        return icons.get(self.status, '⚪')


class Reservation(models.Model):
    """Represents a parking slot reservation."""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('checked_in', 'Checked In'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    slot = models.ForeignKey(ParkingSlot, on_delete=models.CASCADE, related_name='reservations')
    DURATION_CHOICES = [
        (5, '5 minutes'),
        (10, '10 minutes'),
        (15, '15 minutes'),
    ]

    booking_code = models.CharField(max_length=5, unique=True, db_index=True)
    reserved_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    duration_minutes = models.IntegerField(choices=DURATION_CHOICES, default=5, help_text="Reservation duration in minutes")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    checked_in_at = models.DateTimeField(null=True, blank=True)
    
    # Vehicle Information
    VEHICLE_TYPES = [
        ('Car', 'Car'),
        ('Motorcycle', 'Motorcycle'),
        ('SUV', 'SUV'),
        ('Truck', 'Truck'),
        ('Van', 'Van'),
        ('Other', 'Other'),
    ]
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES, default='Car')
    vehicle_color = models.CharField(max_length=50, default='')
    plate_number = models.CharField(max_length=20, db_index=True, default='')

    class Meta:
        ordering = ['-reserved_at']

    def __str__(self):
        return f"[{self.booking_code}] Slot {self.slot.slot_number} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        """Auto-set expires_at based on chosen duration_minutes."""
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=self.duration_minutes)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if reservation has expired."""
        return timezone.now() > self.expires_at and self.status == 'active'

    @property
    def time_remaining(self):
        """Return seconds remaining before expiry."""
        if self.status != 'active':
            return 0
        remaining = (self.expires_at - timezone.now()).total_seconds()
        return max(0, int(remaining))

    @property
    def status_badge(self):
        """Return Bootstrap badge class."""
        badges = {
            'active': 'primary',
            'expired': 'danger',
            'checked_in': 'success',
            'completed': 'info',
            'cancelled': 'secondary',
        }
        return badges.get(self.status, 'secondary')
