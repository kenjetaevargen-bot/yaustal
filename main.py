import asyncio
import logging
import os
import random
import re
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()  # можно несколько через запятую
TIMEZONE = os.getenv("TIMEZONE", "Asia/Bishkek").strip()
MORNING_TIME = os.getenv("MORNING_TIME", "05:00").strip()
LUNCH_TIME = os.getenv("LUNCH_TIME", "13:00").strip()
CITY_NAME = os.getenv("CITY_NAME", "Бишкек").strip()
LAT = float(os.getenv("LAT", "42.8746"))
LON = float(os.getenv("LON", "74.5698"))
PORT = int(os.getenv("PORT", "10000"))
DB_PATH = os.getenv("DB_PATH", "data.db")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

if not BOT_TOKEN:
    raise SystemExit("Не задан BOT_TOKEN. Добавь его в .env или в Environment на Render.")

TZ = ZoneInfo(TIMEZONE)
http: aiohttp.ClientSession | None = None
pool = None

# ---------------------------------------------------------------- тексты

MOTIVATIONS = [
    "Маленький шаг сегодня лучше идеального плана завтра. Начни с самого простого 💪",
    "Идеальность не нужна — нужно начать. Остальное придёт по дороге.",
    "Дисциплина — это решение, которое принимаешь утром, пока нет сомнений 🔥",
    "Каждое утро — чистый лист. Напиши на нём то, чем вечером будешь гордиться.",
    "Пока многие спят, ты уже строишь свой день. Это и есть сила 🚀",
    "Усталость пройдёт, а гордость за сделанное останется.",
    "Не сравнивай свой первый шаг с чужим сотым.",
    "Сегодня необязательно быть лучше всех. Достаточно быть лучше, чем вчера.",
    "Мотивация приходит и уходит, а привычка остаётся. Строй привычку 🧱",
    "Бег начинается не на дорожке, а в голове — в тот момент, когда надеваешь кроссовки 👟",
    "Трудный старт — это нормально. Тяжелее всего первые пять минут.",
    "Ты делаешь это не ради медали, а ради себя через год.",
    "Один километр сегодня — уже победа над диваном 🛋",
    "Не останавливайся, когда устаёшь. Остановись, когда закончишь.",
    "Прогресс редко выглядит эффектно. Чаще это тихие повторяющиеся дни.",
    "Любой большой результат когда-то был скучной ежедневной рутиной.",
    "Сомнения — это просто шум. Сделай шаг, и он стихнет.",
    "Ждать, пока почувствуешь готовность, не нужно. Просто начни.",
    "Сильные не те, у кого нет страха, а те, кто идёт вперёд вместе с ним.",
    "Лучшее время для старта было вчера. Второе лучшее — прямо сейчас ⏰",
    "Твоё тело способно на большее, чем подсказывает голова.",
    "Не бросай в тот день, когда труднее всего. Именно он делает тебя сильнее.",
    "Каждый шаг — это голос за ту версию себя, которой хочешь стать.",
    "Маленькие победы складываются в большие истории ✨",
    "Дыши глубже, иди спокойнее, но не останавливайся.",
    "Вдохни этот день полной грудью. Он только начинается 🌅",
    "Если трудно — значит, ты растёшь.",
    "Побеждает не самый быстрый, а тот, кто продолжает идти.",
    "Сделай сегодня то, за что завтрашнее «я» скажет спасибо.",
    "Хороший день не случается сам — его создают с утра.",
    "Не жди вдохновения. Начни, и оно догонит.",
    "Твой единственный соперник — вчерашний день. И ты уже на шаг впереди.",
    "Терпение и регулярность важнее скорости.",
    "Каждая пробежка делает увереннее. Даже самая короткая 🏃",
    "Пусть сегодня план будет простым: встать, начать, не сдаваться.",
    "Ты можешь больше, чем думаешь. Проверь это сегодня.",
    "Настоящий прогресс — это когда продолжаешь, даже если никто не видит.",
    "Не бойся идти медленно. Бойся стоять на месте.",
    "Улыбнись себе в зеркале. Сегодня хороший день для хороших дел 😊",
    "Усилие сегодня — это свобода завтра.",
    "Выбирай то, что приближает к цели, даже если шаг небольшой.",
    "Утро — лучшее время, чтобы поверить в себя ☀️",
    "Не бывает плохой погоды для движения — бывает неподходящая одежда 🌧",
    "Каждый новый день — ещё один шанс сделать лучше.",
    "Верь в процесс. Результаты придут, когда придёт их время.",
    "Когда захочется сдаться, вспомни, зачем всё это началось.",
    "Лёгких путей мало, зато вид с вершины того стоит ⛰",
    "Забота о себе — это не лень, а топливо для всего остального.",
    "Отдых — тоже часть тренировки. Слушай себя 💛",
    "Не гонись за идеальным темпом. Найди свой.",
    "Даже медленный бег быстрее, чем сидение на диване.",
    "Сегодня у тебя есть шанс удивить себя.",
    "Новый день — новые силы. Бери их и иди вперёд 🌿",
    "Сначала привычка тянет назад, потом начинает толкать вперёд.",
    "Что бы ни случилось вчера, сегодня можно начать заново.",
    "Верь, что получится, — и уже наполовину получилось.",
    "Тот, кто идёт, всегда доходит. Главное — идти.",
    "Дорогу осилит идущий. Сегодня твой шаг 👣",
    "Не откладывай радость на потом. Порадуйся прогрессу уже сегодня 🎉",
    "Если получилось сделать мало, это всё равно больше, чем ничего.",
    "Цель — это мечта с датой. Поставь сегодня маленький срок.",
    "Утренняя пробежка — подарок себе, который работает весь день 🎁",
    "Тишина утра — лучшее время, чтобы услышать свои мысли.",
    "Смелость — это сделать шаг, когда страшно.",
    "Радуйся маленьким шагам: из них состоит любой большой путь.",
    "Сила не в том, чтобы никогда не падать, а в том, чтобы вставать.",
    "Улыбка по дороге делает любую дистанцию короче 😄",
    "Позволь себе быть новичком. Все сильные когда-то начинали с нуля.",
    "Сегодняшний труд — это завтрашняя лёгкость.",
    "Заведи один маленький утренний ритуал, и он изменит весь день ☕",
    "Хорошие привычки работают как проценты: чем дольше, тем больше отдача 📈",
    "Скажи себе: «Я справлюсь». Скажи вслух, пока никто не слышит.",
    "Нет неудач — есть опыт. Бери его с собой дальше.",
    "Каждая капля пота — вклад в будущую тебя 💧",
    "Пусть сегодня шаги будут лёгкими, а мысли светлыми 🌤",
    "Верь в себя так же, как верят в тебя те, кто тебя любит ❤️",
    "Самый трудный шаг — выйти за дверь. Дальше проще.",
    "Ты сильнее, чем кажется в самый трудный момент 🔥",
    "Живи в своём ритме. Сегодня он — твой.",
    "Лучшего момента, чем это утро, не будет ☀️",
    "Радость движения — вот что остаётся, когда забываешь про цифры.",
]

