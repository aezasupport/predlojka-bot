import os
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiosqlite

BOT_TOKEN = os.getenv("BOT_TOKEN", "8751382520:AAGP0pP2ZgtZImjrjHDXjBmlBfxtC35JWlA")
MAIN_ADMIN = 6846734926

DB_PATH = "suggestions.db"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class SetupStates(StatesGroup):
    waiting_channel_id = State()
    waiting_admin_id = State()
    waiting_broadcast = State()
    waiting_caption = State()
    waiting_text_start = State()
    waiting_text_approved = State()
    waiting_text_rejected = State()
    waiting_blacklist_add = State()
    waiting_subscribe_channel = State()
    waiting_suggestion = State()

async def init_db():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                is_banned BOOLEAN DEFAULT FALSE,
                suggested_count INTEGER DEFAULT 0,
                approved_count INTEGER DEFAULT 0
            )''')
            await db.execute('''CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )''')
            await db.execute('''CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )''')
            await db.execute('''CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE,
                channel_name TEXT
            )''')
            await db.execute('''CREATE TABLE IF NOT EXISTS subscribe_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE,
                channel_name TEXT,
                channel_username TEXT
            )''')
            
            await db.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (MAIN_ADMIN,))
            
            defaults = {
                'caption': 'Выкл',
                'auto_mode': 'Выкл',
                'anon_mode': 'Выкл',
                'text_start': '👋 Привет! Это бот для отправки предложений.\n\nПросто отправь сообщение, и оно попадёт на модерацию.',
                'text_approved': '✅ Ваше предложение опубликовано!',
                'text_rejected': '❌ Ваше предложение отклонено.'
            }
            
            for key, value in defaults.items():
                await db.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, value))
            
            await db.commit()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка БД: {e}")
        raise

async def get_setting(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = await cursor.fetchone()
        return result[0] if result else ""

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
        await db.commit()

async def is_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
        return await cursor.fetchone() is not None

async def add_admin_db(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (user_id,))
        await db.commit()

async def remove_admin_db(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
        await db.commit()

async def get_all_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT user_id FROM admins')
        return await cursor.fetchall()

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT user_id, username FROM users')
        return await cursor.fetchall()

async def get_all_channels():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT id, channel_id, channel_name FROM channels')
        return await cursor.fetchall()

async def get_all_subscribe_channels():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT id, channel_id, channel_name, channel_username FROM subscribe_channels')
        return await cursor.fetchall()

async def add_channel_db(channel_id: str, channel_name: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR REPLACE INTO channels (channel_id, channel_name) VALUES (?, ?)', 
                        (channel_id, channel_name))
        await db.commit()

async def remove_channel_db(channel_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
        await db.commit()

async def add_subscribe_channel_db(channel_id: str, channel_name: str = "", channel_username: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR REPLACE INTO subscribe_channels (channel_id, channel_name, channel_username) VALUES (?, ?, ?)', 
                        (channel_id, channel_name, channel_username))
        await db.commit()

async def remove_subscribe_channel_db(channel_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM subscribe_channels WHERE channel_id = ?', (channel_id,))
        await db.commit()

async def ban_user_db(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET is_banned = TRUE WHERE user_id = ?', (user_id,))
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return await cursor.fetchone()

async def create_user(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
        await db.commit()

async def update_stats(user_id: int, field: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f'UPDATE users SET {field} = {field} + 1 WHERE user_id = ?', (user_id,))
        await db.commit()

async def check_subscription(user_id: int) -> bool:
    channels = await get_all_subscribe_channels()
    for channel in channels:
        try:
            member = await bot.get_chat_member(channel[1], user_id)
            if member.status in ['left', 'kicked']:
                return False
        except:
            pass
    return True

async def get_subscribe_keyboard():
    builder = InlineKeyboardBuilder()
    channels = await get_all_subscribe_channels()
    
    for ch in channels:
        ch_id, ch_name, ch_username = ch[1], ch[2], ch[3]
        channel_link = f"https://t.me/{ch_username}" if ch_username else f"https://t.me/{ch_id}"
        display_name = ch_name or ch_username or "Канал"
        
        builder.row(
            InlineKeyboardButton(text=f"📢 {display_name}", url=channel_link)
        )
    
    builder.row(InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription"))
    return builder.as_markup()

async def get_admin_panel():
    builder = InlineKeyboardBuilder()
    auto_mode = await get_setting('auto_mode')
    anon_mode = await get_setting('anon_mode')
    auto_emoji = "🔴 Выкл" if auto_mode == "Выкл" else "🟢 Вкл"
    anon_emoji = "🔴 Выкл" if anon_mode == "Выкл" else "🟢 Вкл"
    
    builder.row(InlineKeyboardButton(text="➕ Подвязать канал", callback_data="admin_add_channel"))
    builder.row(InlineKeyboardButton(text="👥 Админы", callback_data="admin_manage_admins"))
    builder.row(InlineKeyboardButton(text="✏️ Тексты", callback_data="admin_texts"))
    builder.row(InlineKeyboardButton(text="▶️ Быстрые ответы", callback_data="admin_quick_replies"))
    builder.row(InlineKeyboardButton(text="📝 Подпись", callback_data="admin_caption"))
    builder.row(InlineKeyboardButton(text="💬 Рассылка", callback_data="admin_broadcast"))
    builder.row(InlineKeyboardButton(text="🔗 Подписка на канал", callback_data="admin_subscribe_channels"))
    builder.row(InlineKeyboardButton(text="🚫 Черный список", callback_data="admin_blacklist"))
    builder.row(InlineKeyboardButton(text="❌ Удалить бота", callback_data="admin_delete"))
    
    channels = await get_all_channels()
    seen = set()
    for i, ch in enumerate(channels, 1):
        ch_id = ch[1]
        if ch_id in seen:
            continue
        seen.add(ch_id)
        ch_name = ch[2] or f"Канал {i}"
        builder.row(
            InlineKeyboardButton(text=f"📢 {ch_name} | {ch_id}", callback_data=f"channel_view_{ch_id}"),
            InlineKeyboardButton(text="🗑", callback_data=f"channel_remove_{ch_id}")
        )
    
    builder.row(InlineKeyboardButton(text=f"⚙️ Автоматический режим: {auto_emoji}", callback_data="toggle_auto"))
    builder.row(InlineKeyboardButton(text=f"🕵️ Анонимный режим: {anon_emoji}", callback_data="toggle_anon"))
    
    return builder.as_markup()

async def get_anonymity_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🕵️ Анонимно", callback_data="anon_yes"),
        InlineKeyboardButton(text="✍️ Подписать", callback_data="anon_no")
    )
    return builder.as_markup()

async def get_admins_keyboard():
    builder = InlineKeyboardBuilder()
    admins = await get_all_admins()
    
    builder.row(InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add_new"))
    
    for admin in admins:
        user_id = admin[0]
        try:
            user = await bot.get_users(user_id)
            username = user.username if user.username else "Нет username"
            name = user.first_name or "Без имени"
        except:
            username = "Не найден"
            name = "Неизвестно"
        
        builder.row(
            InlineKeyboardButton(text=f"👤 {name} (@{username})", callback_data=f"admin_info_{user_id}"),
            InlineKeyboardButton(text="🗑", callback_data=f"admin_remove_{user_id}")
        )
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
    return builder.as_markup()

async def get_subscribe_channels_keyboard():
    builder = InlineKeyboardBuilder()
    channels = await get_all_subscribe_channels()
    
    builder.row(InlineKeyboardButton(text="➕ Добавить канал", callback_data="subscribe_add_new"))
    
    for i, ch in enumerate(channels, 1):
        ch_id, ch_name, ch_username = ch[1], ch[2], ch[3]
        display_name = ch_name or ch_username or f"Канал {i}"
        builder.row(
            InlineKeyboardButton(text=f"📢 {display_name}", callback_data=f"subscribe_info_{ch_id}"),
            InlineKeyboardButton(text="🗑", callback_data=f"subscribe_remove_{ch_id}")
        )
    
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    try:
        user = await get_user(message.from_user.id)
        if not user:
            await create_user(message.from_user.id, message.from_user.username)
            user = await get_user(message.from_user.id)
        
        subscribe_channels = await get_all_subscribe_channels()
        if subscribe_channels:
            is_subscribed = await check_subscription(message.from_user.id)
            if not is_subscribed:
                channels_text = "📢 Для использования бота подпишитесь на каналы:\n\n"
                for ch in subscribe_channels:
                    ch_id, ch_name, ch_username = ch[1], ch[2], ch[3]
                    channel_link = f"@{ch_username}" if ch_username else ch_id
                    channels_text += f"• {ch_name or channel_link}\n"
                
                channels_text += "\nПосле подписки нажмите кнопку ниже:"
                
                await message.reply(
                    channels_text,
                    reply_markup=await get_subscribe_keyboard()
                )
                return
        
        text = await get_setting('text_start')
        await message.reply(f"{text}\n\n📊 Твоя статистика:\nПредложено: {user[3]}\nОдобрено: {user[4]}")
    except Exception as e:
        logger.error(f"Ошибка в /start: {e}")
        await message.reply("❌ Ошибка")

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery):
    try:
        is_subscribed = await check_subscription(callback.from_user.id)
        
        if is_subscribed:
            await callback.answer("✅ Спасибо за подписку!", show_alert=True)
            await callback.message.delete()
            
            user = await get_user(callback.from_user.id)
            if not user:
                await create_user(callback.from_user.id, callback.from_user.username)
                user = await get_user(callback.from_user.id)
            
            text = await get_setting('text_start')
            await callback.message.answer(
                f"{text}\n\n📊 Твоя статистика:\nПредложено: {user[3]}\nОдобрено: {user[4]}"
            )
        else:
            await callback.answer("❌ Вы еще не подписались на все каналы!", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        await callback.answer("❌ Ошибка проверки", show_alert=True)

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    try:
        if message.from_user.id == MAIN_ADMIN or await is_admin(message.from_user.id):
            keyboard = await get_admin_panel()
            await message.reply("🔧 Админ-панель", reply_markup=keyboard)
        else:
            await message.reply("❌ У вас нет доступа")
    except Exception as e:
        logger.error(f"Ошибка в /admin: {e}")

@dp.callback_query(F.data == "admin_add_channel")
async def channel_add_start(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.answer(
            "🔗 Подвязка канала\n\n"
            "1️⃣ Добавьте бота в админы канала (без прав добавления админов)\n"
            "2️⃣ Отправьте ID канала\n\n"
            "💡 Как получить ID:\n"
            "- Перейдите в @getmy_idbot\n"
            "- Нажмите 'Channel'\n"
            "- Выберите канал\n"
            "- Скопируйте ID"
        )
        await callback.answer()
        await state.set_state(SetupStates.waiting_channel_id)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "admin_manage_admins")
async def admin_manage(callback: types.CallbackQuery):
    try:
        keyboard = await get_admins_keyboard()
        await callback.message.edit_text(
            "👥 Управление админами",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "admin_subscribe_channels")
async def subscribe_channels_manage(callback: types.CallbackQuery):
    try:
        keyboard = await get_subscribe_channels_keyboard()
        await callback.message.edit_text(
            "🔗 Каналы для обязательной подписки\n\n"
            "Пользователи должны будут подписаться на эти каналы, чтобы использовать бота.",
            reply_markup=keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "subscribe_add_new")
async def subscribe_add_start(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.answer(
            "➕ Добавление канала для подписки\n\n"
            "Отправьте ID или username канала (например: @channel_name или -1001234567890)"
        )
        await callback.answer()
        await state.set_state(SetupStates.waiting_subscribe_channel)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data.startswith("subscribe_remove_"))
async def subscribe_remove(callback: types.CallbackQuery):
    try:
        channel_id = callback.data.split("_")[-1]
        await remove_subscribe_channel_db(channel_id)
        await callback.answer("✅ Канал удалён из обязательной подписки", show_alert=True)
        keyboard = await get_subscribe_channels_keyboard()
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data.startswith("subscribe_info_"))
async def subscribe_info(callback: types.CallbackQuery):
    try:
        channel_id = callback.data.split("_")[-1]
        await callback.answer(f"📢 Канал: {channel_id}", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data.startswith("channel_view_"))
async def channel_view(callback: types.CallbackQuery):
    try:
        channel_id = callback.data.split("_")[-1]
        channels = await get_all_channels()
        
        channel_info = None
        for ch in channels:
            if ch[1] == channel_id:
                channel_info = ch
                break
        
        if channel_info:
            text = f"📢 Информация о канале\n\n"
            text += f"ID: {channel_id}\n"
            text += f"Название: {channel_info[2] or 'Не указано'}"
            
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
            
            await callback.message.answer(text, reply_markup=builder.as_markup())
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data.startswith("channel_remove_"))
async def channel_remove(callback: types.CallbackQuery):
    try:
        channel_id = callback.data.split("_")[-1]
        await remove_channel_db(channel_id)
        await callback.answer("✅ Канал удалён", show_alert=True)
        keyboard = await get_admin_panel()
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "admin_add_new")
async def admin_add_start(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.answer(
            "➕ Добавление админа\n\n"
            "Отправьте ID пользователя"
        )
        await callback.answer()
        await state.set_state(SetupStates.waiting_admin_id)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data.startswith("admin_remove_"))
async def admin_remove(callback: types.CallbackQuery):
    try:
        user_id = int(callback.data.split("_")[-1])
        if user_id == MAIN_ADMIN:
            await callback.answer("❌ Нельзя удалить главного админа!", show_alert=True)
            return
        
        await remove_admin_db(user_id)
        await callback.answer(f"✅ Админ {user_id} удалён", show_alert=True)
        keyboard = await get_admins_keyboard()
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    try:
        users = await get_all_users()
        await callback.message.answer(
            f"💬 Рассылка\n\n"
            f"В базе {len(users)} пользователей\n\n"
            f"Отправьте текст для рассылки:"
        )
        await callback.answer()
        await state.set_state(SetupStates.waiting_broadcast)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "admin_texts")
async def admin_texts_menu(callback: types.CallbackQuery):
    try:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="✏️ Приветствие", callback_data="text_edit_start"))
        builder.row(InlineKeyboardButton(text="✅ Одобрено", callback_data="text_edit_approved"))
        builder.row(InlineKeyboardButton(text="❌ Отклонено", callback_data="text_edit_rejected"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
        await callback.message.edit_text("✏️ Редактирование текстов", reply_markup=builder.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "text_edit_start")
async def text_edit_start(callback: types.CallbackQuery, state: FSMContext):
    try:
        current = await get_setting('text_start')
        await callback.message.answer(f"✏️ Текст приветствия\n\nТекущий:\n{current}\n\nОтправьте новый:")
        await callback.answer()
        await state.set_state(SetupStates.waiting_text_start)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "text_edit_approved")
async def text_edit_approved(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.answer("✅ Отправьте новый текст для одобрения:")
        await callback.answer()
        await state.set_state(SetupStates.waiting_text_approved)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "text_edit_rejected")
async def text_edit_rejected(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.answer("❌ Отправьте новый текст для отклонения:")
        await callback.answer()
        await state.set_state(SetupStates.waiting_text_rejected)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "admin_caption")
async def caption_settings(callback: types.CallbackQuery, state: FSMContext):
    try:
        current = await get_setting('caption')
        await callback.message.answer(
            f"📝 Подпись к постам\n\n"
            f"Текущее: {current}\n\n"
            f"Отправьте новую подпись или 'отключите'"
        )
        await callback.answer()
        await state.set_state(SetupStates.waiting_caption)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "admin_blacklist")
async def blacklist_menu(callback: types.CallbackQuery):
    try:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="➕ Добавить в ЧС", callback_data="blacklist_add"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
        await callback.message.edit_text("🚫 Черный список", reply_markup=builder.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "blacklist_add")
async def blacklist_add_start(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.answer("🚫 Отправьте ID пользователя для добавления в ЧС:")
        await callback.answer()
        await state.set_state(SetupStates.waiting_blacklist_add)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "toggle_auto")
async def toggle_auto_mode(callback: types.CallbackQuery):
    try:
        current = await get_setting('auto_mode')
        new_value = "Вкл" if current == "Выкл" else "Выкл"
        await set_setting('auto_mode', new_value)
        keyboard = await get_admin_panel()
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer(f"✅ Автоматический режим: {new_value}", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(F.data == "toggle_anon")
async def toggle_anon_mode(callback: types.CallbackQuery):
    try:
        current = await get_setting('anon_mode')
        new_value = "Вкл" if current == "Выкл" else "Выкл"
        await set_setting('anon_mode', new_value)
        keyboard = await get_admin_panel()
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer(f"✅ Анонимный режим: {new_value}", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    try:
        keyboard = await get_admin_panel()
        await callback.message.edit_text("🔧 Админ-панель", reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(F.data == "admin_quick_replies")
async def admin_quick_replies(callback: types.CallbackQuery):
    try:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="➕ Добавить ответ", callback_data="quick_reply_add"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
        await callback.message.edit_text("▶️ Быстрые ответы\n\nЗдесь можно настроить готовые ответы.", reply_markup=builder.as_markup())
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "admin_delete")
async def admin_delete(callback: types.CallbackQuery):
    try:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="⚠️ Да, удалить", callback_data="admin_delete_confirm"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"))
        await callback.message.edit_text(
            "❌ Удалить бота?\n\n"
            "Это действие удалит все данные бота.",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data == "admin_delete_confirm")
async def admin_delete_confirm(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text("❌ Бот будет удалён. Перезапустите его.")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.callback_query(F.data.in_({"anon_yes", "anon_no"}))
async def handle_anonymity_choice(callback: types.CallbackQuery, state: FSMContext):
    try:
        is_anonymous = callback.data == "anon_yes"
        
        data = await state.get_data()
        message = data.get('suggestion_message')
        
        if not message:
            await callback.answer("❌ Ошибка: сообщение не найдено", show_alert=True)
            await state.clear()
            return
        
        username = message.from_user.username or message.from_user.first_name
        user_mention = f"@{username}" if username else f"[{message.from_user.first_name}]"
        user_id = message.from_user.id
        
        anon_mode = await get_setting('anon_mode')
        is_auto_anon = anon_mode == "Вкл"
        
        if message.text:
            content_text = message.text
        elif message.photo and message.caption:
            content_text = message.caption
        else:
            content_text = "Новое предложение"
        
        auto_mode = await get_setting('auto_mode')
        
        if auto_mode == "Вкл":
            caption_setting = await get_setting('caption')
            
            if is_auto_anon or is_anonymous:
                publish_text = content_text
            else:
                if caption_setting and caption_setting != "Выкл":
                    publish_text = f"{content_text}\n\n{caption_setting}\n\nОтправил: {user_mention}"
                else:
                    publish_text = f"{content_text}\n\nОтправил: {user_mention}"
            
            channels = await get_all_channels()
            for channel in channels:
                try:
                    if message.photo:
                        await bot.send_photo(
                            channel[1], 
                            message.photo[-1].file_id, 
                            caption=publish_text
                        )
                    else:
                        await bot.send_message(channel[1], publish_text)
                except Exception as e:
                    logger.error(f"Ошибка автопублики: {e}")
            
            await update_stats(user_id, 'approved_count')
            await callback.message.edit_text("✅ Отправлено в канал!")
        else:
            admin_text = f"📩 Новое предложение\n\n"
            admin_text += f"👤 От: {user_mention}\n"
            admin_text += f"🆔 ID: {user_id}\n"
            admin_text += f"🔒 Анонимно: {'Да' if is_anonymous else 'Нет'}\n\n"
            
            if message.text:
                admin_text += f"📝 Текст:\n{message.text}"
            elif message.photo:
                admin_text += f"📷 Фото: {message.caption or 'Без подписи'}"
            else:
                admin_text += "📨 Сообщение"
            
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"publish_{user_id}_anon_{is_anonymous}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
            )
            builder.row(
                InlineKeyboardButton(text="👤 Инфо", callback_data=f"show_user_{user_id}"),
                InlineKeyboardButton(text="🚫 Забанить", callback_data=f"ban_user_{user_id}")
            )
            
            admins = await get_all_admins()
            success_count = 0
            
            for admin in admins:
                admin_id = admin[0]
                try:
                    if message.photo:
                        await bot.send_photo(
                            chat_id=admin_id,
                            photo=message.photo[-1].file_id,
                            caption=admin_text,
                            reply_markup=builder.as_markup()
                        )
                    else:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=admin_text,
                            reply_markup=builder.as_markup()
                        )
                    success_count += 1
                except Exception as e:
                    logger.warning(f"Не удалось отправить админу {admin_id}: {e}")
            
            await callback.message.edit_text("✅ Отправлено на модерацию!")
            await update_stats(user_id, 'suggested_count')
        
        await state.clear()
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в handle_anonymity_choice: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# --- ДОБАВЛЕННЫЙ ОБРАБОТЧИК ОТКЛОНЕНИЯ (ИСПРАВЛЕНИЕ БАГА) ---
@dp.callback_query(F.data.startswith("reject_"))
async def callback_reject(callback: types.CallbackQuery):
    try:
        user_id = int(callback.data.split("_")[1])
        
        # Удаляем сообщение у админа
        await callback.message.delete()
        
        # Уведомляем пользователя
        try:
            text_rejected = await get_setting('text_rejected')
            await bot.send_message(
                chat_id=user_id,
                text=text_rejected or "❌ Ваше предложение отклонено."
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
        
        await callback.answer("❌ Предложение отклонено", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка отклонения: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
# -------------------------------------------------------------

@dp.callback_query(F.data.startswith("publish_"))
async def callback_publish(callback: types.CallbackQuery):
    try:
        parts = callback.data.split("_")
        user_id = int(parts[1])
        is_anonymous = parts[3] == "True" if len(parts) > 3 else False
        
        logger.info(f"Публикация: user_id={user_id}, is_anonymous={is_anonymous}")
        
        original_text = callback.message.caption or callback.message.text
        
        # Получаем текст предложения (убраны ** из поиска, так как мы их убрали из шаблона)
        if "📝 Текст:" in original_text:
            content_text = original_text.split("📝 Текст:\n")[-1].strip()
        else:
            if "📨 Сообщение" in original_text:
                content_text = ""
            elif "📷 Фото:" in original_text:
                content_text = original_text.split("📷 Фото:")[-1].split("\n")[0].strip()
            else:
                content_text = original_text
        
        # Получаем username если не анонимно
        user_mention = ""
        if not is_anonymous and "👤 От:" in original_text:
            mention_line = original_text.split("👤 От:")[1].split("\n")[0].strip()
            user_mention = mention_line
        
        # Получаем настройку подписи
        caption_setting = await get_setting('caption')
        
        # Формируем итоговый текст для публикации
        if is_anonymous:
            publish_text = content_text
            logger.info(f"Анонимная публикация: {publish_text}")
        else:
            if caption_setting and caption_setting != "Выкл":
                publish_text = f"{content_text}\n\n{caption_setting}\n\nОтправил: {user_mention}"
            else:
                publish_text = f"{content_text}\n\nОтправил: {user_mention}"
            logger.info(f"Публикация с автором: {publish_text}")
        
        channels = await get_all_channels()
        
        if not channels:
            await callback.answer("❌ Нет подключенных каналов!", show_alert=True)
            return
        
        for channel in channels:
            channel_id = channel[1]
            try:
                await bot.send_message(
                    chat_id=channel_id,
                    text=publish_text
                )
                logger.info(f"Опубликовано в канал {channel_id}")
            except Exception as e:
                logger.error(f"Не удалось опубликовать в канал {channel_id}: {e}")
        
        await callback.message.delete()
        await update_stats(user_id, 'approved_count')
        
        try:
            text_approved = await get_setting('text_approved')
            await bot.send_message(
                chat_id=user_id,
                text=text_approved or "✅ Ваше предложение опубликовано!"
            )
        except:
            pass
        
        await callback.answer("✅ Опубликовано!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Ошибка публикации: {e}")
        import traceback
        traceback.print_exc()
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(F.data.startswith("ban_user_"))
async def callback_ban_user(callback: types.CallbackQuery):
    try:
        user_id = int(callback.data.split("_")[2])
        
        await ban_user_db(user_id)
        await callback.message.delete()
        
        try:
            await bot.send_message(
                chat_id=user_id,
                text="🚫 Вы забанены и не можете отправлять предложения."
            )
        except:
            pass
        
        await callback.answer("🚫 Пользователь забанен", show_alert=True)
        
    except Exception as e:
        logger.error(f"Ошибка бана: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(F.data.startswith("show_user_"))
async def callback_show_user(callback: types.CallbackQuery):
    try:
        user_id = int(callback.data.split("_")[2])
        
        user = await get_user(user_id)
        if user:
            stats = f"👤 Информация о пользователе\n\n"
            stats += f"ID: {user_id}\n"
            stats += f"Имя: {user[1] or 'Не указано'}\n"
            stats += f"Предложено: {user[3]}\n"
            stats += f"Одобрено: {user[4]}\n"
            stats += f"Забанен: {'Да' if user[2] else 'Нет'}"
            
            await callback.answer(stats, show_alert=True)
        else:
            await callback.answer("Пользователь не найден", show_alert=True)
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.message(SetupStates.waiting_channel_id)
async def channel_add_process(message: types.Message, state: FSMContext):
    try:
        channel_id = message.text.strip()
        await add_channel_db(channel_id, "Канал")
        await message.answer(f"✅ Канал {channel_id} успешно добавлен!")
        await state.set_state(None)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(SetupStates.waiting_admin_id)
async def admin_add_process(message: types.Message, state: FSMContext):
    try:
        new_admin_id = int(message.text.strip())
        await add_admin_db(new_admin_id)
        await message.answer(f"✅ Пользователь {new_admin_id} добавлен в админы!")
        await state.set_state(None)
    except ValueError:
        await message.answer("❌ Неверный формат. Отправьте числовой ID")
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.message(SetupStates.waiting_broadcast)
async def broadcast_process(message: types.Message, state: FSMContext):
    try:
        users = await get_all_users()
        success = 0
        failed = 0
        
        progress_msg = await message.answer("🔄 Запуск рассылки...")
        
        for i, user in enumerate(users, 1):
            try:
                await bot.send_message(user[0], message.text)
                success += 1
            except Exception as e:
                logger.error(f"Не удалось отправить {user[0]}: {e}")
                failed += 1
            await asyncio.sleep(0.05)
        
        await progress_msg.edit_text(f"✅ Рассылка завершена!\n\nОтправлено: {success}\nОшибок: {failed}")
        await state.set_state(None)
    except Exception as e:
        logger.error(f"Ошибка рассылки: {e}")

@dp.message(SetupStates.waiting_caption)
async def caption_process(message: types.Message, state: FSMContext):
    try:
        if message.text.lower() in ['отключите', 'off', 'выкл']:
            await set_setting('caption', 'Выкл')
            await message.answer("✅ Подпись отключена")
        else:
            await set_setting('caption', message.text)
            await message.answer(f"✅ Подпись установлена:\n{message.text}")
        await state.set_state(None)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.message(SetupStates.waiting_text_start)
async def text_edit_start_process(message: types.Message, state: FSMContext):
    try:
        await set_setting('text_start', message.text)
        await message.answer("✅ Текст обновлён!")
        await state.set_state(None)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.message(SetupStates.waiting_text_approved)
async def text_edit_approved_process(message: types.Message, state: FSMContext):
    try:
        await set_setting('text_approved', message.text)
        await message.answer("✅ Текст обновлён!")
        await state.set_state(None)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.message(SetupStates.waiting_text_rejected)
async def text_edit_rejected_process(message: types.Message, state: FSMContext):
    try:
        await set_setting('text_rejected', message.text)
        await message.answer("✅ Текст обновлён!")
        await state.set_state(None)
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.message(SetupStates.waiting_blacklist_add)
async def blacklist_add_process(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await ban_user_db(user_id)
        await message.answer(f"✅ Пользователь {user_id} добавлен в ЧС")
        await state.set_state(None)
    except ValueError:
        await message.answer("❌ Неверный ID")
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.message(SetupStates.waiting_subscribe_channel)
async def subscribe_add_process(message: types.Message, state: FSMContext):
    try:
        channel_input = message.text.strip()
        try:
            if channel_input.startswith('@') or channel_input.startswith('-'):
                chat = await bot.get_chat(channel_input)
                channel_id = chat.id
                channel_name = chat.title
                channel_username = chat.username
            else:
                await message.answer("❌ Неверный формат. Начните с @ или введите ID канала")
                return
            
            await add_subscribe_channel_db(str(channel_id), channel_name, channel_username)
            await message.answer(f"✅ Канал {channel_name} добавлен в обязательную подписку!")
            await state.set_state(None)
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}. Убедитесь, что бот добавлен в канал.")
    except Exception as e:
        logger.error(f"Ошибка: {e}")

@dp.message()
async def handle_suggestion_start(message: types.Message, state: FSMContext):
    try:
        current_state = await state.get_state()
        if current_state is not None:
            return
        
        if message.text and message.text.startswith('/'):
            return
        
        user = await get_user(message.from_user.id)
        if not user:
            await create_user(message.from_user.id, message.from_user.username)
            user = await get_user(message.from_user.id)
        
        if user and user[2]:
            await message.reply("❌ Вы забанены.")
            return
        
        subscribe_channels = await get_all_subscribe_channels()
        if subscribe_channels:
            is_subscribed = await check_subscription(message.from_user.id)
            if not is_subscribed:
                channels_text = "📢 Для использования бота подпишитесь на каналы:\n\n"
                for ch in subscribe_channels:
                    ch_id, ch_name, ch_username = ch[1], ch[2], ch[3]
                    channel_link = f"@{ch_username}" if ch_username else ch_id
                    channels_text += f"• {ch_name or channel_link}\n"
                
                channels_text += "\nПосле подписки отправьте любое сообщение."
                await message.reply(channels_text)
                return
        
        await state.update_data(suggestion_message=message)
        
        await message.reply(
            "Хотите ли вы отправить новость анонимно?",
            reply_markup=await get_anonymity_keyboard()
        )
        
        await state.set_state(SetupStates.waiting_suggestion)
        
    except Exception as e:
        logger.error(f"Ошибка в handle_suggestion_start: {e}")
        await message.reply("❌ Произошла ошибка")

async def on_startup():
    logger.info("🚀 Бот запускается...")
    await init_db()
    logger.info("✅ Бот готов к работе!")

async def on_shutdown():
    logger.info("🛑 Бот останавливается...")
    await bot.close()

async def main():
    try:
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        logger.info("✅ Запуск polling...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
    finally:
        await bot.close()

if __name__ == "__main__":
    try:
        logger.info("=" * 50)
        logger.info("🚀 ЗАПУСК БОТА")
        logger.info("=" * 50)
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Бот упал с ошибкой: {e}")
        raise