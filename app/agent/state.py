#here this represent what agent currently knows about the caller
class ConversationState:

    def __init__(self):
        self.problem = None

        self.doctor_id = None
        self.doctor_name = None

        self.appointment_date = None
        self.appointment_time = None

        self.patient_name = None
        self.patient_phone = None

        self.appointment_id = None

        self.appointment_confirmed = False