"""
REST API serializers for the parking booking system.
Used by ESP32 and AJAX endpoints.
"""
from rest_framework import serializers
from .models import ParkingSlot, Reservation


class ParkingSlotSerializer(serializers.ModelSerializer):
    """Serializer for parking slot data."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ParkingSlot
        fields = ['id', 'slot_number', 'location', 'status', 'status_display', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ParkingSlotStatusSerializer(serializers.Serializer):
    """Serializer for updating slot status (ESP32 use)."""
    status = serializers.ChoiceField(choices=ParkingSlot.STATUS_CHOICES)


class ReservationSerializer(serializers.ModelSerializer):
    """Serializer for reservation data."""
    slot_number = serializers.CharField(source='slot.slot_number', read_only=True)
    slot_location = serializers.CharField(source='slot.location', read_only=True)
    time_remaining = serializers.IntegerField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Reservation
        fields = [
            'id', 'slot', 'slot_number', 'slot_location', 'booking_code',
            'reserved_at', 'expires_at', 'date', 'start_time',
            'vehicle_type', 'vehicle_color', 'plate_number',
            'status', 'status_display', 'time_remaining', 'checked_in_at',
        ]
        read_only_fields = ['id', 'booking_code', 'reserved_at', 'expires_at']


class ValidateBookingCodeSerializer(serializers.Serializer):
    """Serializer for validating a booking code (ESP32 use)."""
    booking_code = serializers.CharField(max_length=5, min_length=5)
