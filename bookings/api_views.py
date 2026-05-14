"""
REST API views for ESP32 communication.
These endpoints expose JSON APIs that the ESP32 device consumes to
update slot status, validate booking codes, and control gates/indicators.
"""
import logging
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

logger = logging.getLogger(__name__)


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

    Smart transitions:
    - If a slot is 'reserved' and ESP32 reports 'occupied', the reservation
      is automatically checked-in (car arrived at reserved slot).
    - If a slot is 'reserved' and ESP32 reports 'free', the reservation
      status is preserved (car hasn't arrived yet, don't clear reservation).
    """
    try:
        slot = ParkingSlot.objects.get(id=slot_id)
    except ParkingSlot.DoesNotExist:
        return Response({'error': 'Slot not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ParkingSlotStatusSerializer(data=request.data)
    if not serializer.is_valid():
        logger.warning(
            "ESP32 PATCH slot %s invalid data: %s  (raw body: %s)",
            slot_id, serializer.errors, request.body
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    new_status = serializer.validated_data['status']
    old_status = slot.status

    # Smart transition: reserved → occupied means the car arrived
    if old_status == 'reserved' and new_status == 'occupied':
        active_reservation = slot.reservations.filter(status__in=['active', 'accepted']).first()
        if active_reservation:
            active_reservation.status = 'checked_in'
            active_reservation.checked_in_at = timezone.now()
            active_reservation.save()
            logger.info(
                "Auto check-in reservation %s for slot %s",
                active_reservation.booking_code, slot.slot_number
            )

    # Smart transition: don't let ESP32 clear a reserved slot
    if old_status == 'reserved' and new_status == 'free':
        return Response({
            'message': f'Slot {slot.slot_number} is reserved, ignoring free signal from hardware',
            'slot': ParkingSlotSerializer(slot).data,
        })

    slot.status = new_status
    slot.save()
    logger.info("Slot %s status: %s -> %s", slot.slot_number, old_status, new_status)
    return Response({
        'message': f'Slot {slot.slot_number} status updated to {slot.status}',
        'slot': ParkingSlotSerializer(slot).data,
    })


@api_view(['POST'])
def api_bulk_update_slots(request):
    """
    POST /api/v1/slots/bulk-update/
    Bulk-update all slot statuses from ESP32 in a single HTTP call.

    Request body:
        {"slots": [{"id": 1, "status": "occupied"}, {"id": 2, "status": "free"}, ...]}

    This dramatically reduces latency vs 8 individual PATCH calls.
    """
    slots_data = request.data.get('slots', [])
    if not isinstance(slots_data, list) or len(slots_data) == 0:
        return Response(
            {'error': 'Expected {"slots": [{"id": 1, "status": "occupied"}, ...]}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    results = []
    for entry in slots_data:
        slot_id = entry.get('id')
        new_status = entry.get('status')

        if not slot_id or not new_status:
            results.append({'id': slot_id, 'ok': False, 'error': 'Missing id or status'})
            continue

        if new_status not in ('free', 'occupied'):
            results.append({'id': slot_id, 'ok': False, 'error': f'Invalid status: {new_status}'})
            continue

        try:
            slot = ParkingSlot.objects.get(id=slot_id)
        except ParkingSlot.DoesNotExist:
            results.append({'id': slot_id, 'ok': False, 'error': 'Not found'})
            continue

        old_status = slot.status

        # Smart transition: reserved → occupied = auto check-in
        if old_status == 'reserved' and new_status == 'occupied':
            active_res = slot.reservations.filter(status__in=['active', 'accepted']).first()
            if active_res:
                active_res.status = 'checked_in'
                active_res.checked_in_at = timezone.now()
                active_res.save()

        # Don't clear a reserved slot via hardware
        if old_status == 'reserved' and new_status == 'free':
            results.append({'id': slot_id, 'ok': True, 'skipped': True, 'reason': 'reserved'})
            continue

        if old_status != new_status:
            slot.status = new_status
            slot.save()

        results.append({'id': slot_id, 'ok': True, 'status': slot.status})

    return Response({'results': results})


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

    if reservation.status not in ['active', 'accepted']:
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


@api_view(['GET'])
def api_slot_stats(request):
    """
    GET /api/v1/slots/stats/
    Return aggregated slot counts AND the full slot list in one response.

    Consumed by browser pages (Home, Select Slot, Admin Dashboard) via
    JavaScript polling every 4 seconds to keep the UI in sync with the
    physical state reported by the ESP32 sensors — without a full page reload.

    Single DB query + Python Counter instead of 5 separate filter().count()
    calls — minimises database round-trips on every browser poll.

    Response shape:
    {
        "counts": {
            "total": 8, "free": 5, "reserved": 1, "occupied": 2, "maintenance": 0
        },
        "occupancy_rate": 37.5,
        "slots": [ { "id": 1, "slot_number": "P-1", "location": "...",
                     "status": "free", "status_display": "Free" }, ... ]
    }
    """
    from collections import Counter

    # One DB round-trip: fetch all slots and count statuses in Python.
    slots_qs   = ParkingSlot.objects.all()
    slots_list = list(slots_qs)           # evaluate queryset once
    counts     = Counter(s.status for s in slots_list)

    total       = len(slots_list)
    free        = counts.get('free', 0)
    reserved    = counts.get('reserved', 0)
    occupied    = counts.get('occupied', 0)
    maintenance = counts.get('maintenance', 0)

    occupancy_rate = round(
        (occupied + reserved) / total * 100, 1
    ) if total > 0 else 0

    serializer = ParkingSlotSerializer(slots_list, many=True)

    return Response({
        'counts': {
            'total':       total,
            'free':        free,
            'reserved':    reserved,
            'occupied':    occupied,
            'maintenance': maintenance,
        },
        'occupancy_rate': occupancy_rate,
        'slots': serializer.data,
    })
