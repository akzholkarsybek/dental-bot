# 🦷 Dental AI Receptionist

An AI-powered dental clinic receptionist built with Python, Telegram, OpenAI, and PostgreSQL.

The bot allows customers to interact with a dental clinic through Telegram and perform common appointment operations using natural language.

## Features

- 🤖 AI-powered Telegram receptionist
- 🦷 Retrieve available dental services from PostgreSQL
- 📅 Book dental appointments
- 🕐 Check appointment availability
- 🌅 Morning/afternoon availability filtering
- ⏰ 24-hour appointment times
- 🚫 Prevent booking appointments in the past
- 👤 Store customer information
- 📋 View confirmed appointments
- ❌ Cancel appointments
- 🔄 Reschedule existing appointments
- 🔒 Prevent unauthorized appointment changes
- 🗄️ PostgreSQL database
- 🧠 Appointment conversation state
- 🧪 Automated tests with pytest
- 🛡️ Error handling and logging
- 🔐 Environment variables for secrets

## Tech Stack

- Python 3
- Telegram Bot API
- OpenAI Responses API
- PostgreSQL
- psycopg2
- python-telegram-bot
- pytest
- python-dotenv

## Architecture

```text
Telegram User
      │
      ▼
Telegram Bot
      │
      ▼
Message Handler
      │
      ▼
OpenAI Responses API
      │
      ├── get_services
      ├── select_service
      ├── check_availability
      ├── select_appointment_time
      ├── book_appointment
      ├── get_my_appointments
      ├── cancel_appointment
      └── reschedule_appointment
              │
              ▼
        PostgreSQL