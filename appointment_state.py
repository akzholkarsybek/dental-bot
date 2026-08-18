class AppointmentState:
    def __init__(self):
        self.operation = None
        self.appointment_id = None
        self.service_id = None
        self.service_name = None
        self.date = None
        self.time = None
        self.period = None
        self.customer_name = None

    def clear(self):
        self.operation = None
        self.appointment_id = None
        self.service_id = None
        self.service_name = None
        self.date = None
        self.time = None
        self.period = None
        self.customer_name = None

    def is_complete(self):
        return all([
            self.service_id,
            self.date,
            self.time,
            self.customer_name,
        ])

    def to_prompt(self):
        return f"""
Current appointment state:

Operation: {self.operation}
Appointment ID: {self.appointment_id}
Service ID: {self.service_id}
Service: {self.service_name}
Date: {self.date}
Time: {self.time}
Period: {self.period}
Customer name: {self.customer_name}
"""