VIDEO_IDEAS = [
    "«День из жизни SMM-щика»: утро, задачи, правки от клиента — всё в ритме 30 секунд.",
    "«Что просит клиент vs что получает» — смешной монтаж до/после.",
    "«3 ошибки новичков в сторис» — быстрый список с текстом на экране.",
    "«Как я придумываю 30 идей за 10 минут» — покажи свой метод шаг за шагом.",
    "Возьми один трендовый звук и покажи, как адаптировать его под любую нишу.",
    "«Было/стало»: профиль клиента до и после обновления ленты.",
    "«Закулисье съёмки»: покажи, как делается один ролик за кадром.",
    "«Миф или правда»: 3 мифа о продвижении в Instagram.",
    "«Одна фишка Reels за 15 секунд»: переход, субтитры или быстрый монтаж.",
    "«Как выбрать хештеги» за 20 секунд — с живым примером.",
    "Разбор чужого удачного ролика: почему он зашёл — хук, ритм, финал.",
    "«5 приложений для монтажа с телефона» — коротко, что умеет каждое.",
    "«Контент-план на неделю за 5 минут» — покажи свой шаблон.",
    "Ответ на вопрос из комментариев: сними видео-ответ с цитатой вопроса.",
    "«Как писать цепляющие первые 3 секунды» — 3 примера хуков.",
    "Мини-урок: как снять ролик на телефон при плохом свете.",
    "«Сколько стоит ролик» — честный разговор о цене работы.",
    "Челлендж «30 дней — 30 роликов»: объяви старт и план.",
    "«Моё рабочее место»: обзор стола и инструментов SMM-щика.",
    "Скетч «Как сказать клиенту нет» — с юмором и по-человечески.",
    "Сравни ролик с хорошим и плохим звуком — пусть зрители услышат разницу.",
    "«Топ-3 ошибки в описании профиля» — с примерами до и после.",
    "«Где брать вдохновение, когда идей нет» — 4 источника.",
    "Мини-история клиента: какая была проблема и что сделали (с разрешения).",
    "«Охват и вовлечённость простыми словами» — на пальцах за 30 секунд.",
    "Отреагируй на популярный тренд с профессиональным взглядом SMM.",
    "«Шаблон текста для продающих сторис» — покажи готовый пример.",
    "«Как красиво оформить закреплённые посты» — 3 идеи.",
    "«Утро SMM-щика, который работает из дома»: распорядок дня.",
    "«Как я получил первого клиента» — личная история с выводами.",
    "«Что делаю, если ролик не набирает просмотры» — чек-лист из 4 пунктов.",
    "Сравни 3 шрифта для субтитров: какой читается лучше всего.",
    "«Как собрать референсы за 10 минут» — покажи свою подборку.",
    "Инструкция: как сделать обложку для Reels в Canva.",
    "«5 фраз, которые убивают вовлечённость» в подписях к постам.",
    "«Как работает опрос в сторис и зачем он нужен».",
    "Блиц: ответь на 5 частых вопросов новичков за одну минуту.",
    "«Один ролик тремя способами»: покажи, как снять одну идею в разных стилях.",
    "Бесплатные источники музыки и звуков для роликов — подборка.",
    "«3 цифры, которые смотрю в статистике каждую неделю».",
    "«Реклама vs органика» — что выбрать новичку и почему.",
    "Скетч «Клиент пишет в пятницу вечером» — всем знакомая боль.",
    "«Как не выгореть в соцсетях» — 3 простые привычки.",
    "Ответь на вопрос «Где учиться SMM?» — список проверенных ресурсов.",
    "Покажи один простой монтажный переход за 15 секунд.",
    "«Как придумать название для рубрики» — 3 приёма.",
    "«Один пост — четыре формата»: из поста сделай Reels, сторис и карусель.",
    "«Что такое хук и как его проверить на друге».",
    "«TikTok и Reels: в чём разница» — для начинающих.",
    "«Тихие ролики»: контент без озвучки, только текст на экране.",
    "«Как я готовлюсь к съёмке» — чек-лист из 5 пунктов.",
    "«3 ошибки в видео, которые видно сразу».",
    "«Угадай ошибку»: покажи пост с промахом, пусть угадают в комментариях.",
    "«Мой любимый приём в сторис» — покажи один и объясни, почему он работает.",
    "«Как ответить на негативный комментарий» — пример диалога.",
    "«Подборка трендов недели»: 3 тренда и как их использовать.",
    "«Контент для скучной ниши: как сделать интересно» — 3 идеи.",
    "«Что снять, если нет идей» — 7 универсальных тем на любой день.",
    "«Личный бренд SMM-щика: с чего начать» — 3 шага.",
    "«Итоги недели»: покажи цифры и выводы, сделай рубрику постоянной.",
]

