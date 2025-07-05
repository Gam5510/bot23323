import json
import requests
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import datetime
import os
from aiogram.dispatcher import filters
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.callback_data import CallbackData
import functools

# === КОНФИГ ===
CONFIG_FILE = 'config.json'
STORAGE_FILE = 'storage.json'

def load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "admin_ids": [5699915010,702647778],
            "token": "7557819980:AAHRwbvaTCof6UBE47PyGDRbqJi4jgLX6pA"
        }
        save_config(default_config)
        return default_config
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

config = load_config()
TOKEN = config['token']
ADMIN_IDS = config['admin_ids']


def load_storage():
    if not os.path.exists(STORAGE_FILE):
        return {"channels": [], "ad": "", "ad_enabled": True, "post_time": "09:00", "hide_ad": False}
    with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_storage(data):
    with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

storage = load_storage()


def get_currency():
    url = 'https://cbu.uz/uz/arkhiv-kursov-valyut/json/'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        usd = next(x for x in data if x['Ccy'] == 'USD')
        eur = next(x for x in data if x['Ccy'] == 'EUR')
        rub = next(x for x in data if x['Ccy'] == 'RUB')
        return {
            'usd': int(float(usd['Rate']) * 100),
            'eur': int(float(eur['Rate']) * 100),
            'rub': int(float(rub['Rate']) * 1000)
        }
    except Exception as e:
        print('Ошибка парсинга:', e)
        return None

def uzbek_month_name(month_num):
    months = [
        '', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
        'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr'
    ]
    return months[month_num]

# === ФОРМИРОВАНИЕ ПОСТА ===
def make_post():
    now = datetime.datetime.now()
    day = now.day
    month = uzbek_month_name(now.month)
    year = now.year
    today = f"{day} - {month} {year}"
    kurs = get_currency()
    if not kurs:
        return 'Valyuta kurslarini olishda xatolik.'
    post = f"{today}. 💵\n\n"
    post += f"🇺🇸 100 dollar = {kurs['usd']:,} sum 🇺🇿\n"
    post += f"🇪🇺 100 euro = {kurs['eur']:,} sum 🇺🇿\n"
    post += f"🇷🇺 1000 ruble = {kurs['rub']:,} sum 🇺🇿\n\n"
    if storage['channels']:
        username = storage['channels'][0].lstrip('@')
        post += f"@{username}\n"
    if storage.get('ad_enabled', True) and storage.get('ad') and not storage.get('hide_ad', False):
        post += f"Reklama: {storage['ad']}"
    return post

# FSM для ввода рекламы и времени
class AdminStates(StatesGroup):
    waiting_for_ad = State()
    waiting_for_time = State()
    waiting_for_channel = State()
    waiting_for_adv_post = State()
    waiting_for_adv_time = State()
    waiting_for_admin_id = State()

# === TELEGRAM БОТ ===
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
storage_fsm = MemoryStorage()
dp = Dispatcher(bot, storage=storage_fsm)
scheduler = AsyncIOScheduler()

# === ХЕЛПЕР: Только для админа ===
def is_admin(message):
    return message.from_user.id in ADMIN_IDS

# === ГЛАВНОЕ МЕНЮ ===
def get_main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton('📋 Kanal ro\'yxati', callback_data='list_channels'),
        InlineKeyboardButton('💬 Reklama', callback_data='ad_menu'),
        InlineKeyboardButton('🔄 Reklamani yoqish/o\'chirish', callback_data='toggle_ad'),
        InlineKeyboardButton('⏰ Avtomatik joylash vaqti', callback_data='post_time'),
        InlineKeyboardButton('🚀 Hozir yuborish', callback_data='post_now'),
        InlineKeyboardButton('📢 Reklama posti', callback_data='adv_post'),
        InlineKeyboardButton('👥 Administratorlar', callback_data='admins_menu')
    )
    return kb

# === КНОПКИ: Список каналов ===
def get_channels_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    for ch in storage['channels']:
        kb.add(InlineKeyboardButton(ch, callback_data=f'channel_{ch}'))
    kb.add(InlineKeyboardButton('➕ Kanal qo\'shish', callback_data='add_channel'))
    kb.add(InlineKeyboardButton('⬅️ Orqaga', callback_data='main_menu'))
    return kb

