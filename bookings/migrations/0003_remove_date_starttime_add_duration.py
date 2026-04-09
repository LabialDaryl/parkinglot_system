from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0002_reservation_plate_number_reservation_vehicle_color_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reservation',
            name='date',
        ),
        migrations.RemoveField(
            model_name='reservation',
            name='start_time',
        ),
        migrations.AddField(
            model_name='reservation',
            name='duration_minutes',
            field=models.IntegerField(
                choices=[(10, '10 minutes'), (20, '20 minutes'), (30, '30 minutes')],
                default=10,
                help_text='Reservation duration in minutes',
            ),
        ),
    ]
