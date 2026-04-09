from django import forms
from .models import Reservation, ParkingSlot


class ReservationForm(forms.Form):
    """Form for creating a new parking reservation."""

    slot = forms.ModelChoiceField(
        queryset=ParkingSlot.objects.filter(status='free'),
        widget=forms.HiddenInput(),
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'id': 'booking-date',
        })
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'form-control',
            'id': 'booking-time',
        })
    )
    vehicle_type = forms.ChoiceField(
        choices=[
            ('Car', 'Car'),
            ('Motorcycle', 'Motorcycle'),
            ('SUV', 'SUV'),
            ('Truck', 'Truck'),
            ('Van', 'Van'),
            ('Other', 'Other'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    vehicle_color = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Red',
        })
    )
    plate_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. ABC 1234',
        })
    )