# Один раз перемешиваем с фиксированным зерном: порядок стабильный после перезапусков.
random.Random(2026).shuffle(MOTIVATIONS)
random.Random(7).shuffle(VIDEO_IDEAS)


def pick_for_day(items: list[str], day) -> str:
    return items[day.toordinal() % len(items)]


# ---------------------------------------------------------------- база данных
# DATABASE_URL (Neon) -> Postgres, данные не пропадают.
# Без него -> SQLite-файл (на бесплатном Render он стирается при перезапуске).

SCHEMA = [
    "CREATE TABLE IF NOT EXISTS users (chat_id BIGINT PRIMARY KEY)",
    "CREATE TABLE IF NOT EXISTS runs (chat_id BIGINT, day TEXT, km DOUBLE PRECISION, "
    "minutes DOUBLE PRECISION, feeling TEXT)",
    "CREATE TABLE IF NOT EXISTS sent (kind TEXT, day TEXT, PRIMARY KEY (kind, day))",
]


def _pg(q: str) -> str:
    i = 0
    out = []
    for ch in q:
        if ch == "?":
            i += 1
            out.append(f"${i}")
        else:
            out.append(ch)
    return "".join(out)


def _sqlite(q: str, args=(), fetch: bool = False):
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(q, args)
        rows = cur.fetchall() if fetch else None
        rc = cur.rowcount
        conn.commit()
        return rows, rc
    finally:
        conn.close()


