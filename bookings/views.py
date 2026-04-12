"""
Views for the parking booking system.
Handles the public booking flow and admin dashboard.
"""
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.db.models import Count, Q
from datetime import timedelta

from .models import ParkingSlot, Reservation
from .forms import ReservationForm
from .utils import generate_booking_code


# ─── Public Views ────────────────────────────────────────────────────────────

def home_view(request):
    """Landing page with parking overview and stats."""
    slots = ParkingSlot.objects.all()
    total = slots.count()
    free = slots.filter(status='free').count()
    reserved = slots.filter(status='reserved').count()
    occupied = slots.filter(status='occupied').count()
    maintenance = slots.filter(status='maintenance').count()

    context = {
        'slots': slots,
        'total': total,
        'free': free,
        'reserved': reserved,
        'occupied': occupied,
        'maintenance': maintenance,
    }
    return render(request, 'home.html', context)


def select_slot_view(request):
    """Interactive grid of available parking slots."""
    slots = ParkingSlot.objects.all()
    context = {'slots': slots}
    return render(request, 'booking/select_slot.html', context)


def reserve_slot_view(request, slot_id):
    """Show reservation form and process booking."""
    slot = get_object_or_404(ParkingSlot, id=slot_id)

    if slot.status != 'free':
        messages.error(request, f'Slot {slot.slot_number} is no longer available.')
        return redirect('select_slot')

    if request.method == 'POST':
        form = ReservationForm(request.POST)
        if form.is_valid():
            # Create the reservation
            booking_code = generate_booking_code()
            now = timezone.now()
            duration = int(form.cleaned_data['duration_minutes'])
            reservation = Reservation(
                slot=slot,
                booking_code=booking_code,
                expires_at=now + timedelta(minutes=duration),
                duration_minutes=duration,
                vehicle_type=form.cleaned_data['vehicle_type'],
                vehicle_color=form.cleaned_data['vehicle_color'],
                plate_number=form.cleaned_data['plate_number'],
                status='active',
            )
            reservation.save()

            # Mark slot as reserved
            slot.status = 'reserved'
            slot.save()

            return redirect('confirmation', booking_code=booking_code)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ReservationForm(initial={'slot': slot})

    context = {
        'form': form,
        'slot': slot,
    }
    return render(request, 'booking/reservation_form.html', context)


def confirmation_view(request, booking_code):
    """Show receipt with booking code and countdown timer."""
    reservation = get_object_or_404(Reservation, booking_code=booking_code)
    context = {
        'reservation': reservation,
        'time_remaining': reservation.time_remaining,
    }
    return render(request, 'booking/confirmation.html', context)


def receipt_view(request, booking_code):
    """Printable receipt page."""
    reservation = get_object_or_404(Reservation, booking_code=booking_code)
    context = {'reservation': reservation}
    return render(request, 'booking/receipt_pdf.html', context)


def check_status_api(request, booking_code):
    """AJAX endpoint to check reservation countdown status."""
    try:
        reservation = Reservation.objects.get(booking_code=booking_code)
        return JsonResponse({
            'status': reservation.status,
            'time_remaining': reservation.time_remaining,
            'slot_status': reservation.slot.status,
            'is_expired': reservation.is_expired,
        })
    except Reservation.DoesNotExist:
        return JsonResponse({'error': 'Reservation not found'}, status=404)


def find_reservation_view(request):
    """Handle booking code submission from the navbar modal."""
    if request.method == 'POST':
        booking_code = request.POST.get('booking_code', '').strip().upper()
        if booking_code:
            try:
                reservation = Reservation.objects.get(booking_code=booking_code)
                return redirect('confirmation', booking_code=reservation.booking_code)
            except Reservation.DoesNotExist:
                messages.error(request, f'Reservation {booking_code} not found.')
        else:
            messages.error(request, 'Please enter a valid booking code.')
            
    return redirect(request.META.get('HTTP_REFERER', 'home'))


def cancel_reservation_view(request, booking_code):
    """Allow user to cancel their active reservation."""
    reservation = get_object_or_404(Reservation, booking_code=booking_code)

    if reservation.status == 'active':
        # Free the slot
        slot = reservation.slot
        slot.status = 'free'
        slot.save()

        # Mark reservation as cancelled
        reservation.status = 'cancelled'
        reservation.save()

        messages.success(request, f'Reservation {booking_code} has been successfully cancelled. The slot is now free.')
    else:
        messages.warning(request, f'Reservation {booking_code} cannot be cancelled (Current status: {reservation.get_status_display()}).')

    return redirect('home')


# ─── Admin Views ─────────────────────────────────────────────────────────────

def admin_login_view(request):
    """Simple password-based admin login."""
    if request.session.get('is_admin'):
        return redirect('admin_dashboard')

    if request.method == 'POST':
        password = request.POST.get('password', '')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        if password == admin_password:
            request.session['is_admin'] = True
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'Invalid password.')

    return render(request, 'admin_dashboard/login.html')


def admin_logout_view(request):
    """Logout from admin."""
    request.session.pop('is_admin', None)
    return redirect('admin_login')


