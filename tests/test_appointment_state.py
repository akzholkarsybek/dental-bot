from appointment_state import AppointmentState


def test_new_state_is_empty():
    state = AppointmentState()

    assert state.service_id is None
    assert state.service_name is None
    assert state.date is None
    assert state.time is None
    assert state.period is None
    assert state.customer_name is None


def test_incomplete_state():
    state = AppointmentState()

    state.service_id = 3
    state.date = "2026-08-18"
    state.customer_name = "Akzhol"

    assert state.is_complete() is False


def test_complete_state():
    state = AppointmentState()

    state.service_id = 3
    state.service_name = "Dental Filling"
    state.date = "2026-08-18"
    state.time = "09:00"
    state.customer_name = "Akzhol"

    assert state.is_complete() is True


def test_clear_resets_state():
    state = AppointmentState()

    state.service_id = 3
    state.service_name = "Dental Filling"
    state.date = "2026-08-18"
    state.time = "09:00"
    state.period = "morning"
    state.customer_name = "Akzhol"

    state.clear()

    assert state.service_id is None
    assert state.service_name is None
    assert state.date is None
    assert state.time is None
    assert state.period is None
    assert state.customer_name is None


def test_to_prompt_contains_state():
    state = AppointmentState()

    state.service_id = 3
    state.service_name = "Dental Filling"
    state.date = "2026-08-18"
    state.time = "09:00"
    state.period = "morning"
    state.customer_name = "Akzhol"

    prompt = state.to_prompt()

    assert "Dental Filling" in prompt
    assert "2026-08-18" in prompt
    assert "09:00" in prompt
    assert "morning" in prompt
    assert "Akzhol" in prompt

def test_new_state_has_no_operation():
    state = AppointmentState()

    assert state.operation is None


def test_operation_can_be_set():
    state = AppointmentState()

    state.operation = "reschedule"

    assert state.operation == "reschedule"


def test_clear_resets_operation():
    state = AppointmentState()

    state.operation = "reschedule"
    state.service_id = 3
    state.date = "2026-08-19"
    state.time = "17:00"

    state.clear()

    assert state.operation is None
    assert state.service_id is None
    assert state.date is None
    assert state.time is None


def test_to_prompt_contains_operation():
    state = AppointmentState()

    state.operation = "reschedule"

    prompt = state.to_prompt()

    assert "Operation: reschedule" in prompt