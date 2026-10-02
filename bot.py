"""
«Ассистент Екатерины» — Telegram-бот на aiogram 3.
Запуск: python bot.py (консоль должна оставаться открытой)
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, Message, ReplyKeyboardMarkup,
)

# ── НАСТРОЙКИ ─────────────────────────────────────────────────
TOKEN = ""YOUR_BOT_TOKEN_HERE""
ADMIN_ID =  0        # ← сюда вставьте свой ID (узнать: /myid у бота), потом перезапустить
LEADS_FILE = "leads.json"

router = Router()

# ── СОСТОЯНИЯ АНКЕТЫ ─────────────────────────────────────────
class Lead(StatesGroup):
    name = State()
    contact_method = State()
    contact = State()
    task = State()
    confirm = State()

# ── ТЕКСТЫ ────────────────────────────────────────────────────
WELCOME = ("Привет! 👋 Я ассистент Екатерины Филатовой — специалиста по нейросетям.\n\n"
           "Помогаю разобраться с услугами и подобрать то, что решит именно вашу задачу. "
           "Выберите раздел или просто напишите вопрос.")
FALLBACK = ("Давайте вернёмся к вашей задаче 🙂\n"
            "Выберите раздел в меню или запишитесь на бесплатную консультацию.")

SERVICES = {
    "cards": {"btn": "🛒 Карточки товара", "short": "Карточки товара",
        "text": "🛒 <b>Карточки товара для маркетплейсов</b>\n\nПродающие описания, SEO-оптимизация и инфографика для Wildberries, Ozon и Яндекс.Маркета.\n\n⏱ Срок: 1–2 дня\n📈 Результат: рост CTR и конверсии в покупку"},
    "photo": {"btn": "📷 Фото для маркетплейсов", "short": "Фото для маркетплейсов",
        "text": "📷 <b>Фото для маркетплейсов</b>\n\nПредметные фото, фоны и инфографика с помощью нейросетей — без студийных съёмок. Быстрее и дешевле классической фотографии.\n\n⏱ Срок: 3–5 дней\n📈 Результат: карточка выделяется в поиске и выдаче"},
    "content": {"btn": "📝 Контент-план", "short": "Контент-план",
        "text": "📝 <b>Контент-план для соцсетей</b>\n\nПлан публикаций на месяц с помощью ИИ: темы, тексты, идеи визуала.\n\n⏱ Срок: 2–3 дня\n📈 Результат: регулярный контент без выгорания"},
    "landing": {"btn": "🌐 Лендинг", "short": "Лендинг",
        "text": "🌐 <b>Лендинг под ключ</b>\n\nОдностраничный сайт, созданный с помощью нейросетей. Адаптивный дизайн под все устройства.\n\n⏱ Срок: 5 дней\n📈 Результат: страница, которая приводит заявки"},
    "bot": {"btn": "🤖 Чат-боты и боты с ИИ", "short": "Чат-бот / бот с ИИ",
        "text": "🤖 <b>Чат-боты и боты с ИИ</b>\n\nБоты для Telegram, WhatsApp и сайта: автоматические ответы, запись клиентов, продажи и поддержка 24/7.\n\n⏱ Срок: 2–3 недели\n📈 Результат: экономия времени и круглосуточная работа бизнеса"},
}

FAQ = {
    "price": "💰 Стоимость рассчитывается индивидуально после короткого брифа — вы платите только за то, что действительно нужно. Обсудите задачу на бесплатной консультации — Екатерина назовёт цену под ваш случай 🙂",
    "terms": "⏱ Сроки по услугам:\n• Карточки товара — 1–2 дня\n• Контент-план — 2–3 дня\n• Фото — 3–5 дней\n• Лендинг — 5 дней\n• Чат-бот — 2–3 недели",
    "what": "🤖 Нейросеть — это программа, обученная на миллионах примеров. Представьте очень начитанного помощника: вы описываете задачу — он готовит тексты, фото или сайт. А Екатерина проверяет результат и доводит его до профессионального уровня.",
    "why": "⚡ Нейросети работают быстрее и дешевле классических студий, а качество — на уровне профессионалов. Все материалы Екатерина дорабатывает вручную: скорость ИИ плюс живой экспертный взгляд.",
    "examples": "📁 Примеры по вашей нише Екатерина покажет на бесплатной консультации — так вы увидите работы, релевантные именно вашей задаче.\n\nЗаписаться? Нажмите «📅 Записаться на консультацию».",
}

def esc(s: str) -> str:
    """Экранирование пользовательского текста для HTML-режима."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ── КЛАВИАТУРЫ ────────────────────────────────────────────────
