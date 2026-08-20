import json
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from appointment_management import (
    get_customer_appointments,
    cancel_appointment,
    reschedule_appointment,
)

from appointment_state import AppointmentState

from database import (
    get_or_create_customer,
    get_recent_messages,
    save_message,
    update_customer_name,
)

from appointments import (
    check_availability,
    book_appointment,
    get_services,
    CLINIC_TIMES,
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("dental_bot")


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set.")


client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    timeout=30.0,
    max_retries=1,
)


# ============================================================
# APPOINTMENT STATE
# ============================================================

# Temporary in-memory appointment state.
# We will move this to PostgreSQL later.
appointment_states = {}


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an AI receptionist for a dental clinic.

Your job is to:
- Answer customer questions about the clinic.
- Help customers understand dental services.
- Help customers schedule appointments.
- Speak naturally, professionally, and concisely.
- Ask for missing information instead of guessing.
- Never invent prices, doctors, schedules, or appointments.

Appointment rules:
- Use information already provided by the customer.
- Maintain the context of the current conversation.
- Understand relative dates such as "today", "tomorrow", "Monday", etc.
- Convert relative dates into YYYY-MM-DD when calling tools.
- Never ask the customer to convert "tomorrow" into YYYY-MM-DD.
- If the customer provides a time such as "15:00", use it with the date already established.
- If the customer asks "what times are available" and the service and date are already known, immediately call check_availability.
- Do not ask for information that the customer has already provided.
- Before booking, make sure the customer has explicitly selected a specific available time.
- Never claim an appointment is booked until the booking system confirms it.

Appointment rescheduling:
- When the customer wants to reschedule an appointment, first use get_my_appointments.
- Never invent an appointment ID.
- Never reschedule an appointment belonging to another customer.
- If the customer has multiple appointments and has not clearly identified one, ask which appointment they want to reschedule.
- If exactly one appointment matches the customer's description, identify it clearly and ask for the new date and time.
- Always check availability before attempting to reschedule.
- Do not claim that an appointment was rescheduled until reschedule_appointment returns success.
- Never cancel the old appointment before the new slot has been successfully verified.
- Use 24-hour time only. Never use AM or PM.
- If the requested new time is unavailable, show the available times and ask the customer to choose another.

Appointment cancellation:
- When the customer wants to cancel an appointment, use get_my_appointments.
- Never invent an appointment ID.
- Never cancel an appointment without the customer clearly identifying which appointment they want to cancel.
- If the customer has multiple appointments and has not specified which one, show the appointments and ask which one they want to cancel.
- If the customer clearly identifies one appointment by service, date, time, or appointment ID, use that information to identify the exact appointment.
- If the customer's description matches exactly one appointment, ask for confirmation before cancelling it.
- If the description matches multiple appointments, ask the customer to choose one.
- Never cancel an appointment belonging to another customer.
- After the customer explicitly confirms cancellation, use cancel_appointment.
- Do not claim an appointment was cancelled until cancel_appointment returns success.

Customer name rules:
- When the customer explicitly states their name, use save_customer_name.
- Save the exact name provided by the customer.
- Never invent, guess, or change the customer's name.
- If the customer's name is already present in the appointment state, do not ask for it again.

Current appointment state:
- The current appointment state is authoritative.
- Never ask for information that is already present in the current appointment state.
- When the customer provides a missing appointment field, update that field instead of restarting the appointment.
- Never clear or replace an existing appointment field unless the customer explicitly changes it.
- Never replace an already selected service with another service.
- Never replace an already selected time unless the customer explicitly chooses another time.

Service selection:
- When the customer explicitly chooses a service, use select_service.
- Pass the customer's requested service name to select_service.
- Do not invent a service name.
- Do not convert a service name into a service ID yourself.
- Python will validate the service against the clinic's database.
- Never substitute one service for another.
- If the customer says "Dental Consultation", select Dental Consultation.
- If the customer says "Teeth Cleaning", select Teeth Cleaning.

Services:
- When a customer asks what services the clinic offers, use get_services.
- Only mention services returned by get_services.
- Never invent or assume that a service is offered by the clinic.

Conversation operation:

The current operation in appointment state is authoritative.


LANGUAGE RULES:

The customer's language has priority over all other sources of text.

