from django.contrib import admin
from .models import ParkingSlot, Reservation


@admin.register(ParkingSlot)
class ParkingSlotAdmin(admin.ModelAdmin):
    list_display = ['slot_number', 'location', 'status', 'updated_at']
    list_filter = ['status', 'location']
    search_fields = ['slot_number', 'location']


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ['booking_code', 'plate_number', 'slot', 'date', 'start_time', 'status', 'reserved_at', 'expires_at']
    list_filter = ['status', 'date', 'vehicle_type']
    search_fields = ['booking_code', 'plate_number']
    readonly_fields = ['booking_code', 'reserved_at']