@dp.message_handler(commands=['start', 'menu'], state='*')
async def menu_handler(message: types.Message, state: FSMContext):
    if not is_admin(message):
        return
    await state.finish()  # Сбросить любое состояние FSM
    await message.answer('Bosh menyu:', reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data == 'list_channels')
async def cb_list_channels(call: CallbackQuery):
    if not is_admin_from_call(call): return
    if not storage['channels']:
        await call.message.edit_text('Kanal ro\'yxati bo\'sh.', reply_markup=get_main_menu())
        return
    await call.message.edit_text('Kanal ro\'yxati:', reply_markup=get_channels_menu())

@dp.callback_query_handler(lambda c: c.data.startswith('channel_'))
async def cb_channel_info(call: CallbackQuery):
    if not is_admin_from_call(call): return
    ch = call.data.replace('channel_', '')
    text = f'Kanal: {ch}\n\nKanalni o\'chirish?'
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton('❌ O\'chirish', callback_data=f'delch_{ch}'),
        InlineKeyboardButton('⬅️ Orqaga', callback_data='list_channels')
    )
    await call.message.edit_text(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('delch_'))
async def cb_delete_channel(call: CallbackQuery):
    if not is_admin_from_call(call): return
    ch = call.data.replace('delch_', '')
    if ch in storage['channels']:
        storage['channels'].remove(ch)
        save_storage(storage)
        await call.message.edit_text(f'Kanal {ch} o\'chirildi.', reply_markup=get_channels_menu())
    else:
        await call.message.edit_text('Kanal topilmadi.', reply_markup=get_channels_menu())

@dp.callback_query_handler(lambda c: c.data == 'ad_menu')
async def cb_ad_menu(call: CallbackQuery):
    if not is_admin_from_call(call): return
    ad = storage.get('ad', '')
    enabled = storage.get('ad_enabled', True)
    status = "Yoqilgan" if enabled else "O'chirilgan"
    text = f'Hozirgi reklama:\n{ad}\nHolat: {status}'
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton('✏️ O\'zgartirish', callback_data='edit_ad'),
        InlineKeyboardButton('⬅️ Orqaga', callback_data='main_menu')
    )
    await call.message.edit_text(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == 'edit_ad')
async def cb_edit_ad(call: CallbackQuery, state: FSMContext):
    if not is_admin_from_call(call): return
    await call.message.edit_text('Yangi reklama matnini bitta xabar sifatida yuboring:')
    await AdminStates.waiting_for_ad.set()

@dp.message_handler(state=AdminStates.waiting_for_ad)
async def set_new_ad(message: types.Message, state: FSMContext):
    if not is_admin(message): return
    storage['ad'] = message.text
    save_storage(storage)
    await message.answer('Reklama yangilandi!', reply_markup=get_main_menu())
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'toggle_ad')
async def cb_toggle_ad(call: CallbackQuery):
    if not is_admin_from_call(call): return
    storage['ad_enabled'] = not storage.get('ad_enabled', True)
    save_storage(storage)
    status = 'yoqilgan' if storage['ad_enabled'] else 'o\'chirilgan'
    await call.message.edit_text(f'Reklama endi {status}.', reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data == 'post_time')
async def cb_post_time(call: CallbackQuery, state: FSMContext):
    if not is_admin_from_call(call): return
    time = storage.get('post_time', '09:00')
    text = f'Hozirgi avtomatik joylash vaqti: {time}\n\nYangi vaqtni HH:MM formatida yuboring:'
    await call.message.edit_text(text)
    await AdminStates.waiting_for_time.set()

@dp.message_handler(state=AdminStates.waiting_for_time)
async def set_new_time(message: types.Message, state: FSMContext):
    if not is_admin(message): return
    try:
        datetime.datetime.strptime(message.text.strip(), '%H:%M')
        storage['post_time'] = message.text.strip()
        save_storage(storage)
        restart_scheduler()
        await message.answer(f'Avtomatik joylash vaqti yangilandi: {message.text.strip()}', reply_markup=get_main_menu())
        await state.finish()
    except Exception:
        await message.answer('Vaqt formati: HH:MM (masalan, 09:00)')