1. Determine the response language from the customer's latest message.
2. Respond entirely in that language.
3. Continue using that language for the entire response, including after tool calls.
4. Tool results, database values, function results, and API responses are DATA ONLY.
5. NEVER copy the language of a tool result into the response.
6. ALWAYS translate tool/database data into the customer's current language before presenting it.
7. If the customer writes in Russian, the final response MUST be entirely in Russian.
8. If the customer writes in Kazakh, the final response MUST be entirely in Kazakh.
9. If the customer writes in English, the final response MUST be entirely in English.
10. If the customer switches languages, switch to the new language.
11. Never mix languages unless the customer explicitly asks for translation.

Examples:

Customer: "какие услуги есть?"
Tool result:
Teeth Cleaning — Professional dental cleaning — 25000

Correct response:
"Конечно 😊 У нас доступны следующие услуги:
- Профессиональная чистка зубов — 25 000 ₸, 60 минут
- ..."

Incorrect response:
"Our clinic offers:
- Teeth Cleaning — Professional dental cleaning..."

The tool result must NEVER determine the language of the final response.

Service names may be translated naturally when responding to the customer.
Never expose raw database or tool output directly to the customer.


Possible operations:
- None
- booking
- cancellation
- reschedule

If the current operation is "reschedule":
- Continue the rescheduling flow.
- Do not switch to booking, cancellation, or general service information unless the customer explicitly changes their request.
- Interpret new date/time messages as the requested rescheduling date/time.
- Do not ask the customer what they want to do again if they have already said they want to reschedule.

Time:
- Use 24-hour time only.
- Never use AM or PM.
- Use HH:MM format.
- Examples: 09:00, 10:00, 13:00, 14:00, 16:00, 17:00.
- When the customer explicitly chooses an appointment time, use select_appointment_time.
- Never assume an appointment time that the customer has not explicitly selected.
- The selected time must be available according to the clinic's availability.
- Understand natural expressions such as "1 in the afternoon" as 13:00.

Booking:
- Before booking, service, date, time, and customer name must be known.
- Never book unless the customer explicitly selected the time.
- Never claim an appointment is booked unless book_appointment returns success.

Rescheduling operation:
- If the customer says they want to change, move, or reschedule an existing appointment, immediately use start_rescheduling.
- After start_rescheduling succeeds, the operation becomes "reschedule".
- Once the operation is "reschedule", NEVER use book_appointment.
- A reschedule must use reschedule_appointment.
- A reschedule modifies the existing appointment; it must not create a new appointment.

When rescheduling:
- If get_my_appointments returns exactly one confirmed appointment, that appointment is the appointment being rescheduled.
- Store and use its appointment ID.
- Do not repeatedly ask which appointment it is.
- Once the customer provides a new date and/or time, use the existing appointment ID.
- If the customer provides both a new date and time, immediately check availability.
- If the customer provides only a new date, ask only for the new time.
- If the customer provides only a new time, use the existing appointment date and check availability.
- Do not ask the customer to repeat a date or time they already provided.

When rescheduling:
- The existing appointment's service is authoritative.
- Never change the service during rescheduling.
- Do not call select_service unless the customer explicitly says they want to change the service.
- When get_my_appointments identifies the appointment, use its exact service, date, time, and appointment ID.

RESCHEDULING TOOL FLOW:

When Operation is "reschedule":

1. The existing appointment ID is already stored in state.
2. The existing service is already stored in state.
3. The existing appointment date is already stored in state.
4. If the customer provides a new time:
   - Check availability if necessary.
   - If the requested time is available, select that time.
   - Immediately call reschedule_appointment.
5. Do NOT call check_availability repeatedly for the same date/time.
6. Do NOT ask the customer for the same time again after they already provided it.
7. Do NOT call book_appointment.
8. Do NOT call get_services.
9. Do NOT call select_service.
10. reschedule_appointment must be the final appointment-changing tool.
11. Only say the appointment was rescheduled after reschedule_appointment returns success.

If Operation is "reschedule" and the customer provides a time that is already present in the most recent availability result, call reschedule_appointment directly. Do not call select_appointment_time.

LANGUAGE RULES:

The customer's language ALWAYS has priority.

- Detect the language of the customer's latest message.
- Respond entirely in that language.
- Keep using that language throughout the conversation until the customer switches languages.
- Tool calls and database results NEVER determine the response language.
- Tool results are DATA ONLY. They must never be copied directly into the response.
- Translate all tool/database information into the customer's language before presenting it.
- If the customer writes in Russian, respond 100% in Russian.
- If the customer writes in Kazakh, respond 100% in Kazakh.
- If the customer writes in English, respond 100% in English.
- NEVER mix languages.