async def execute(q: str, *args) -> int:
    if pool:
        status = await pool.execute(_pg(q), *args)
        try:
            return int(status.split()[-1])
        except (ValueError, IndexError):
            return 0
    return _sqlite(q, args)[1]


async def fetch(q: str, *args) -> list[tuple]:
    if pool:
        rows = await pool.fetch(_pg(q), *args)
        return [tuple(r) for r in rows]
    return _sqlite(q, args, fetch=True)[0]


async def init_db():
    global pool
    if DATABASE_URL:
        import asyncpg

        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=3,
            statement_cache_size=0,
            max_inactive_connection_lifetime=60,
        )
        log.info("База данных: Postgres")
    else:
        log.warning("DATABASE_URL не задан — используется временный SQLite")
    for q in SCHEMA:
        await execute(q)


async def add_user(chat_id: int):
    await execute("INSERT INTO users (chat_id) VALUES (?) ON CONFLICT DO NOTHING", chat_id)


async def remove_user(chat_id: int):
    await execute("DELETE FROM users WHERE chat_id = ?", chat_id)


async def all_recipients() -> set[int]:
    result = {r[0] for r in await fetch("SELECT chat_id FROM users")}
    for part in OWNER_CHAT_ID.replace(" ", "").split(","):
        if part.lstrip("-").isdigit():
            result.add(int(part))
    return result


async def claim(kind: str, day: str) -> bool:
    """True, если рассылка этого вида за этот день ещё не отправлялась (защита от дублей)."""
    n = await execute("INSERT INTO sent (kind, day) VALUES (?, ?) ON CONFLICT DO NOTHING", kind, day)
    return n == 1


async def save_run(chat_id: int, day: str, km: float, minutes: float, feeling: str):
    await execute(
        "INSERT INTO runs (chat_id, day, km, minutes, feeling) VALUES (?, ?, ?, ?, ?)",
        chat_id, day, km, minutes, feeling,
    )


# ---------------------------------------------------------------- погода

WMO = {
    0: "ясно ☀️", 1: "в основном ясно 🌤", 2: "переменная облачность ⛅", 3: "пасмурно ☁️",
    45: "туман 🌫", 48: "изморозь 🌫", 51: "лёгкая морось 🌦", 53: "морось 🌦", 55: "сильная морось 🌧",
    56: "ледяная морось 🌧", 57: "сильная ледяная морось 🌧",
    61: "небольшой дождь 🌦", 63: "дождь 🌧", 65: "сильный дождь 🌧", 66: "ледяной дождь 🌧",
    67: "сильный ледяной дождь 🌧", 71: "небольшой снег 🌨", 73: "снег 🌨", 75: "сильный снег ❄️",
    77: "снежные зёрна 🌨", 80: "ливни 🌦", 81: "сильные ливни 🌧", 82: "очень сильные ливни ⛈",
    85: "снегопад 🌨", 86: "сильный снегопад ❄️", 95: "гроза ⛈", 96: "гроза с градом ⛈",
    99: "сильная гроза с градом ⛈",
}


