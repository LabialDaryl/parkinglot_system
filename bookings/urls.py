"""
URL configuration for the bookings app.
"""
from django.urls import path
from . import views, api_views

urlpatterns = [
    # ── Public booking flow ───────────────────────────────────────────
    path('', views.home_view, name='home'),
    path('slots/', views.select_slot_view, name='select_slot'),
    path('book/<int:slot_id>/', views.reserve_slot_view, name='reserve_slot'),
    path('confirmation/<str:booking_code>/', views.confirmation_view, name='confirmation'),
    path('receipt/<str:booking_code>/', views.receipt_view, name='receipt'),
    path('status/<str:booking_code>/', views.check_status_api, name='check_status'),
    path('cancel/<str:booking_code>/', views.cancel_reservation_view, name='cancel_reservation'),
    path('find/', views.find_reservation_view, name='find_reservation'),

    # ── Admin ─────────────────────────────────────────────────────────
    path('admin-panel/login/', views.admin_login_view, name='admin_login'),
    path('admin-panel/logout/', views.admin_logout_view, name='admin_logout'),
    path('admin-panel/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin-panel/slots/', views.admin_slot_management_view, name='admin_slot_management'),
    path('admin-panel/reports/', views.admin_reports_view, name='admin_reports'),

    # ── REST API (ESP32 placeholder) ──────────────────────────────────
    path('api/v1/slots/', api_views.api_slot_list, name='api_slot_list'),
    path('api/v1/slots/<int:slot_id>/', api_views.api_slot_detail, name='api_slot_detail'),
    path('api/v1/slots/<int:slot_id>/status/', api_views.api_slot_update_status, name='api_slot_update_status'),
    path('api/v1/reservations/validate/', api_views.api_validate_booking, name='api_validate_booking'),
    path('api/v1/reservations/<str:booking_code>/', api_views.api_reservation_detail, name='api_reservation_detail'),
]
