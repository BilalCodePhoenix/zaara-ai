from datetime import date, time, datetime

from pydantic import BaseModel, Field, field_validator


class BookingRequest(BaseModel):

    problem: str = Field(min_length=2)

    patient_name: str = Field(min_length=2)

    patient_phone: str = Field(min_length=10, max_length=15)

    appointment_date: date

    appointment_time: time

    @field_validator("patient_phone")
    @classmethod
    def validate_phone(cls, value):

        if not value.isdigit():
            raise ValueError("Phone number must contain only digits")

        return value

    @field_validator("patient_name")
    @classmethod
    def validate_name(cls, value):

        if not value.replace(" ", "").isalpha():
            raise ValueError("Name must contain only letters and spaces")

        return value

    @field_validator("appointment_date")
    @classmethod
    def validate_date(cls, value):

        if value < date.today():
            raise ValueError("Appointment date cannot be in the past")

        return value


    @field_validator("appointment_time")
    @classmethod
    def validate_time(cls, value, info):

        clinic_open = time(9, 0)
        clinic_close = time(18, 0)

        if value < clinic_open or value >= clinic_close:
            raise ValueError(
                "Appointment time must be between 09:00 and 18:00."
            )

        appointment_date = info.data.get("appointment_date")

        if appointment_date == date.today():
            current_time = datetime.now().time()

            if value <= current_time:
                raise ValueError(
                    "Appointment time must be later than the current time."
                )

        return value