def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛠 Услуги"), KeyboardButton(text="❓ Частые вопросы")],
        [KeyboardButton(text="📅 Записаться на консультацию")],
    ], resize_keyboard=True, input_field_placeholder="Напишите вопрос или выберите раздел…")

def services_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=s["btn"], callback_data=f"service:{k}")]
            for k, s in SERVICES.items()]
    rows.append([InlineKeyboardButton(text="← В главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def service_actions_kb(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Записаться на консультацию", callback_data=f"lead_service:{key}")],
        [InlineKeyboardButton(text="← Другая услуга", callback_data="back_services")],
    ])

def faq_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Сколько стоит?", callback_data="faq:price")],
        [InlineKeyboardButton(text="⏱ Сроки выполнения", callback_data="faq:terms")],
        [InlineKeyboardButton(text="🤖 Что такое нейросети?", callback_data="faq:what")],
        [InlineKeyboardButton(text="⚡ Почему ИИ, а не человек?", callback_data="faq:why")],
        [InlineKeyboardButton(text="📁 Примеры работ", callback_data="faq:examples")],
        [InlineKeyboardButton(text="← В главное меню", callback_data="back_main")],
    ])

def method_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✈️ Telegram", callback_data="lead_method:tg")],
        [InlineKeyboardButton(text="💬 WhatsApp", callback_data="lead_method:wa")],
    ])

def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить запись", callback_data="lead_confirm:yes")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="lead_confirm:no")],
    ])

def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

def skip_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Пропустить ⏭")]], resize_keyboard=True)

def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Отправить номер", request_contact=True)]],
        resize_keyboard=True)

# ── КОМАНДЫ ───────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME, reply_markup=main_menu_kb())

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено. Чем ещё помочь? 🙂", reply_markup=main_menu_kb())

@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    await message.answer(f"Ваш ID: <code>{message.from_user.id}</code>\n"
                         f"Вставьте его в ADMIN_ID в коде и перезапустите бота.")

# ── КНОПКИ ГЛАВНОГО МЕНЮ ─────────────────────────────────────
@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME, reply_markup=main_menu_kb())