def deg(x) -> str:
    v = round(x)
    return f"{v}°" if v != 0 else "0°"


async def get_weather() -> str:
    params = {
        "latitude": LAT,
        "longitude": LON,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
        "hourly": "temperature_2m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
        "timezone": TIMEZONE,
        "forecast_days": 1,
    }
    for attempt in range(2):
        try:
            async with http.get(
                "https://api.open-meteo.com/v1/forecast",
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                r.raise_for_status()
                w = await r.json()
            cur, day, hourly = w["current"], w["daily"], w["hourly"]["temperature_2m"]
            lines = [
                f"🌍 {CITY_NAME}, сегодня",
                f"Сейчас: {deg(cur['temperature_2m'])}C (ощущается как {deg(cur['apparent_temperature'])}C), "
                f"{WMO.get(cur['weather_code'], '')}",
                f"Утро {deg(hourly[8])} · День {deg(hourly[14])} · Вечер {deg(hourly[20])}",
                f"Днём от {deg(day['temperature_2m_min'][0])} до {deg(day['temperature_2m_max'][0])}C",
            ]
            rain = day["precipitation_probability_max"][0]
            if rain is not None:
                lines.append(f"Вероятность осадков: до {rain}%")
            lines.append(f"Ветер: {round(cur['wind_speed_10m'])} км/ч · Влажность: {cur['relative_humidity_2m']}%")
            lines.append(f"🌅 Восход {day['sunrise'][0][11:16]} · 🌇 Закат {day['sunset'][0][11:16]}")
            return "\n".join(lines)
        except Exception as e:
            log.warning("Weather error (попытка %s): %s", attempt + 1, e)
            await asyncio.sleep(2)
    return f"🌍 {CITY_NAME}: не удалось получить погоду, попробуй чуть позже."


# ---------------------------------------------------------------- рассылка


async def morning_text(day) -> str:
    return f"☀️ Доброе утро!\n\n{await get_weather()}\n\n💬 {pick_for_day(MOTIVATIONS, day)}"


def lunch_text(day) -> str:
    return (
        "🎬 Идея для видео на сегодня:\n\n"
        f"{pick_for_day(VIDEO_IDEAS, day)}\n\n"
        "Совет: хук — в первые 3 секунды, весь ролик — до 30 секунд 😉"
    )


async def broadcast(text: str):
    for chat_id in await all_recipients():
        try:
            await bot.send_message(chat_id, text)
        except TelegramForbiddenError:
            await remove_user(chat_id)  # человек заблокировал бота
        except Exception as e:
            log.warning("Не отправлено %s: %s", chat_id, e)
        await asyncio.sleep(0.05)


async def job_morning():
    day = datetime.now(TZ).date()
    if not await claim("morning", day.isoformat()):
        log.info("Утренняя рассылка за %s уже была", day)
        return
    await broadcast(await morning_text(day))


async def job_lunch():
    day = datetime.now(TZ).date()
    if not await claim("lunch", day.isoformat()):
        log.info("Обеденная рассылка за %s уже была", day)
        return
    await broadcast(lunch_text(day))


# ---------------------------------------------------------------- бот

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

BTN_WEATHER = "🌤 Погода"
BTN_RUN = "🏃 Записать пробежку"
BTN_LINKS = "🔗 Полезные ссылки"
BTN_ABOUT = "ℹ️ О сервисе"

FEELINGS = {"great": "😄 Отлично", "ok": "🙂 Нормально", "hard": "😓 Тяжело"}


def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_WEATHER), KeyboardButton(text=BTN_RUN)],
            [KeyboardButton(text=BTN_LINKS), KeyboardButton(text=BTN_ABOUT)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выбери кнопку 👇",
    )


