"""Web endpoints for the admin page (the "receptionist").

Each endpoint does three things only:
  1. FastAPI checks the incoming data against the schema (rules).
  2. We call ONE service function.
  3. We return the result.
No SQL and no business logic lives here.

These are plain `def` functions on purpose: psycopg is a blocking
library, and FastAPI runs plain `def` endpoints in a worker thread, so a
slow database call never freezes the whole server.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Path, Query

from app.admin import service
from app.admin.schemas import (
    AppointmentOut,
    AppointmentPage,
    AppointmentStatus,
    AppointmentStatusUpdate,
    DoctorActive,
    DoctorCreate,
    DoctorOut,
    DoctorUpdate,
    PatientPage,
    Specialization,
    UpcomingCount,
)

router = APIRouter(prefix="/api")

DoctorId = Path(ge=1, description="Database id of the doctor")
AppointmentId = Path(ge=1, description="Database id of the appointment")


# ---------------------------------------------------------------- doctors

@router.get("/specializations", response_model=list[str], tags=["doctors"])
def list_specializations():
    """The allowed specializations (feeds the page's dropdowns)."""
    return [s.value for s in Specialization]


@router.get("/doctors", response_model=list[DoctorOut], tags=["doctors"])
def list_doctors():
    return service.list_doctors()


@router.post("/doctors", response_model=DoctorOut, status_code=201, tags=["doctors"])
def create_doctor(body: DoctorCreate):
    return service.create_doctor(
        name=body.name,
        specialization=body.specialization,
        consultation_fee=body.consultation_fee,
        is_active=body.is_active,
    )


@router.patch("/doctors/{doctor_id}", response_model=DoctorOut, tags=["doctors"])
def update_doctor(body: DoctorUpdate, doctor_id: int = DoctorId):
    # exclude_unset: only the fields the page actually sent.
    return service.update_doctor(doctor_id, body.model_dump(exclude_unset=True))


@router.patch(
    "/doctors/{doctor_id}/active", response_model=DoctorOut, tags=["doctors"]
)
def set_doctor_active(body: DoctorActive, doctor_id: int = DoctorId):
    return service.set_doctor_active(doctor_id, body.is_active)


@router.get(
    "/doctors/{doctor_id}/upcoming", response_model=UpcomingCount, tags=["doctors"]
)
def doctor_upcoming(doctor_id: int = DoctorId):
    """Used by the page to warn before deactivating a busy doctor."""
    return {"upcoming_appointments": service.count_upcoming_for_doctor(doctor_id)}


# --------------------------------------------------------------- patients

@router.get("/patients", response_model=PatientPage, tags=["patients"])
def list_patients(
    q: str | None = Query(None, max_length=100, description="Name or phone"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return service.list_patients(q=q, limit=limit, offset=offset)


# ----------------------------------------------------------- appointments

@router.get("/appointments", response_model=AppointmentPage, tags=["appointments"])
def list_appointments(
    scope: Literal["upcoming", "past", "all"] = "upcoming",
    on_date: date | None = Query(None, alias="date", description="One exact day"),
    doctor_id: int | None = Query(None, ge=1),
    status: AppointmentStatus | None = None,
    q: str | None = Query(None, max_length=100, description="Patient name or phone"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return service.list_appointments(
        scope=scope,
        on_date=on_date,
        doctor_id=doctor_id,
        status=status.value if status else None,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/appointments/{appointment_id}/status",
    response_model=AppointmentOut,
    tags=["appointments"],
)
def update_appointment_status(
    body: AppointmentStatusUpdate, appointment_id: int = AppointmentId
):
    return service.update_appointment_status(appointment_id, body.status)