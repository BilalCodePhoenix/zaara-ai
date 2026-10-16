import logging

from app.database.queries import get_doctors

logger = logging.getLogger(__name__)


def get_available_doctors():
    logger.info("Fetching available doctors")

    doctors = get_doctors()

    logger.info("Found %s available doctors", len(doctors))

    return doctors


def recommend_doctor(problem):
    logger.info("Finding doctor for patient problem")

    doctors = get_available_doctors()
    problem = problem.lower()

    if "toothache" in problem or "tooth pain" in problem:
        specialization = "Endodontist"

    elif "braces" in problem or "crooked teeth" in problem:
        specialization = "Orthodontist"

    elif "wisdom tooth" in problem or "surgery" in problem:
        specialization = "Oral Surgeon"

    else:
        specialization = "General Dentist"

    for doctor in doctors:
        if doctor[2] == specialization:
            logger.info(
                "Doctor selected: %s (%s)",
                doctor[1],
                doctor[2]
            )
            return doctor

    logger.warning(
        "No doctor found for specialization: %s",
        specialization
    )

    return None