@dp.callback_query_handler(lambda c: c.data == 'post_now')
async def cb_post_now(call: CallbackQuery):
    if not is_admin_from_call(call): return
    await send_post()
    await call.message.edit_text('Post yuborildi!', reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data == 'main_menu')
async def cb_main_menu(call: CallbackQuery):
    if not is_admin_from_call(call): return
    await call.message.edit_text('Bosh menyu:', reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data == 'add_channel')
async def cb_add_channel(call: CallbackQuery, state: FSMContext):
    if not is_admin_from_call(call): return
    await call.message.edit_text('Kanal username\'ini kiriting (masalan, @mychannel):')
    await AdminStates.waiting_for_channel.set()

@dp.message_handler(state=AdminStates.waiting_for_channel)
async def add_channel_username(message: types.Message, state: FSMContext):
    if not is_admin(message): return
    username = message.text.strip()
    if not username.startswith('@') or len(username) < 5:
        await message.answer('Noto\'g\'ri username. @username formatida kiriting:')
        return
    if username in storage['channels']:
        await message.answer('Kanal allaqachon qo\'shilgan.', reply_markup=get_channels_menu())
        await state.finish()
        return
    storage['channels'].append(username)
    save_storage(storage)
    await message.answer(f'Kanal {username} qo\'shildi!', reply_markup=get_channels_menu())
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'adv_post')
async def cb_adv_post(call: CallbackQuery, state: FSMContext):
    if not is_admin_from_call(call): return
    await call.message.edit_text('Barcha kanallarga yuboriladigan reklama posti matnini kiriting:')
    await AdminStates.waiting_for_adv_post.set()

@dp.message_handler(state=AdminStates.waiting_for_adv_post)
async def adv_post_text(message: types.Message, state: FSMContext):
    if not is_admin(message): return
    await state.update_data(adv_text=message.text.strip())
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton('Hozir yuborish', callback_data='adv_send_now')
    )
    await message.answer('Reklama postini joylash vaqtini HH:MM formatida kiriting (masalan, 15:30):', reply_markup=kb)
    await AdminStates.waiting_for_adv_time.set()

@dp.callback_query_handler(lambda c: c.data == 'adv_send_now', state=AdminStates.waiting_for_adv_time)
async def adv_send_now(call: CallbackQuery, state: FSMContext):
    if not is_admin_from_call(call): return
    data = await state.get_data()
    adv_text = data.get('adv_text', '')
    for ch in storage['channels']:
        try:
            await bot.send_message(ch, adv_text)
        except Exception as e:
            print(f'Reklama yuborishda xatolik {ch}:', e)
    await call.message.edit_text('Reklama posti barcha kanallarga yuborildi!', reply_markup=get_main_menu())
    await state.finish()

async def send_adv_post_async(adv_text):
    for ch in storage['channels']:
        try:
            await bot.send_message(ch, adv_text)
        except Exception as e:
            print(f'Reklama yuborishda xatolik {ch}:', e)

@dp.message_handler(state=AdminStates.waiting_for_adv_time)
async def adv_post_time(message: types.Message, state: FSMContext):
    if not is_admin(message): return
    time_str = message.text.strip()
    try:
        hour, minute = map(int, time_str.split(':'))
        now = datetime.datetime.now()
        post_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if post_time < now:
            post_time += datetime.timedelta(days=1)  # если время уже прошло, на следующий день
    except Exception:
        await message.answer('Vaqt formati: HH:MM (masalan, 15:30)')
        return
    data = await state.get_data()
    adv_text = data.get('adv_text', '')
    # Планируем публикацию через APScheduler (асинхронно)
    loop = asyncio.get_event_loop()
    scheduler.add_job(
        functools.partial(asyncio.run_coroutine_threadsafe, send_adv_post_async(adv_text), loop),
        'date', run_date=post_time
    )
    await message.answer(f'Reklama posti {post_time.strftime("%d.%m.%Y %H:%M")} da barcha kanallarga yuboriladi!', reply_markup=get_main_menu())
    await state.finish()

# === ОТПРАВКА ПОСТА ===
async def send_post():
    post = make_post()
    for ch in storage['channels']:
        try:
            await bot.send_message(ch, post)
        except Exception as e:
            print(f'Yuborishda xatolik {ch}:', e)
    # Сброс hide_ad после поста
    if storage.get('hide_ad', False):
        storage['hide_ad'] = False
        save_storage(storage)