def links_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏃 Strava", url="https://www.strava.com")],
            [InlineKeyboardButton(text="▶️ YouTube", url="https://www.youtube.com")],
            [InlineKeyboardButton(text="✨ Gemini", url="https://gemini.google.com")],
        ]
    )


def feelings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=f"feel:{k}") for k, t in FEELINGS.items()]]
    )


class RunForm(StatesGroup):
    km = State()
    minutes = State()
    feeling = State()


def num(text: str) -> float | None:
    m = re.search(r"\d+(?:[.,]\d+)?", text or "")
    return float(m.group(0).replace(",", ".")) if m else None


def fmt(x: float) -> str:
    return f"{x:g}"


def fmt_pace(total_min: float, total_km: float) -> str:
    if total_km <= 0:
        return "—"
    p = total_min / total_km
    m = int(p)
    s = round((p - m) * 60)
    if s == 60:
        m, s = m + 1, 0
    return f"{m}:{s:02d} мин/км"


async def week_summary(chat_id: int) -> str:
    today = datetime.now(TZ).date()
    monday = today - timedelta(days=today.weekday())
    rows = await fetch("SELECT km, minutes FROM runs WHERE chat_id = ? AND day >= ?", chat_id, monday.isoformat())
    count = len(rows)
    total_km = sum(r[0] for r in rows)
    total_min = sum(r[1] for r in rows)
    return (
        "📊 Твоя неделя:\n"
        f"• Пробежек: {count}\n"
        f"• Всего: {fmt(round(total_km, 2))} км\n"
        f"• Всего времени: {fmt(round(total_min))} мин\n"
        f"• В среднем: {fmt(round(total_min / count))} мин за пробежку\n"
        f"• Средний темп: {fmt_pace(total_min, total_km)}"
    )


# ---- команды


@dp.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    await add_user(m.chat.id)
    await m.answer(
        f"Привет, {m.from_user.first_name}! 👋\n\n"
        "Этот бот создан специально для тебя 💛\n\n"
        f"🌅 Каждое утро в {MORNING_TIME} — погода в {CITY_NAME} и мотивация на день\n"
        f"🎬 В {LUNCH_TIME} — идея для видео\n"
        "🏃 А ещё здесь можно записывать пробежки и смотреть итоги недели\n\n"
        "Кнопки внизу — всегда под рукой 👇",
        reply_markup=main_kb(),
    )


@dp.message(Command("id"))
async def cmd_id(m: Message):
    await m.answer(f"Твой chat ID: {m.chat.id}")


@dp.message(Command("stop"))
async def cmd_stop(m: Message):
    await remove_user(m.chat.id)
    await m.answer("Отписал от рассылки. Вернуться — /start 🙌")


@dp.message(Command("cancel"))
async def cmd_cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Окей, отменили 👌", reply_markup=main_kb())


# Тестовые команды: сразу показывают сегодняшнее сообщение (рассылку не расходуют)
@dp.message(Command("morning"))
async def cmd_morning(m: Message):
    await m.answer(await morning_text(datetime.now(TZ).date()))


@dp.message(Command("lunch"))
async def cmd_lunch(m: Message):
    await m.answer(lunch_text(datetime.now(TZ).date()))


# ---- кнопки меню (сбрасывают незавершённую запись пробежки)


