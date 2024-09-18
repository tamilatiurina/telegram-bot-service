import os
from dotenv import load_dotenv
import logging
import gspread
import requests
import time
from concurrent.futures import ThreadPoolExecutor
from aiogram.dispatcher.filters import CommandStart
from aiogram import Bot, Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from datetime import datetime
import pytz
import asyncio
from gspread import utils
from apscheduler.triggers.cron import CronTrigger
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials

import keyboard as kb

# Load environment variables from the .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Google Sheets Authorization
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
# Load the Google Sheets credentials file from environment
creds_file = os.getenv("CREDS")
creds = Credentials.from_service_account_file(creds_file, scopes=scope)

# Function to refresh credentials if needed
def ensure_credentials_refresh(creds):
    if not creds.valid or creds.expired:
        creds.refresh(Request())
    return creds

# Refresh credentials and authorize gspread
def get_refreshed_sheet():
    global creds
    creds = ensure_credentials_refresh(creds)
    client = gspread.authorize(creds)
    sheet = client.open("Report").sheet1 #OPEN THE SPREADSHEET BY ITS NAME(IN MY CASE - "Report")
    sheet.client.session.timeout = 60  # Set the session timeout
    return sheet

# Initialize bot and dispatcher
API_TOKEN = os.getenv("TOKEN")  # Load the Telegram bot token from environmentgit
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Create a scheduler for task scheduling
scheduler = AsyncIOScheduler()
scheduler.start()

# Executor for handling concurrent sheet updates
executor_pool = ThreadPoolExecutor(max_workers=5)

# Define states for FSM
class ReportForm(StatesGroup):
    choosing_department = State()
    confirming_department = State()
    entering_password = State()
    waiting_for_plan = State()
    waiting_for_serviced = State()
    waiting_for_serviced1 = State()
    waiting_for_load_percentage = State()
    waiting_for_own = State()
    waiting_for_closed_orders = State()
    waiting_for_new_clients = State()
    waiting_for_completed_work = State()
    waiting_for_workers = State()
    waiting_for_worked_hours = State()
    waiting_for_employee_performance = State()
    waiting_for_problems = State()
    waiting_for_plans = State()
    waiting_for_notes = State()
    waiting_for_ready_tech = State()

# Department passwords
DEPARTMENT_PASSWORDS = {
    "rem1": "1",
    "rem2": "2",
    "wash": "3",
    "to": "4",
    "breakup": "5"
}

DEPARTMENT_NAMES = {
    "rem1": "service1",
    "rem2": "service2",
    "wash": "wash",
    "to": "ТО",
    "breakup": "breakup"
}

# Dictionary to store the last report time of users
user_last_report_time = {}
# Define your timezone
TIMEZONE = pytz.timezone('Europe/Kiev')

# Command to set a daily reminder
@dp.message_handler(commands=['reminder'])
async def set_reminder(message: types.Message):
    # Schedule the reminder every day at 4.45 pm Kyiv time (except weekends)
    scheduler.add_job(send_reminder, CronTrigger(day_of_week='mon-fri', hour=16, minute=45, timezone=TIMEZONE), args=[message.chat.id])
    await message.answer("Reminder set for every weekday at 16:45.")

# Function to send the reminder
async def send_reminder(chat_id):
    await bot.send_message(chat_id, "Don't forget to submit your daily report!", reply_markup=kb.main)

# Handle /stop command to end the report submission process
@dp.message_handler(commands=['stop'], state='*')
async def stop_reporting(message: types.Message, state: FSMContext):
    await state.finish()  # Reset the state
    await message.reply("Reporting stopped.")

# Function to check if the user is allowed to submit a report for the department today
def can_send_report(user_id, department):
    current_time = datetime.now(TIMEZONE).date()
    last_reports = user_last_report_time.get(user_id, {})
    last_report_date = last_reports.get(department)
    if last_report_date == current_time:
        return False
    return True