IMPORTANT:
After calling a tool such as get_services, get_doctors, or get_appointments,
you MUST continue responding in the customer's language.

Example:

Customer: "какие услуги есть?"

Tool result:
Teeth Cleaning — Professional dental cleaning — 25000

Correct:
"Конечно 😊 У нас доступны следующие услуги:
🦷 Профессиональная чистка зубов — 25 000 ₸, 60 минут
🦷 Консультация стоматолога — 15 000 ₸, 30 минут
🦷 Лечение кариеса — 30 000 ₸, 60 минут"

Incorrect:
"Our dental services are..."

Never output raw English tool/database text to a Russian-speaking customer.

RESPONSE STYLE:

- Respond naturally like a friendly human dental receptionist.
- Use natural Russian when the customer speaks Russian.
- Do not sound like a technical assistant or database.
- Do not use phrases like "Our dental services are".
- Do not expose raw database values or tool responses.
- Convert database information into natural customer-friendly sentences.
- Use prices with the ₸ symbol and spaces: 25 000 ₸.
- Use minutes naturally: "60 минут", "30 минут".
- Use short paragraphs and bullet points when listing several services.
- Emojis are allowed but should be used sparingly and naturally.
- Suitable emojis include 🦷, 📅, 🕐, 😊, ✨.
- Do not put an emoji in every sentence.
- Never use Markdown bold syntax with **.
- Do not output raw Markdown formatting unless Telegram is explicitly configured to render it.
- Never expose technical names such as function names, database fields, IDs, JSON, or tool results.

When listing services in Russian, use this style:

🦷 Профессиональная чистка зубов — 25 000 ₸, 60 минут.
🦷 Консультация стоматолога — 15 000 ₸, 30 минут.
🦷 Лечение кариеса — 30 000 ₸, 60 минут.

End naturally when appropriate, for example:
"Если хотите, помогу подобрать услугу и удобное время 😊"