@router.message(Command("services"))
async def cmd_services(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Вот что делает Екатерина 🛠", reply_markup=services_kb())


@router.message(Command("faq"))
async def cmd_faq(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Частые вопросы — выберите тему:", reply_markup=faq_kb())


@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext) -> None:
    await state.set_state(Lead.name)
    await state.update_data(service_key=None)
    await message.answer("Отлично! Как вас зовут?", reply_markup=cancel_kb())

@router.message(F.text == "🛠 Услуги")
async def show_services(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Вот что делает Екатерина 🛠", reply_markup=services_kb())

@router.message(F.text == "❌ Отмена")
async def cancel_btn(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено. Чем ещё помочь? 🙂", reply_markup=main_menu_kb())

@router.message(F.text == "❓ Частые вопросы")
async def show_faq(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Частые вопросы — выберите тему:", reply_markup=faq_kb())

@router.message(F.text == "📅 Записаться на консультацию")
async def book_menu(message: Message, state: FSMContext) -> None:
    await state.set_state(Lead.name)
    await state.update_data(service_key=None)
    await message.answer("Отлично! Как вас зовут?", reply_markup=cancel_kb())

# ── УСЛУГИ И FAQ (кнопки) ────────────────────────────────────
@router.callback_query(F.data.startswith("service:"))
async def show_service(cb: CallbackQuery) -> None:
    key = cb.data.split(":", 1)[1]
    s = SERVICES.get(key)
    if s:
        await cb.message.answer(s["text"], reply_markup=service_actions_kb(key))
    await cb.answer()

@router.callback_query(F.data == "back_services")
async def back_services(cb: CallbackQuery) -> None:
    await cb.message.answer("Вот что делает Екатерина 🛠", reply_markup=services_kb())
    await cb.answer()

@router.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.answer(WELCOME, reply_markup=main_menu_kb())
    await cb.answer()

@router.callback_query(F.data.startswith("faq:"))
async def show_faq_answer(cb: CallbackQuery) -> None:
    answer = FAQ.get(cb.data.split(":", 1)[1])
    if answer:
        await cb.message.answer(answer)
    await cb.answer()

# ── АНКЕТА ЗАЯВКИ ────────────────────────────────────────────
@router.callback_query(F.data.startswith("lead_service:"))
async def book_service(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Lead.name)
    await state.update_data(service_key=cb.data.split(":", 1)[1])
    await cb.message.answer("Отлично! Как вас зовут?", reply_markup=cancel_kb())
    await cb.answer()

@router.message(Lead.name, F.text)
async def process_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not 2 <= len(name) <= 50:
        await message.answer("Введите имя — от 2 до 50 символов.")
        return
    await state.update_data(name=name)
    await state.set_state(Lead.contact_method)
    await message.answer(f"Приятно познакомиться, {esc(name)}! Куда Екатерине удобнее написать?",
                         reply_markup=method_kb())

@router.callback_query(Lead.contact_method, F.data.startswith("lead_method:"))
async def process_method(cb: CallbackQuery, state: FSMContext) -> None:
    method = cb.data.split(":", 1)[1]
    await state.update_data(contact_method=method)
    await state.set_state(Lead.contact)
    if method == "tg":
        await cb.message.answer("Отправьте ваш ник в Telegram, например: @username",
                                reply_markup=cancel_kb())
    else:
        await cb.message.answer("Нажмите «📞 Отправить номер» — или пришлите номер текстом: +7XXXXXXXXXX",
                                reply_markup=phone_kb())
    await cb.answer()

@router.message(Lead.contact_method)
async def hint_method(message: Message) -> None:
    await message.answer("Выберите вариант кнопкой под сообщением 🙂")

@router.message(Lead.contact, F.contact)
async def process_phone_btn(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    if phone.startswith("+8") and len(phone) == 12:
        phone = "+7" + phone[2:]
    await state.update_data(contact=phone)
    await state.set_state(Lead.task)
    await message.answer("Коротко опишите вашу задачу — Екатерина подготовится к разговору.\n\n"
                         "Или нажмите «Пропустить ⏭».", reply_markup=skip_kb())

@router.message(Lead.contact, F.text)
async def process_contact_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    value = message.text.strip()

    if data.get("contact_method") == "tg":
        if not re.fullmatch(r"@?[A-Za-z0-9_]{4,32}", value):
            await message.answer("Это похоже не на ник 🙂 Формат: @username — попробуйте ещё раз.")
            return
        contact = value if value.startswith("@") else "@" + value
    else:
        digits = re.sub(r"[\s\-()]", "", value)
        if not re.fullmatch(r"\+?\d{10,15}", digits):
            await message.answer("Отправьте номер в формате +7XXXXXXXXXX — попробуйте ещё раз.")
            return
        contact = digits if digits.startswith("+") else "+" + digits
        if contact.startswith("+8") and len(contact) == 12:
            contact = "+7" + contact[2:]

    await state.update_data(contact=contact)
    await state.set_state(Lead.task)
    await message.answer("Коротко опишите вашу задачу — Екатерина подготовится к разговору.\n\n"
                         "Или нажмите «Пропустить ⏭».", reply_markup=skip_kb())

@router.message(Lead.task, F.text)
async def process_task(message: Message, state: FSMContext) -> None:
    task = None if message.text.strip() == "Пропустить ⏭" else message.text.strip()[:1000]
    await state.update_data(task=task)
    data = await state.get_data()
    service = SERVICES.get(data.get("service_key"), {}).get("short", "не выбрана — обсудим на консультации")
    method = "Telegram" if data.get("contact_method") == "tg" else "WhatsApp"
    await state.set_state(Lead.confirm)
    await message.answer(
        "Проверьте, всё ли верно:\n\n"
        f"👤 Имя: {esc(data['name'])}\n"
        f"🔗 Связь: {method} — {esc(data['contact'])}\n"
        f"🛠 Услуга: {service}\n"
        f"📝 Задача: {esc(task) if task else 'не указана'}",
        reply_markup=confirm_kb())

@router.message(Lead.confirm)
async def hint_confirm(message: Message) -> None:
    await message.answer("Нажмите «✅ Подтвердить запись» или «❌ Отменить» 🙂")

@router.callback_query(Lead.confirm, F.data == "lead_confirm:yes")
async def confirm_yes(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    service = SERVICES.get(data.get("service_key"), {}).get("short", "не выбрана")
    lead = {
        "name": data.get("name", "—"),
        "service": service,
        "contact_method": "Telegram" if data.get("contact_method") == "tg" else "WhatsApp",
        "contact": data.get("contact", "—"),
        "task": data.get("task") or "не указана",
        "user_id": cb.from_user.id,
        "username": f"@{cb.from_user.username}" if cb.from_user.username else "—",
        "created_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
    save_lead(lead)
    await notify_admin(bot, lead)
    await state.clear()
    await cb.message.answer(f"Готово, {esc(lead['name'])}! ✅ Заявка отправлена.\n\n"
                            "Екатерина свяжется с вами в течение 15 минут.",
                            reply_markup=main_menu_kb())
    await cb.answer()

@router.callback_query(Lead.confirm, F.data == "lead_confirm:no")
async def confirm_no(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.answer("Действие отменено. Чем ещё помочь? 🙂", reply_markup=main_menu_kb())
    await cb.answer()

@router.message(StateFilter(Lead.name, Lead.contact, Lead.task))
async def fsm_need_text(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте сообщение текстом 🙂")

# ── FALLBACK ─────────────────────────────────────────────────
@router.message(StateFilter(None))
async def fallback(message: Message) -> None:
    await message.answer(FALLBACK, reply_markup=main_menu_kb())

@router.callback_query()
async def stale_callback(cb: CallbackQuery) -> None:
    await cb.answer()

# ── ЗАЯВКИ ────────────────────────────────────────────────────
def save_lead(lead: dict) -> None:
    leads = []
    if os.path.exists(LEADS_FILE):
        try:
            with open(LEADS_FILE, encoding="utf-8") as f:
                leads = json.load(f)
        except Exception:
            leads = []
    leads.append(lead)
    with open(LEADS_FILE, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)

async def notify_admin(bot: Bot, lead: dict) -> None:
    if not ADMIN_ID:
        logging.warning("ADMIN_ID not set — lead saved to file only")
        return
    text = ("🆕 <b>Новая заявка на консультацию</b>\n\n"
            f"👤 Имя: {esc(lead['name'])}\n"
            f"🛠 Услуга: {lead['service']}\n"
            f"🔗 Связь: {lead['contact_method']} — {esc(lead['contact'])}\n"
            f"📝 Задача: {esc(lead['task'])}\n"
            f"👤 {lead['username']} (id: {lead['user_id']})\n"
            f"🕒 {lead['created_at']}")
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception:
        logging.exception("Failed to notify admin")

# ── ЗАПУСК ────────────────────────────────────────────────────
async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="cancel", description="Отменить действие"),
        BotCommand(command="myid", description="Узнать свой ID"),
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot started. Press Ctrl+C to stop.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())