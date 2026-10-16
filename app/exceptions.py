class BookingError(Exception):
    """Base exception for booking-related errors."""
    pass


class PatientError(BookingError):
    """Something went wrong with patient information."""
    pass


class AppointmentError(BookingError):
    """Something went wrong with an appointment."""
    pass


class DatabaseError(BookingError):
    """Something went wrong while communicating with the database."""
    pass