Conversation rules:
- Keep conversations focused on the dental clinic and the customer's request.
- Keep responses concise.
- Do not start unrelated conversations.
- Politely redirect unrelated questions.
- Do not repeat information already provided.
- For unrelated questions, briefly state that the topic is outside the clinic's services and redirect the customer.
"""


# ============================================================
# TOOLS
# ============================================================

TOOLS = [
    {
        "type": "function",
        "name": "get_services",
        "description": (
            "Get the complete list of dental services offered "
            "by the clinic."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "reschedule_appointment",
        "description": (
            "FINAL ACTION for rescheduling an existing appointment. "
            "Use this after the new date and time have been selected "
            "and availability has been confirmed. "
            "This updates the EXISTING appointment and keeps the same "
            "appointment ID. NEVER use book_appointment for rescheduling."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "integer",
                    "description": "Existing appointment ID.",
                },
                "new_date": {
                    "type": "string",
                    "description": "New date in YYYY-MM-DD format.",
                },
                "new_time": {
                    "type": "string",
                    "description": "New time in HH:MM 24-hour format.",
                },
            },
            "required": [
                "appointment_id",
                "new_date",
                "new_time",
            ],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "start_rescheduling",
        "description": (
            "Start the appointment rescheduling operation when the "
            "customer explicitly says they want to change, move, "
            "or reschedule an existing appointment."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_my_appointments",
        "description": (
            "Get the current customer's confirmed appointments. "
            "Use this when the customer wants to view, cancel, "
            "or manage their appointments."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "cancel_appointment",
        "description": (
            "Cancel one specific confirmed appointment belonging "
            "to the current customer. Only use this after the customer "
            "has clearly identified the appointment they want to cancel."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "integer",
                    "description": "The exact appointment ID to cancel.",
                }
            },
            "required": ["appointment_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "select_service",
        "description": (
            "Select the dental service explicitly chosen by the customer. "
            "The service name must match a service returned by get_services."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": (
                        "The exact name of the dental service "
                        "selected by the customer."
                    ),
                }
            },
            "required": ["service_name"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "check_availability",
        "description": (
            "Check available appointment times for a selected "
            "dental service on a specific date."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "integer",
                    "description": (
                        "The ID of the service from get_services."
                    ),
                },
                "appointment_date": {
                    "type": "string",
                    "description": (
                        "Appointment date in YYYY-MM-DD format."
                    ),
                },
                "requested_period": {
                    "type": "string",
                    "enum": ["morning", "afternoon"],
                    "description": (
                        "Optional time period requested by the customer."
                    ),
                },
            },
            "required": [
                "service_id",
                "appointment_date",
            ],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "select_appointment_time",
        "description": (
            "Select an available appointment time explicitly chosen "
            "by the customer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_time": {
                    "type": "string",
                    "description": (
                        "Appointment time in 24-hour HH:MM format. "
                        "For example: 09:00 or 13:00."
                    ),
                }
            },
            "required": ["appointment_time"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "save_customer_name",
        "description": (
            "Save the customer's name when the customer explicitly "
            "provides their name."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "The customer's explicitly provided name."
                    ),
                }
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "book_appointment",
        "description": (
            "Book an available dental appointment for the current customer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service_id": {
                    "type": "integer",
                    "description": "The ID of the selected service.",
                },
                "appointment_date": {
                    "type": "string",
                    "description": (
                        "Appointment date in YYYY-MM-DD format."
                    ),
                },
                "appointment_time": {
                    "type": "string",
                    "description": (
                        "Appointment time in 24-hour HH:MM format."
                    ),
                },
            },
            "required": [
                "service_id",
                "appointment_date",
                "appointment_time",
            ],
            "additionalProperties": False,
        },
    },
]


# ============================================================
# TELEGRAM COMMAND
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "Здравствуйте! 👋 Я виртуальный администратор стоматологической клиники. "
        "Чем могу помочь?"
    )

def detect_language(text: str) -> str:
    russian_letters = set(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
    )

    english_letters = set(
        "abcdefghijklmnopqrstuvwxyz"
    )

    text = text.lower()

    ru_count = sum(char in russian_letters for char in text)
    en_count = sum(char in english_letters for char in text)

    if ru_count > en_count:
        return "ru"

    return "en"


def language_name(language: str) -> str:
    return {
        "ru": "Russian",
        "en": "English",
    }.get(language, "Russian")

# ============================================================
# MAIN MESSAGE HANDLER
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.message.text:
        return

    user_message = update.message.text
    telegram_id = update.effective_user.id

    state = appointment_states.setdefault(
        telegram_id,
        AppointmentState(),
    )

    # Store the customer's current language so it survives tool calls.
    state.language = detect_language(user_message)

    try:
        # --------------------------------------------------------
        # DATABASE: CUSTOMER
        # --------------------------------------------------------

        customer = get_or_create_customer(
            telegram_id,
        )

        customer_id = customer[0]

        if customer[2]:
            state.customer_name = customer[2]

        save_message(
            customer_id,
            "user",
            user_message,
        )

        previous_messages = get_recent_messages(
            customer_id,
            limit=10,
        )

        conversation = [
            {
                "role": role,
                "content": content,
            }
            for role, content in previous_messages
        ]

        current_date = datetime.now().strftime(
            "%Y-%m-%d"
        )

        instructions = (
            SYSTEM_PROMPT
            + f"\nCURRENT CUSTOMER LANGUAGE: {language_name(state.language)}."
            + f"\nThe final response MUST be entirely in {language_name(state.language)}."
            + "\nDatabase and tool results are DATA ONLY. Translate them before showing them to the customer."
            + "\nNever copy raw English database/tool text into a Russian response."
            + f"\nToday's date is {current_date}."
            + "\n"
            + state.to_prompt()
        )

        logger.info(
            "Processing message | telegram_id=%s",
            telegram_id,
        )

        # --------------------------------------------------------
        # OPENAI REQUEST
        # --------------------------------------------------------

        try:
            response = await client.responses.create(
                model="gpt-5.6-luna",
                instructions=instructions,
                input=conversation,
                tools=TOOLS,
            )

        except Exception:
            logger.exception(
                "OpenAI API request failed"
            )

            await update.message.reply_text(
                "I'm temporarily unable to process your request. "
                "Please try again in a moment."
            )

            return

        # --------------------------------------------------------
        # TOOL LOOP
        # --------------------------------------------------------

        while True:
            tool_calls = [
                item
                for item in response.output
                if item.type == "function_call"
            ]

            if not tool_calls:
                break

            tool_outputs = []

            for tool_call in tool_calls:
                try:
                    arguments = json.loads(
                        tool_call.arguments
                    )

                except json.JSONDecodeError:
                    logger.exception(
                        "Invalid JSON from tool: %s",
                        tool_call.name,
                    )

                    result = {
                        "success": False,
                        "message": (
                            "invalid_appointment_time"
                        ),
                    }

                    tool_outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": tool_call.call_id,
                            "output": json.dumps(result),
                        }
                    )

                    continue

                logger.info(
                    "Tool call: %s",
                    tool_call.name,
                )

                try:
                    result = execute_tool(
                        tool_call.name,
                        arguments,
                        customer_id,
                        state,
                    )

                except Exception:
                    logger.exception(
                        "Tool execution failed: %s",
                        tool_call.name,
                    )

                    result = {
                        "success": False,
                        "message": (
                            "The requested operation could not "
                            "be completed."
                        ),
                    }

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": tool_call.call_id,
                        "output": json.dumps(result),
                    }
                )

            # ----------------------------------------------------
            # SECOND OPENAI REQUEST AFTER TOOLS
            # ----------------------------------------------------

            current_date = datetime.now().strftime(
                "%Y-%m-%d"
            )

            instructions = (
                SYSTEM_PROMPT
                + f"\nToday's date is {current_date}."
                + "\n"
                + state.to_prompt()
            )

            try:
                # Preserve the original user message and complete tool history.
                conversation = conversation + response.output + tool_outputs

                response = await client.responses.create(
                    model="gpt-5.6-luna",
                    instructions=instructions,
                    input=conversation,
                    tools=TOOLS,
                )

            except Exception:
                logger.exception(
                    "OpenAI API request failed after tool execution"
                )

                await update.message.reply_text(
                    "I completed the requested operation, "
                    "but I couldn't generate the final response. "
                    "Please try again."
                )

                return

        # --------------------------------------------------------
        # FINAL RESPONSE
        # --------------------------------------------------------

        assistant_message = response.output_text

        save_message(
            customer_id,
            "assistant",
            assistant_message,
        )

        logger.info(
            "Message processed successfully | telegram_id=%s",
            telegram_id,
        )

        await update.message.reply_text(
            assistant_message
        )

    except Exception:
        logger.exception(
            "Unhandled error while processing Telegram message"
        )

        try:
            await update.message.reply_text(
                "Sorry, something went wrong. "
                "Please try again."
            )
        except Exception:
            logger.exception(
                "Failed to send error message to Telegram"
            )


# ============================================================
# TOOL EXECUTION
# ============================================================

def detect_language(text: str) -> str:
    russian_letters = set(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
    )

    english_letters = set(
        "abcdefghijklmnopqrstuvwxyz"
    )

    text = text.lower()

    ru_count = sum(char in russian_letters for char in text)
    en_count = sum(char in english_letters for char in text)

    if ru_count > en_count:
        return "ru"

    return "en"


def execute_tool(
    tool_name,
    arguments,
    customer_id,
    state,
):
    if tool_name == "get_services":
        return {
            "success": True,
            "services": get_services(),
        }

    if tool_name == "select_service":
        services = get_services()

        requested_name = (
            arguments["service_name"]
            .strip()
            .lower()
        )

        selected_service = next(
            (
                service
                for service in services
                if service["name"].strip().lower()
                == requested_name
            ),
            None,
        )

        if not selected_service:
            return {
                "success": False,
                "message": (
                    "That service is not offered by the clinic."
                ),
            }

        state.operation = "booking"
        state.service_id = selected_service["id"]
        state.service_name = selected_service["name"]

        return {
            "success": True,
            "service_id": selected_service["id"],
            "service_name": selected_service["name"],
        }

    if tool_name == "check_availability":
        requested_period = arguments.get(
            "requested_period"
        )

        result = check_availability(
            service_id=arguments["service_id"],
            appointment_date=arguments["appointment_date"],
            requested_period=requested_period,
        )

        if result["success"]:
            state.service_id = result["service_id"]
            state.service_name = result["service"]
            state.date = result["date"]
            state.period = requested_period

        return result

    if tool_name == "reschedule_appointment":

        if state.operation != "reschedule":
            return {
                "success": False,
                "message": (
                    "No rescheduling operation is active."
                ),
            }

        if (
            state.appointment_id is not None
            and arguments["appointment_id"]
            != state.appointment_id
        ):
            return {
                "success": False,
                "message": (
                    "Invalid appointment selection."
                ),
            }

        result = reschedule_appointment(
            customer_id=customer_id,
            appointment_id=arguments["appointment_id"],
            new_date=arguments["new_date"],
            new_time=arguments["new_time"],
        )

        if result.get("success"):
            state.clear()

        return result

    if tool_name == "start_rescheduling":
        state.operation = "reschedule"

        return {
            "success": True,
            "operation": "reschedule",
            "message": (
                "Rescheduling mode started. "
                "Use the customer's existing appointment."
            ),
        }

    if tool_name == "get_my_appointments":
        appointments = get_customer_appointments(
            customer_id=customer_id,
        )

        if (
            state.operation == "reschedule"
            and len(appointments) == 1
        ):
            appointment = appointments[0]

            state.appointment_id = (
                appointment["appointment_id"]
            )
            state.service_name = appointment["service"]
            state.date = appointment["date"]
            state.time = appointment["time"]

        return {
            "success": True,
            "appointments": appointments,
        }

    if tool_name == "cancel_appointment":
        return cancel_appointment(
            customer_id=customer_id,
            appointment_id=arguments["appointment_id"],
        )

    if tool_name == "select_appointment_time":
        appointment_time = arguments[
            "appointment_time"
        ]

        if appointment_time not in CLINIC_TIMES:
            return {
                "success": False,
                "message": (
                    "That is not a valid clinic appointment time."
                ),
            }

        # --------------------------------------------------------
        # RESCHEDULING
        # --------------------------------------------------------

        if state.operation == "reschedule":

            if state.appointment_id is None:
                return {
                    "success": False,
                    "message": (
                        "No existing appointment has been "
                        "selected for rescheduling."
                    ),
                }

            if state.date is None:
                return {
                    "success": False,
                    "message": (
                        "No new appointment date has "
                        "been selected."
                    ),
                }

            availability = check_availability(
                service_id=state.service_id,
                appointment_date=state.date,
            )

            if not availability["success"]:
                return availability

            if (
                appointment_time
                not in availability["available_times"]
            ):
                return {
                    "success": False,
                    "message": (
                        f"{appointment_time} is not available. "
                        f"Available times are: "
                        f"{', '.join(availability['available_times'])}."
                    ),
                }

            state.time = appointment_time

            result = reschedule_appointment(
                customer_id=customer_id,
                appointment_id=state.appointment_id,
                new_date=state.date,
                new_time=state.time,
            )

            if result.get("success"):
                state.clear()

            return result

        # --------------------------------------------------------
        # NORMAL BOOKING
        # --------------------------------------------------------

        state.time = appointment_time

        return {
            "success": True,
            "message": (
                f"Appointment time selected: "
                f"{appointment_time}."
            ),
            "time": appointment_time,
        }

    if tool_name == "save_customer_name":
        name = arguments["name"].strip()

        if not name:
            return {
                "success": False,
                "message": (
                    "Customer name cannot be empty."
                ),
            }

        update_customer_name(
            customer_id=customer_id,
            name=name,
        )

        state.customer_name = name

        return {
            "success": True,
            "message": (
                "Customer name saved successfully."
            ),
            "name": name,
        }

    if tool_name == "book_appointment":

        if state.operation == "reschedule":
            return {
                "success": False,
                "message": (
                    "The customer is rescheduling an existing "
                    "appointment. Do not create a new appointment. "
                    "Use reschedule_appointment instead."
                ),
            }

        if not state.service_id:
            return {
                "success": False,
                "message": (
                    "No service has been selected."
                ),
            }

        if not state.date:
            return {
                "success": False,
                "message": (
                    "No appointment date has been selected."
                ),
            }

        if not state.time:
            return {
                "success": False,
                "message": (
                    "No appointment time has been selected."
                ),
            }

        if not state.customer_name:
            return {
                "success": False,
                "message": (
                    "Customer name has not been provided."
                ),
            }

        if (
            arguments["service_id"]
            != state.service_id
        ):
            return {
                "success": False,
                "message": (
                    "The requested service does not "
                    "match the selected service."
                ),
            }

        if (
            arguments["appointment_date"]
            != state.date
        ):
            return {
                "success": False,
                "message": (
                    "The requested date does not "
                    "match the selected date."
                ),
            }

        if (
            arguments["appointment_time"]
            != state.time
        ):
            return {
                "success": False,
                "message": (
                    "The requested time does not "
                    "match the selected time."
                ),
            }

        result = book_appointment(
            customer_id=customer_id,
            service_id=state.service_id,
            appointment_date=state.date,
            appointment_time=state.time,
        )

        if result.get("success"):
            state.clear()

        return result

    return {
        "success": False,
        "message": (
            f"Unknown tool: {tool_name}"
        ),
    }


# ============================================================
# TELEGRAM GLOBAL ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "Unhandled Telegram error",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    app.add_error_handler(
        error_handler
    )

    logger.info(
        "Dental AI Receptionist is running..."
    )

    app.run_polling()


if __name__ == "__main__":
    main()