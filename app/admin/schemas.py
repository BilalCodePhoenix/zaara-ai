"""Data rules for the admin side (Pydantic models).

A schema is a checklist that describes what VALID data looks like.
Anything that fails the checklist is rejected before it reaches the
database, and the page shows a clear message instead.
"""

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class Specialization(str, Enum):
    """The only specializations the voice assistant understands.

    These strings MUST match what recommend_doctor() looks for in
    app/services/doctor_service.py. Using a fixed list (a dropdown in
    the page) means a typo can never hide a doctor from the assistant.
    """

    GENERAL_DENTIST = "General Dentist"
    ORTHODONTIST = "Orthodontist"
    ENDODONTIST = "Endodontist"
    ORAL_SURGEON = "Oral Surgeon"


def _tidy(value: str) -> str:
    """Trim the ends and collapse repeated spaces: ' Dr.  Rahul ' -> 'Dr. Rahul'."""
    return " ".join(value.split())


# ---------------------------------------------------------------------
# Doctors
# ---------------------------------------------------------------------

class DoctorCreate(BaseModel):
    """What the owner must provide to add a doctor."""

    # extra="forbid": unknown fields are an error, not silently ignored.
    # use_enum_values: specialization arrives as a plain string.
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    name: str = Field(min_length=2, max_length=100)
    specialization: Specialization
    consultation_fee: Decimal = Field(ge=0, max_digits=8, decimal_places=2)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def tidy_name(cls, value: str) -> str:
        value = _tidy(value)
        if len(value) < 2:
            raise ValueError("Name must have at least 2 characters.")
        return value


class DoctorUpdate(BaseModel):
    """Fields the owner may change. Every field is optional,
    but at least one must be sent and none may be null."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    name: str | None = Field(default=None, min_length=2, max_length=100)
    specialization: Specialization | None = None
    consultation_fee: Decimal | None = Field(
        default=None, ge=0, max_digits=8, decimal_places=2
    )

    @field_validator("name")
    @classmethod
    def tidy_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = _tidy(value)
        if len(value) < 2:
            raise ValueError("Name must have at least 2 characters.")
        return value

    @model_validator(mode="after")
    def at_least_one_real_field(self):
        if not self.model_fields_set:
            raise ValueError("Send at least one field to change.")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be empty.")
        return self


class DoctorActive(BaseModel):
    """Body of the on/off toggle."""

    model_config = ConfigDict(extra="forbid")

    is_active: bool


class DoctorOut(BaseModel):
    """What the API sends back to the page."""

    id: int
    name: str
    specialization: str
    consultation_fee: float  # numeric(10,2) -> plain JSON number for the page
    is_active: bool

    @field_validator("consultation_fee", mode="before")
    @classmethod
    def fee_to_float(cls, value):
        return float(value)


class UpcomingCount(BaseModel):
    """How many booked appointments a doctor still has (today or later)."""

    upcoming_appointments: int


# ---------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------

class PatientOut(BaseModel):
    id: int
    name: str
    phone: str
    created_at: datetime
    total_appointments: int
    upcoming_appointments: int
    next_appointment: datetime | None = None


class PatientPage(BaseModel):
    items: list[PatientOut]
    total: int  # all matches, not just this page (the page shows "1-25 of total")


# ---------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------

class AppointmentStatus(str, Enum):
    """Same three values your appointments_status_check allows."""

    BOOKED = "booked"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class AppointmentOut(BaseModel):
    id: int
    appointment_date: date
    appointment_time: time
    status: str
    patient_id: int
    patient_name: str
    patient_phone: str
    doctor_id: int
    doctor_name: str
    doctor_specialization: str


class AppointmentPage(BaseModel):
    items: list[AppointmentOut]
    total: int


class AppointmentStatusUpdate(BaseModel):
    """The admin may only move a BOOKED appointment to one of these two."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["cancelled", "completed"]