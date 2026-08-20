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
        self.language = "ru"

    def clear(self):
        self.operation = None
        self.appointment_id = None
        self.service_id = None
        self.service_name = None
        self.date = None
        self.time = None
        self.period = None
        self.customer_name = None
        # Keep the customer's language

    def is_complete(self):
        return all([
            self.service_id,
            self.date,
            self.time,
            self.customer_name,
        ])

    def to_prompt(self):
        return f"""
Текущее состояние записи:

Операция: {self.operation}
ID записи: {self.appointment_id}
ID услуги: {self.service_id}
Услуга: {self.service_name}
Дата: {self.date}
Время: {self.time}
Период: {self.period}
Имя клиента: {self.customer_name}
Язык клиента: {self.language}
"""