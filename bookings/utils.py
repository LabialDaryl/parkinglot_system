import random
import string


def generate_booking_code():
    """
    Generate a unique 5-character alphanumeric booking code.
    Uses uppercase letters and digits for readability.
    """
    from .models import Reservation

    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if not Reservation.objects.filter(booking_code=code).exists():
            return code
