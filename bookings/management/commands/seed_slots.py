from django.core.management.base import BaseCommand
from bookings.models import ParkingSlot

class Command(BaseCommand):
    help = 'Seeds the database with 8 initial parking slots for the ESP32 hardware.'

    def handle(self, *args, **kwargs):
        slots_to_create = [
            {'slot_number': f'P-{i}', 'location': 'Main Parking Area'} for i in range(1, 9)
        ]
        
        created_count = 0
        for slot_data in slots_to_create:
            slot, created = ParkingSlot.objects.get_or_create(
                slot_number=slot_data['slot_number'],
                defaults={'location': slot_data['location'], 'status': 'free'}
            )
            if created:
                created_count += 1
                
        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(f'Successfully seeded {created_count} parking slots.'))
        else:
            self.stdout.write(self.style.SUCCESS('Parking slots already exist. No new slots seeded.'))