def admin_required(view_func):
    """Decorator to require admin session."""
    def wrapper(request, *args, **kwargs):
        if not request.session.get('is_admin'):
            return redirect('admin_login')
        return view_func(request, *args, **kwargs)
    return wrapper


@admin_required
def admin_dashboard_view(request):
    """Admin dashboard with overview stats."""
    slots = ParkingSlot.objects.all()
    reservations = Reservation.objects.all()
    active_reservations = reservations.filter(status='active')
    today = timezone.now().date()

    # Stats
    total_slots = slots.count()
    free_slots = slots.filter(status='free').count()
    reserved_slots = slots.filter(status='reserved').count()
    occupied_slots = slots.filter(status='occupied').count()
    maintenance_slots = slots.filter(status='maintenance').count()

    today_reservations = reservations.filter(reserved_at__date=today).count()
    expired_today = reservations.filter(status='expired', reserved_at__date=today).count()
    checked_in_today = reservations.filter(status='checked_in', reserved_at__date=today).count()

    # Recent reservations
    recent_reservations = reservations[:20]

    context = {
        'total_slots': total_slots,
        'free_slots': free_slots,
        'reserved_slots': reserved_slots,
        'occupied_slots': occupied_slots,
        'maintenance_slots': maintenance_slots,
        'today_reservations': today_reservations,
        'expired_today': expired_today,
        'checked_in_today': checked_in_today,
        'active_reservations': active_reservations,
        'recent_reservations': recent_reservations,
        'occupancy_rate': round((occupied_slots + reserved_slots) / total_slots * 100, 1) if total_slots > 0 else 0,
    }
    return render(request, 'admin_dashboard/dashboard.html', context)


@admin_required
def admin_slot_management_view(request):
    """Manage parking slots – add, remove, toggle maintenance."""
    slots = ParkingSlot.objects.all()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            slot_number = request.POST.get('slot_number', '').strip().upper()
            location = request.POST.get('location', '').strip()
            if slot_number and location:
                if ParkingSlot.objects.filter(slot_number=slot_number).exists():
                    messages.error(request, f'Slot {slot_number} already exists.')
                else:
                    ParkingSlot.objects.create(slot_number=slot_number, location=location)
                    messages.success(request, f'Slot {slot_number} added successfully.')
            else:
                messages.error(request, 'Slot number and location are required.')

        elif action == 'delete':
            slot_id = request.POST.get('slot_id')
            slot = get_object_or_404(ParkingSlot, id=slot_id)
            if slot.status in ('reserved', 'occupied'):
                messages.error(request, f'Cannot delete slot {slot.slot_number} – it is currently {slot.status}.')
            else:
                slot_num = slot.slot_number
                slot.delete()
                messages.success(request, f'Slot {slot_num} deleted.')

        elif action == 'maintenance':
            slot_id = request.POST.get('slot_id')
            slot = get_object_or_404(ParkingSlot, id=slot_id)
            if slot.status == 'maintenance':
                slot.status = 'free'
                slot.save()
                messages.success(request, f'Slot {slot.slot_number} taken out of maintenance.')
            elif slot.status == 'free':
                slot.status = 'maintenance'
                slot.save()
                messages.success(request, f'Slot {slot.slot_number} set to maintenance.')
            else:
                messages.error(request, f'Cannot change slot {slot.slot_number} – it is currently {slot.status}.')

        return redirect('admin_slot_management')

    context = {'slots': slots}
    return render(request, 'admin_dashboard/slot_management.html', context)


@admin_required
def admin_reports_view(request):
    """Usage statistics and reservation reports."""
    today = timezone.now().date()
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)

    all_reservations = Reservation.objects.all()

    # Daily counts for last 7 days
    daily_data = []
    for i in range(7):
        day = today - timedelta(days=i)
        count = all_reservations.filter(reserved_at__date=day).count()
        expired = all_reservations.filter(reserved_at__date=day, status='expired').count()
        checked = all_reservations.filter(reserved_at__date=day, status='checked_in').count()
        
        w_success = int((checked / count) * 100) if count > 0 else 0
        w_danger = int((expired / count) * 100) if count > 0 else 0
        
        daily_data.append({
            'date': day,
            'total': count,
            'expired': expired,
            'checked_in': checked,
            'success_attr': f'style="width: {w_success}%;"',
            'danger_attr': f'style="width: {w_danger}%;"',
        })

    # Totals
    total_all_time = all_reservations.count()
    total_last_7 = all_reservations.filter(reserved_at__date__gte=last_7_days).count()
    total_last_30 = all_reservations.filter(reserved_at__date__gte=last_30_days).count()
    expired_count = all_reservations.filter(status='expired').count()
    checked_in_count = all_reservations.filter(status='checked_in').count()

    # Turnover rate
    turnover_rate = round(
        (checked_in_count / total_all_time * 100) if total_all_time > 0 else 0, 1
    )

    context = {
        'daily_data': daily_data,
        'total_all_time': total_all_time,
        'total_last_7': total_last_7,
        'total_last_30': total_last_30,
        'expired_count': expired_count,
        'checked_in_count': checked_in_count,
        'turnover_rate': turnover_rate,
    }
    return render(request, 'admin_dashboard/reports.html', context)
