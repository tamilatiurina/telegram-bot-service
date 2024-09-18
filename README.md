# Daily Report Bot for Service Station

This bot is designed to automate the process of submitting daily reports for various departments on service station. It collects data from employees, validates it, and logs it into a Google Sheet. The bot supports multiple departments, custom password validation for each department, and ensures reports are submitted only once per day per department.

## Features

- **Department-specific Reports**: Users can submit reports for different departments, each with specific metrics.
- **Daily Submission Control**: Prevents users from submitting more than one report per department per day.
- **Google Sheets Integration**: Stores the reports in a designated Google Sheet.
- **Reminder Feature**: Sends daily reminders at a specified time to remind users to submit their reports.
- **Flexible Question Flow**: Custom question flow based on the department selected.
- **Password Protection**: Each department is password-protected to ensure only authorized personnel can submit reports.

## Prerequisites

- **Python 3.8+**
- **Telegram Bot API token**: You can create a bot and get an API token from the [BotFather](https://core.telegram.org/bots#botfather).
- **Google Service Account Key**: Create a Google service account and download the JSON credentials file to enable Google Sheets API access.
- **Google Sheets Document**: Set up a Google Sheet to store the reports.

## Installation

### 1. Clone the Repository:
```bash
git clone https://github.com/yourusername/daily-report-bot.git
cd daily-report-bot
```
### 2. Install Dependencies:
```bash
pip install -r requirements.txt
```
### 3. Configure Google Sheets:
- Create a Google Sheet and share it with the service account email found in the JSON credentials file.
- Set up the sheet format according to the departments and columns.
### 4. Set Up Environment Variables (create a .env file with the following environment variables):
```bash
API_TOKEN=your_telegram_bot_api_token
GOOGLE_SHEET_CREDENTIALS=path_to_google_credentials.json
```
### 5. Run the Bot:
```bash
python bot.py
```

## Usage

### Commands
- ```/start```: Start the report submission process.
- ```/reminder```: Set daily reminders for report submission.
- ```/stop```: Stop the reporting process for the current session.
### How It Works
1. The bot prompts the user to select a department(service1, service2, wash, TO - technical analysis, breakup - tyre alignment).
2. Users must enter the correct password for the department.
3. Based on the department, users are asked a series of questions about their daily work.
4. Once the data is collected, it is logged into a Google Sheet.
5. The bot can remind users daily to submit reports at a specific time.
### Departments and Passwords
Department | Password
--- | --- | 
Service 1 | 1
Service 2 | 2
Wash | 3
TO | 4
Breakup | 5
### Google Sheet Structure
- The Google Sheet is divided into sections for each department.
- Each row corresponds to different metrics, and each column is used for a new day's report.
### Reminder Schedule
- The bot can send reminders at a fixed time every day (configurable via the /reminder command).

## Contributing
Contributions are welcome! If you find a bug or have a suggestion, feel free to open an issue or submit a pull request.

## License
This project is licensed under the MIT License. See the ```LICENSE``` file for details.