@dp.message(F.text == BTN_WEATHER)
async def btn_weather(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(await get_weather(), reply_markup=main_kb())


@dp.message(F.text == BTN_LINKS)
async def btn_links(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Полезные ссылки 👇", reply_markup=links_kb())


@dp.message(F.text == BTN_ABOUT)
async def btn_about(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(
        "ℹ️ О сервисе\n\n"
        "Этот бот был специально сделан для вас 💛\n\n"
        f"🌅 {MORNING_TIME} — погода в {CITY_NAME} и одна мотивация\n"
        f"🎬 {LUNCH_TIME} — одна идея для видео\n"
        "🏃 Дневник пробежек: километры, минуты, самочувствие и итоги недели\n"
        "🔗 Быстрые ссылки: Strava, YouTube, Gemini",
        reply_markup=main_kb(),
    )


@dp.message(F.text == BTN_RUN)
async def btn_run(m: Message, state: FSMContext):
    await state.set_state(RunForm.km)
    await m.answer("Сколько километров ты сегодня пробежала? 🏃\nНапиши число, например 5 или 3.5\n\nОтмена: /cancel")


# ---- запись пробежки


@dp.message(RunForm.km, F.text)
async def run_km(m: Message, state: FSMContext):
    km = num(m.text)
    if km is None or not (0.1 <= km <= 200):
        await m.answer("Напиши число километров, например 5 или 3.5 🙂")
        return
    await state.update_data(km=km)
    await state.set_state(RunForm.minutes)
    await m.answer("Сколько минут ты бегала? ⏱\nНапиши число, например 32")


@dp.message(RunForm.minutes, F.text)
async def run_minutes(m: Message, state: FSMContext):
    minutes = num(m.text)
    if minutes is None or not (1 <= minutes <= 1000):
        await m.answer("Напиши число минут, например 32 🙂")
        return
    await state.update_data(minutes=minutes)
    await state.set_state(RunForm.feeling)
    await m.answer("Как самочувствие? 💭", reply_markup=feelings_kb())


@dp.message(RunForm.feeling, F.text)
async def run_feeling_text(m: Message):
    await m.answer("Выбери самочувствие кнопкой выше 👆", reply_markup=feelings_kb())


@dp.callback_query(RunForm.feeling, F.data.startswith("feel:"))
async def run_feeling(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":", 1)[1]
    feeling = FEELINGS.get(key, "🙂 Нормально")
    data = await state.get_data()
    km, minutes = data["km"], data["minutes"]
    chat_id = cb.message.chat.id
    today = datetime.now(TZ).date().isoformat()
    await save_run(chat_id, today, km, minutes, feeling)
    await state.clear()
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(
        f"✅ Записано!\nСегодня: {fmt(km)} км за {fmt(minutes)} мин\nСамочувствие: {feeling}\n\n"
        f"{await week_summary(chat_id)}\n\nМолодец! 💪",
        reply_markup=main_kb(),
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("feel:"))
async def run_feeling_expired(cb: CallbackQuery):
    await cb.answer("Эта запись устарела. Нажми «Записать пробежку» и начни заново 🙂", show_alert=True)


@dp.message(F.text)
async def fallback(m: Message):
    await m.answer("Пользуйся кнопками внизу 👇", reply_markup=main_kb())


# ---------------------------------------------------------------- веб-сервер для Render / мониторинга


async def start_web():
    async def ok(_):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", ok)
    app.router.add_get("/health", ok)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info("Веб-сервер запущен на порту %s", PORT)


def parse_time(value: str) -> tuple[int, int]:
    h, m = value.split(":")
    return int(h), int(m)


async def main():
    global http
    http = aiohttp.ClientSession()
    await init_db()
    await start_web()

    scheduler = AsyncIOScheduler(timezone=TZ)
    mh, mm = parse_time(MORNING_TIME)
    lh, lm = parse_time(LUNCH_TIME)
    scheduler.add_job(job_morning, CronTrigger(hour=mh, minute=mm, timezone=TZ),
                      misfire_grace_time=600, coalesce=True, id="morning")
    scheduler.add_job(job_lunch, CronTrigger(hour=lh, minute=lm, timezone=TZ),
                      misfire_grace_time=600, coalesce=True, id="lunch")
    scheduler.start()
    log.info("Расписание: утро %s, обед %s (%s)", MORNING_TIME, LUNCH_TIME, TIMEZONE)

    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await http.close()


if __name__ == "__main__":
    asyncio.run(main())