# Start function for handling the /start command or "Create report" button
@dp.message_handler(lambda message: CommandStart() or message.text == "Create Report")
async def start(message: types.Message):
    await message.answer(
            "Hi, you have entered the system to submit a daily report. Please choose the department you want to report for.",
                reply_markup=kb.department_kb
        )

    await ReportForm.choosing_department.set()

# Handle department selection
@dp.callback_query_handler(state=ReportForm.choosing_department)
async def process_department_choice(callback_query: types.CallbackQuery, state: FSMContext):
    department = callback_query.data
    user_id = callback_query.from_user.id

    # Check if the user can submit for this department today
    if can_send_report(user_id, department):
        # Update the department in the state
        await state.update_data(department=department)

        # Fetch the descriptive name for the selected department
        department_name = DEPARTMENT_NAMES.get(department, "department")

        # Confirm the selection with the option to reselect
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(
            callback_query.from_user.id,
            f"You have chosen {department_name}. Confirm your choice?",
            reply_markup=kb.confirm_department_kb
        )
        await ReportForm.confirming_department.set()
    else:
        # Deny sending the report for this department today
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(
            callback_query.from_user.id,
            f"You have already submitted a report for {department} today. Please choose another department."
        )
        await ReportForm.choosing_department.set()


# Handle confirmation or reselecting of department
@dp.callback_query_handler(state=ReportForm.confirming_department)
async def confirm_or_reselect_department(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    user_data = await state.get_data()
    department = user_data.get("department")

    if callback_query.data == 'confirm':
        current_time = datetime.now(TIMEZONE).date()
        if user_id not in user_last_report_time:
            user_last_report_time[user_id] = {}

        user_last_report_time[user_id][department] = current_time

        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(callback_query.from_user.id, "Enter the password for the selected department:")
        await ReportForm.entering_password.set()
    elif callback_query.data == 'reselect':
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(
            callback_query.from_user.id,
            "Please choose the department you want to report for.",
            reply_markup=kb.department_kb
        )
        await ReportForm.choosing_department.set()

# Validate the entered password
@dp.message_handler(state=ReportForm.entering_password)
async def process_password(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    department = user_data.get("department")

    if message.text == DEPARTMENT_PASSWORDS[department]:
        await message.answer("Password correct. Let's start reporting.")
        await ask_first_question(message, state)
    else:
        await message.answer("Incorrect password. Please try again:")

async def ask_first_question(message: types.Message,  state: FSMContext):
    user_data = await state.get_data()
    department = user_data.get("department")

    if department == "rem1" or department == "rem2":
        await message.answer("Planned arrival at work")
        await ReportForm.waiting_for_plan.set()
    elif department == "wash":
        await message.answer("Number of washes from 17:00 to 08:00")
        await ReportForm.waiting_for_serviced.set()
    elif department == "to":
        await message.answer("Planned TO records")
        await ReportForm.waiting_for_plan.set()
    elif department == "breakup":
        await message.answer("Planned breakup records")
        await ReportForm.waiting_for_plan.set()

# Function to check if the input is a valid float
async def is_float(message: types.Message):
    user_input = message.text.replace(',', '.')
    try:
        float(user_input)
        return True
    except ValueError:
        await message.answer("Please enter a valid numeric value. Try again:")
        return False


# Function to check if the input is an integer
async def is_int(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Please enter a numeric value only. Try again:")
        return False
    return True


# Handle the input for the plan
@dp.message_handler(state=ReportForm.waiting_for_plan)
async def process_plan(message: types.Message,  state: FSMContext):
    user_data = await state.get_data()
    department = user_data.get("department")

    # Check if the input is an integer
    if not await is_int(message, state):
        return

    # Store the plan value
    await state.update_data(plan=int(message.text))

    # Ask the next question based on the department
    if department == "rem1" or department == "rem2":
        await message.answer("Readiness plan (departure)")
        await ReportForm.waiting_for_serviced.set()
    elif department == "to":
        await message.answer("Actual amount TO")
        await ReportForm.waiting_for_serviced.set()
    elif department == "breakup":
        await message.answer("Actual amount breakup")
        await ReportForm.waiting_for_serviced.set()

@dp.message_handler(state=ReportForm.waiting_for_serviced)
async def process_serviced(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    department = user_data.get("department")

    # Check if the input is an integer
    if not await is_int(message, state):
        return

    await state.update_data(serviced=int(message.text))

    if department in ["rem1", "rem2"]:
        await message.answer("Quantity of ready equipment")
        await ReportForm.waiting_for_ready_tech.set()
    elif department == "wash":
        await message.answer("Actual number of washes from 08:00 to 17:00")
        await ReportForm.waiting_for_serviced1.set()
    elif department == "to":
        await message.answer("Quantity of own vehicles")
        await ReportForm.waiting_for_own.set()
    elif department == "breakup":
        await message.answer("Load percentage")
        await ReportForm.waiting_for_load_percentage.set()

@dp.message_handler(state=ReportForm.waiting_for_ready_tech)
async def process_ready_tech(message: types.Message, state: FSMContext):
    # Check if the input is an integer
    if not await is_int(message, state):
        return

    await state.update_data(ready_tech=int(message.text))

    await message.answer("Number of closed orders")
    await ReportForm.waiting_for_closed_orders.set()

@dp.message_handler(state=ReportForm.waiting_for_load_percentage)
async def process_load_percentage(message: types.Message, state: FSMContext):
    user_input = message.text.replace(',', '.')

    # Check if the input is a valid float
    if not await is_float(message):
        return

    await state.update_data(load_percentage=float(user_input))

    await message.answer("Number of new clients")
    await ReportForm.waiting_for_new_clients.set()

@dp.message_handler(state=ReportForm.waiting_for_serviced1)
async def process_serviced1(message: types.Message, state: FSMContext):
    # Check if the input is an integer
    if not await is_int(message, state):
        return

    await state.update_data(serviced1=int(message.text))

    await message.answer("Number of own vehicles:")
    await ReportForm.waiting_for_own.set()

@dp.message_handler(state=ReportForm.waiting_for_closed_orders)
async def process_closed_orders(message: types.Message, state: FSMContext):
    # Check if the input is an integer
    if not await is_int(message, state):
        return

    await state.update_data(closed_orders=int(message.text))

    await message.answer("Number of own vehicles:")
    await ReportForm.waiting_for_own.set()

@dp.message_handler(state=ReportForm.waiting_for_own)
async def process_own(message: types.Message,  state: FSMContext):
    # Check if the input is an integer
    if not await is_int(message, state):
        return

    await state.update_data(own=int(message.text))

    await message.answer("Number of new clients:")

    await ReportForm.waiting_for_new_clients.set()

@dp.message_handler(state=ReportForm.waiting_for_new_clients)
async def process_new_clients(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    department = user_data.get("department")

    # Check if the input is an integer
    if not await is_int(message, state):
        return

    await state.update_data(new_clients=int(message.text))

    if department == "wash":
        await message.answer("Number of worked hours")
        await ReportForm.waiting_for_worked_hours.set()
    elif department == "breakup":
        await message.answer("Add notes (if none, send ‘-’):")
        await ReportForm.waiting_for_notes.set()
    else:
        await message.answer("Number of employees:")
        await ReportForm.waiting_for_workers.set()

@dp.message_handler(state=ReportForm.waiting_for_workers)
async def process_workers(message: types.Message, state: FSMContext):
    # Check if the input is an integer
    if not await is_int(message, state):
        return

    await state.update_data(workers=int(message.text))

    await message.answer("Number of worked hours:")
    await ReportForm.waiting_for_worked_hours.set()

@dp.message_handler(state=ReportForm.waiting_for_worked_hours)
async def process_worked_hours(message: types.Message, state: FSMContext):
    user_input = message.text.replace(',', '.')

    if not await is_float(message):
        return

    await state.update_data(worked_hours=float(user_input))

    await message.answer("Employee performance:")
    await ReportForm.waiting_for_employee_performance.set()

@dp.message_handler(state=ReportForm.waiting_for_employee_performance)
async def process_employee_performance(message: types.Message, state: FSMContext):
    user_input = message.text.replace(',', '.')

    if not await is_float(message):
        return

    await state.update_data(employee_performance=float(user_input))

    await message.answer("Problems detected today (if none, send ‘-’):")
    await ReportForm.waiting_for_problems.set()

@dp.message_handler(state=ReportForm.waiting_for_problems)
async def process_problems(message: types.Message, state: FSMContext):
    await state.update_data(problems=message.text)

    await message.answer("Plans for solving (if none, send ‘-’):")
    await ReportForm.waiting_for_plans.set()

@dp.message_handler(state=ReportForm.waiting_for_plans)
async def process_plans(message: types.Message, state: FSMContext):
    await state.update_data(plans=message.text)

    await message.answer("Add notes (if none, send ‘-’):")
    await ReportForm.waiting_for_notes.set()

# Finds the next empty column in the specified row with retry logic for handling API errors
def find_next_empty_column(sheet, row, max_retries=5, base_delay=2):
    """
        Finds the next empty column in the specified row of a Google Sheets spreadsheet.

        Args:
            sheet (gspread.models.Sheet): The Google Sheets sheet object.
            row (int): The row number to search for an empty column.
            max_retries (int): Maximum number of retry attempts in case of API errors.
            base_delay (int): Base delay in seconds before retrying, increased exponentially.

        Returns:
            int: The index of the next empty column.

        Raises:
            gspread.exceptions.APIError: If the API request fails after max_retries.
            requests.exceptions.ConnectionError: If there is a connection error after max_retries.
    """
    col_index = 3  # Starting from column C
    retries = 0

    while True:
        try:
            # Retrieve the value of the cell at the current column index
            cell_value = sheet.cell(row, col_index).value
            if not cell_value:
                return col_index # Return the column index if cell is empty
            col_index += 1
        except (gspread.exceptions.APIError, requests.exceptions.ConnectionError) as e:
            if retries < max_retries:
                # Calculate delay with exponential backoff
                delay = base_delay * (2 ** retries)
                retries += 1
                logger.warning(f"Retrying to find empty column after {delay} seconds. Error: {e}")
                time.sleep(delay) # Pause before retrying
            else:
                logger.error(f"Failed to find empty column after {max_retries} attempts. Error: {e}")
                raise

@dp.message_handler(state=ReportForm.waiting_for_notes)
async def process_notes(message: types.Message, state: FSMContext):
    """
        Processes and saves user notes to the Google Sheets document.

        Args:
            message (types.Message): The message object containing user input.
            state (FSMContext): The state context for managing conversation states.

        Returns:
            None
        """
    # Save the received notes to the state
    await state.update_data(notes=message.text)

    await message.answer("Your report has been successfully sent!", reply_markup=kb.main)

    sheet = get_refreshed_sheet()

    # Retrieve user data from the state
    user_data = await state.get_data()
    department = user_data.get("department")

    # Define starting rows for different departments
    department_start_rows = {
        "rem1": 4,
        "rem2": 18,
        "wash": 32,
        "to": 43,
        "breakup": 55
    }

    # Get the starting row for the specified department
    department_start_row = department_start_rows[department]

    # Determine the next empty column in the department's starting row
    next_column_index = find_next_empty_column(sheet, department_start_row)

    # Asynchronously update the Google Sheet
    asyncio.create_task(update_sheet_async(sheet, department, department_start_row, next_column_index, user_data))

    # Finish the FSM context
    await state.finish()

async def update_sheet_async(sheet, department, start_row, next_column_index, user_data, max_retries=5, base_delay=2):
    """
        Updates the Google Sheets document with the user data asynchronously.

        Args:
            sheet (gspread.models.Sheet): The Google Sheets sheet object.
            department (str): The department for which data is being updated.
            start_row (int): The starting row index for updates.
            next_column_index (int): The index of the next empty column.
            user_data (dict): Dictionary containing user data to be updated.
            max_retries (int): Maximum number of retry attempts in case of API errors.
            base_delay (int): Base delay in seconds before retrying, increased exponentially.

        Returns:
            None

        Raises:
            gspread.exceptions.APIError: If the API request fails after max_retries.
            requests.exceptions.RequestException: If a request error occurs after max_retries.
    """
    updates = []
    next_column_letter = utils.rowcol_to_a1(1, next_column_index)[0]
    next_column_letter_for_plan = utils.rowcol_to_a1(1, next_column_index + 1)[0]

    sheet.update_acell(f"{next_column_letter}{start_row}", datetime.now().strftime("%d/%m/%Y"))

    # Define the update patterns for different departments
    department_updates = {
        "wash": [
            ('serviced', 1),
            ('serviced1', 2),
            ('own', 3),
            ('new_clients', 4),
            ('worked_hours', 5),
            ('employee_performance', 6),
            ('problems', 7),
            ('plans', 8),
            ('notes', 9)
        ],
        "rem1": [
            ('plan', 1, next_column_letter_for_plan),
            ('serviced', 2, next_column_letter_for_plan),
            ('ready_tech', 3),
            ('own', 4),
            ('closed_orders', 5),
            ('new_clients', 6),
            ('workers', 7),
            ('worked_hours', 8),
            ('employee_performance', 9),
            ('problems', 10),
            ('plans', 11),
            ('notes', 12)
        ],
        "rem2": [
            ('plan', 1, next_column_letter_for_plan),
            ('serviced', 2, next_column_letter_for_plan),
            ('ready_tech', 3),
            ('own', 4),
            ('closed_orders', 5),
            ('new_clients', 6),
            ('workers', 7),
            ('worked_hours', 8),
            ('employee_performance', 9),
            ('problems', 10),
            ('plans', 11),
            ('notes', 12)
        ],
        "to": [
            ('plan', 1, next_column_letter_for_plan),
            ('serviced', 2),
            ('own', 3),
            ('new_clients', 4),
            ('workers', 5),
            ('worked_hours', 6),
            ('employee_performance', 7),
            ('problems', 8),
            ('plans', 9),
            ('notes', 10)
        ],
        "breakup": [
            ('plan', 1, next_column_letter_for_plan),
            ('serviced', 2),
            ('load_percentage', 3),
            ('new_clients', 4),
            ('notes', 5)
        ]
    }

    # Prepare the updates for the sheet
    for item in department_updates.get(department, []):
        column_letter = next_column_letter if len(item) == 2 else item[2]
        updates.append({
            'range': f"{column_letter}{start_row + item[1]}",
            'values': [[user_data.get(item[0])]]
        })
        time.sleep(0.01) # Brief delay to avoid overwhelming the API

    # Retry logic with exponential backoff for batch updates
    for attempt in range(max_retries):
        try:
            # Try to perform the batch update
            sheet.batch_update(updates)
            logger.info(f"Successfully updated Google Sheets on attempt {attempt + 1}")
            break  # Exit the retry loop if successful
        except (gspread.exceptions.APIError, requests.exceptions.RequestException) as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(
                    f"Failed to update Google Sheets (attempt {attempt + 1}/{max_retries}). Retrying in {delay} seconds. Error: {e}")
                await asyncio.sleep(delay)  # Wait before retrying
            else:
                logger.error(f"Failed to update Google Sheets after {max_retries} attempts. Error: {e}")
                await bot.send_message(user_data['chat_id'], "An error occurred while recording the report. Please try again later.")
                return

async def on_startup(dp):
    """
       Called when the bot starts up.

       Args:
           dp (Dispatcher): The Dispatcher instance.

       Returns:
           None
    """
    print("Bot is starting...")

async def on_shutdown(dp):
    """
        Called when the bot shuts down.

        Args:
            dp (Dispatcher): The Dispatcher instance.

        Returns:
            None
    """
    print("Bot is shutting down...")

if __name__ == '__main__':
    dp.register_message_handler(stop_reporting, commands=['stop'], state='*')
    dp.register_message_handler(set_reminder, commands=['reminder'], state='*')
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)