# === РАСПИСАНИЕ ===
def restart_scheduler():
    scheduler.remove_all_jobs()
    time = storage.get('post_time', '09:00')
    hour, minute = map(int, time.split(':'))
    scheduler.add_job(send_post, 'cron', hour=hour, minute=minute, id='post_job')
    if not scheduler.running:
        scheduler.start()

# === УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ ===
def get_admins_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    for admin_id in ADMIN_IDS:
        kb.add(InlineKeyboardButton(f'👤 ID: {admin_id}', callback_data=f'admin_info_{admin_id}'))
    kb.add(InlineKeyboardButton('➕ Administrator qo\'shish', callback_data='add_admin'))
    kb.add(InlineKeyboardButton('⬅️ Orqaga', callback_data='main_menu'))
    return kb

@dp.callback_query_handler(lambda c: c.data == 'admins_menu')
async def cb_admins_menu(call: CallbackQuery):
    if not is_admin_from_call(call): return
    text = f'Hozirgi administratorlar ({len(ADMIN_IDS)}):'
    await call.message.edit_text(text, reply_markup=get_admins_menu())

@dp.callback_query_handler(lambda c: c.data.startswith('admin_info_'))
async def cb_admin_info(call: CallbackQuery):
    if not is_admin_from_call(call): return
    admin_id = int(call.data.replace('admin_info_', ''))
    if admin_id == call.from_user.id:
        text = f'👤 Administrator: {admin_id}\n\nBu siz!'
    else:
        text = f'👤 Administrator: {admin_id}\n\nBu administratorni o\'chirish?'
    
    kb = InlineKeyboardMarkup()
    if admin_id != call.from_user.id:
        kb.add(InlineKeyboardButton('❌ O\'chirish', callback_data=f'del_admin_{admin_id}'))
    kb.add(InlineKeyboardButton('⬅️ Orqaga', callback_data='admins_menu'))
    await call.message.edit_text(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('del_admin_'))
async def cb_delete_admin(call: CallbackQuery):
    global ADMIN_IDS, config
    if not is_admin_from_call(call): return
    admin_id = int(call.data.replace('del_admin_', ''))
    if admin_id == call.from_user.id:
        await call.message.edit_text('O\'zingizni o\'chira olmaysiz!', reply_markup=get_admins_menu())
        return
    
    if admin_id in ADMIN_IDS:
        ADMIN_IDS.remove(admin_id)
        config['admin_ids'] = ADMIN_IDS
        save_config(config)
        await call.message.edit_text(f'Administrator {admin_id} o\'chirildi.', reply_markup=get_admins_menu())
    else:
        await call.message.edit_text('Administrator topilmadi.', reply_markup=get_admins_menu())

@dp.callback_query_handler(lambda c: c.data == 'add_admin')
async def cb_add_admin(call: CallbackQuery, state: FSMContext):
    if not is_admin_from_call(call): return
    await call.message.edit_text('Yangi administratorning Telegram ID\'sini yuboring (faqat raqamlar):')
    await AdminStates.waiting_for_admin_id.set()

@dp.message_handler(state=AdminStates.waiting_for_admin_id)
async def add_admin_id(message: types.Message, state: FSMContext):
    global ADMIN_IDS, config
    if not is_admin(message): return
    try:
        new_admin_id = int(message.text.strip())
        if new_admin_id in ADMIN_IDS:
            await message.answer('Bu administrator allaqachon qo\'shilgan.', reply_markup=get_admins_menu())
            await state.finish()
            return
        
        ADMIN_IDS.append(new_admin_id)
        config['admin_ids'] = ADMIN_IDS
        save_config(config)
        await message.answer(f'Administrator {new_admin_id} qo\'shildi!', reply_markup=get_admins_menu())
        await state.finish()
    except ValueError:
        await message.answer('Noto\'g\'ri ID. Faqat raqamlarni yuboring:')

# === СТАРТ ===
@dp.message_handler()
async def ignore_others(message: types.Message):
    if not is_admin(message):
        return

async def on_startup(dp):
    restart_scheduler()

def is_admin_from_call(call):
    return call.from_user.id in ADMIN_IDS

if __name__ == '__main__':
    print('Бот запущен!')
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
