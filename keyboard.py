from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

department_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton("Service 1", callback_data='rem1')],
    [InlineKeyboardButton("Service 2", callback_data='rem2')],
    [InlineKeyboardButton("Wash", callback_data='wash')],
    [InlineKeyboardButton("ТО", callback_data='to')],
    [InlineKeyboardButton("Breakup", callback_data='breakup')]
])

confirm_department_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton("Confirm", callback_data='confirm')],
    [InlineKeyboardButton("Reselect", callback_data='reselect')]
])

main = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='Create Report')]], resize_keyboard=True)
