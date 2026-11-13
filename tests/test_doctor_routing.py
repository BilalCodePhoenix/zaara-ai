import pytest
from app.services.doctor_service import recommend_doctor


@pytest.mark.parametrize("problem, expected", [
    ("toothache", "Endodontist"),
    ("tooth pain", "Endodontist"),
    ("wisdom tooth pain", "Oral Surgeon"),
    ("braces", "Orthodontist"),
    ("cleaning", "General Dentist"),
])
def test_recommend_doctor(problem, expected):
    assert recommend_doctor(problem)[2] == expected