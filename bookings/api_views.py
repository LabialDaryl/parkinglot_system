"""
REST API views for ESP32 communication (placeholder endpoints).
These endpoints expose JSON APIs that an ESP32 device will consume in the future
to update slot status, validate booking codes, and control gates/indicators.
"""
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone

from .models import ParkingSlot, Reservation
from .serializers import (
    ParkingSlotSerializer,
    ParkingSlotStatusSerializer,
    ReservationSerializer,
    ValidateBookingCodeSerializer,
)


@api_view(['GET'])
def api_slot_list(request):
    """
    GET /api/v1/slots/
    List all parking slots with their current status.
    ESP32 can poll this to update physical indicators.
    """
    slots = ParkingSlot.objects.all()
    serializer = ParkingSlotSerializer(slots, many=True)
    return Response({
        'count': slots.count(),
        'results': serializer.data,
    })


@api_view(['GET'])
def api_slot_detail(request, slot_id):
    """
    GET /api/v1/slots/<id>/
    Get details for a single parking slot.
    """
    try:
        slot = ParkingSlot.objects.get(id=slot_id)
    except ParkingSlot.DoesNotExist:
        return Response({'error': 'Slot not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ParkingSlotSerializer(slot)
    return Response(serializer.data)


@api_view(['PATCH'])
def api_slot_update_status(request, slot_id):
    """
    PATCH /api/v1/slots/<id>/status/
    Update slot status. Used by ESP32 to mark slots as occupied/free.
    
    Request body: {"status": "occupied"} or {"status": "free"}
    """
    try:
        slot = ParkingSlot.objects.get(id=slot_id)
    except ParkingSlot.DoesNotExist:
        return Response({'error': 'Slot not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ParkingSlotStatusSerializer(data=request.data)
    if serializer.is_valid():
        slot.status = serializer.validated_data['status']
        slot.save()
        return Response({
            'message': f'Slot {slot.slot_number} status updated to {slot.status}',
            'slot': ParkingSlotSerializer(slot).data,
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def api_validate_booking(request):
    """
    POST /api/v1/reservations/validate/
    Validate a booking code and mark the reservation as checked in.
    ESP32 sends the code scanned/entered at the gate.
    
    Request body: {"booking_code": "AB12C"}
    Response: reservation details + slot info if valid.
    """
    serializer = ValidateBookingCodeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    code = serializer.validated_data['booking_code'].upper()

    try:
        reservation = Reservation.objects.get(booking_code=code)
    except Reservation.DoesNotExist:
        return Response({
            'valid': False,
            'error': 'Booking code not found',
        }, status=status.HTTP_404_NOT_FOUND)

    if reservation.status == 'expired':
        return Response({
            'valid': False,
            'error': 'Reservation has expired',
        }, status=status.HTTP_410_GONE)

    if reservation.status == 'checked_in':
        return Response({
            'valid': False,
            'error': 'Already checked in',
        }, status=status.HTTP_409_CONFLICT)

    if reservation.status != 'active':
        return Response({
            'valid': False,
            'error': f'Reservation status is {reservation.status}',
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check in the reservation
    reservation.status = 'checked_in'
    reservation.checked_in_at = timezone.now()
    reservation.save()

    # Update slot to occupied
    reservation.slot.status = 'occupied'
    reservation.slot.save()

    return Response({
        'valid': True,
        'message': 'Check-in successful',
        'reservation': ReservationSerializer(reservation).data,
    })


@api_view(['GET'])
def api_reservation_detail(request, booking_code):
    """
    GET /api/v1/reservations/<code>/
    Get reservation details by booking code.
    """
    try:
        reservation = Reservation.objects.get(booking_code=booking_code.upper())
    except Reservation.DoesNotExist:
        return Response({'error': 'Reservation not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ReservationSerializer(reservation)
    return Response(serializer.data)
