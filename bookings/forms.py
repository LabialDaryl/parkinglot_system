from django import forms
from .models import Reservation, ParkingSlot


class ReservationForm(forms.Form):
    """Form for creating a new parking reservation."""

    slot = forms.ModelChoiceField(
        queryset=ParkingSlot.objects.filter(status='free'),
        widget=forms.HiddenInput(),
    )
    DURATION_CHOICES = [
        (10, '10 minutes'),
        (20, '20 minutes'),
        (30, '30 minutes'),
    ]
    duration_minutes = forms.ChoiceField(
        choices=DURATION_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'btn-check',
        }),
        initial=10,
        label='Reserve for',
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
