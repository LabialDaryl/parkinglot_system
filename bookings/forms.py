from django import forms
from .models import Reservation, ParkingSlot


class ReservationForm(forms.Form):
    """Form for creating a new parking reservation."""

    slot = forms.ModelChoiceField(
        queryset=ParkingSlot.objects.filter(status='free'),
        widget=forms.HiddenInput(),
    )
    DURATION_CHOICES = [
        (5, '5 minutes'),
        (10, '10 minutes'),
        (15, '15 minutes'),
    ]
    duration_minutes = forms.ChoiceField(
        choices=DURATION_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'btn-check',
        }),
        initial=5,
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

    def clean_plate_number(self):
        plate_number = self.cleaned_data.get('plate_number')
        if plate_number:
            # Check if this plate number already has an active or checked_in reservation
            active_reservation = Reservation.objects.filter(
                plate_number__iexact=plate_number,
                status__in=['active', 'checked_in']
            ).first()
            
            if active_reservation:
                raise forms.ValidationError(
                    f"This vehicle (Plate: {plate_number}) already has an ongoing reservation."
                )
        return plate_number
