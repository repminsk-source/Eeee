import asyncio
import json
import os
import re
import aiohttp
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ChatMemberUpdated, ChatMemberAdministrator, ChatMemberOwner
)
from aiogram.filters import Command, CommandStart
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ═══════════════════════════════════════════════════════════════
#  AURUM FC BOT v3.0
# ═══════════════════════════════════════════════════════════════

TOKEN = "8723334205:AAGEsLo5zzAlUpjnafgL-Bo2WZ7DTvcCP9w"
ADMIN_IDS = []
OWNER_ID = None

PLAYERS_FILE = "players.json"
WARNS_FILE = "warns.json"
MUTES_FILE = "mutes.json"
BANS_FILE = "bans.json"
NOTES_FILE = "notes.json"
SCHEDULE_FILE = "schedule.json"
ADMINS_FILE = "admins.json"
POLLS_FILE = "polls.json"

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

POSITIONS = {
    "gk": "🧤 Вратарь", "cb": "🛡️ Центральный защитник",
    "lb": "⬅️ Левый защитник", "rb": "➡️ Правый защитник",
    "cdm": "🎯 Опорный полузащитник", "cm": "⚙️ Центральный полузащитник",
    "cam": "🎨 Атакующий полузащитник", "lm": "⬅️ Левый полузащитник",
    "rm": "➡️ Правый полузащитник", "lw": "⬅️ Левый вингер",
    "rw": "➡️ Правый вингер", "st": "⚽ Нападающий", "cf": "🎯 Форвард",
}

EVENT_TYPES = {
    "match": {"emoji": "⚽", "name": "Матч", "keywords": ["матч", "игра", "встреча", "тур", "против", "vs", "versus"]},
    "training": {"emoji": "🏃", "name": "Тренировка", "keywords": ["тренировка", "треня", "практика", "занятие", "тренинг"]},
    "league": {"emoji": "🏆", "name": "Лига/Турнир", "keywords": ["лига", "турнир", "чемпионат", "кубок", "соревнование"]},
    "meeting": {"emoji": "📋", "name": "Собрание", "keywords": ["собрание", "совещание", "митинг"]},
    "friendly": {"emoji": "🤝", "name": "Товарищеский матч", "keywords": ["товарищеский", "спарринг", "контрольный"]},
}

def load_data(filename, default=None):
    if default is None:
        default = {}
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class AdminSystem:
    def __init__(self):
        self.manual = load_data(ADMINS_FILE, [])
        self.auto = {}
    def is_admin(self, user_id, chat_id=None):
        if user_id in self.manual: return True
        if chat_id and chat_id in self.auto and user_id in self.auto[chat_id]: return True
        if OWNER_ID and user_id == OWNER_ID: return True
        return False
    def add_manual(self, user_id):
        if user_id not in self.manual:
            self.manual.append(user_id)
            save_data(ADMINS_FILE, self.manual)
    def remove_manual(self, user_id):
        if user_id in self.manual:
            self.manual.remove(user_id)
            save_data(ADMINS_FILE, self.manual)
    def update_auto(self, chat_id, admin_ids):
        self.auto[chat_id] = set(admin_ids)
    def get_all(self, chat_id=None):
        result = set(self.manual)
        if OWNER_ID: result.add(OWNER_ID)
        if chat_id and chat_id in self.auto: result.update(self.auto[chat_id])
        return result

admins_sys = AdminSystem()

class PlayerStats:
    def __init__(self):
        self.data = load_data(PLAYERS_FILE, {})
    def get(self, user_id):
        return self.data.get(str(user_id), {})
    def set_position(self, user_id, position):
        uid = str(user_id)
        if uid not in self.data:
            self.data[uid] = {
                "goals": 0, "assists": 0, "matches": 0,
                "wins": 0, "draws": 0, "losses": 0,
                "yellow_cards": 0, "red_cards": 0,
                "position": None, "registered": datetime.now().isoformat()
            }
        self.data[uid]["position"] = position
        save_data(PLAYERS_FILE, self.data)
    def add_stat(self, user_id, stat, value=1):
        uid = str(user_id)
        if uid in self.data and stat in self.data[uid]:
            self.data[uid][stat] += value
            save_data(PLAYERS_FILE, self.data)
    def set_stat(self, user_id, stat, value):
        uid = str(user_id)
        if uid in self.data:
            self.data[uid][stat] = value
            save_data(PLAYERS_FILE, self.data)
    def get_all(self):
        return self.data

players = PlayerStats()

class WarnSystem:
    def __init__(self):
        self.data = load_data(WARNS_FILE, {})
    def get(self, user_id, chat_id):
        return self.data.get(f"{chat_id}:{user_id}", {"count": 0, "history": []})
    def add(self, user_id, chat_id, reason, by_admin):
        key = f"{chat_id}:{user_id}"
        if key not in self.data:
            self.data[key] = {"count": 0, "history": []}
        self.data[key]["count"] += 1
        self.data[key]["history"].append({"reason": reason, "by": by_admin, "date": datetime.now().isoformat()})
        save_data(WARNS_FILE, self.data)
        return self.data[key]["count"]
    def remove(self, user_id, chat_id):
        key = f"{chat_id}:{user_id}"
        if key in self.data and self.data[key]["count"] > 0:
            self.data[key]["count"] -= 1
            if self.data[key]["history"]:
                self.data[key]["history"].pop()
            save_data(WARNS_FILE, self.data)
            return self.data[key]["count"]
        return 0
    def reset(self, user_id, chat_id):
        key = f"{chat_id}:{user_id}"
        if key in self.data:
            del self.data[key]
            save_data(WARNS_FILE, self.data)

warns = WarnSystem()

class MuteSystem:
    def __init__(self):
        self.data = load_data(MUTES_FILE, {})
    def add(self, user_id, chat_id, duration_minutes, reason, by_admin):
        until = (datetime.now() + timedelta(minutes=duration_minutes)).isoformat()
        key = f"{chat_id}:{user_id}"
        self.data[key] = {"until": until, "reason": reason, "by": by_admin, "date": datetime.now().isoformat()}
        save_data(MUTES_FILE, self.data)
        return until
    def is_muted(self, user_id, chat_id):
        key = f"{chat_id}:{user_id}"
        if key not in self.data: return False
        until = datetime.fromisoformat(self.data[key]["until"])
        if datetime.now() > until:
            del self.data[key]
            save_data(MUTES_FILE, self.data)
            return False
        return True
    def get_info(self, user_id, chat_id):
        key = f"{chat_id}:{user_id}"
        if key in self.data:
            info = self.data[key].copy()
            info["until_dt"] = datetime.fromisoformat(info["until"])
            return info
        return None
    def unmute(self, user_id, chat_id):
        key = f"{chat_id}:{user_id}"
        if key in self.data:
            del self.data[key]
            save_data(MUTES_FILE, self.data)

mutes = MuteSystem()

class BanSystem:
    def __init__(self):
        self.data = load_data(BANS_FILE, {})
    def add(self, user_id, chat_id, duration_minutes, reason, by_admin):
        until = (datetime.now() + timedelta(minutes=duration_minutes)).isoformat() if duration_minutes else None
        key = f"{chat_id}:{user_id}"
        self.data[key] = {"until": until, "reason": reason, "by": by_admin, "date": datetime.now().isoformat(), "permanent": duration_minutes is None}
        save_data(BANS_FILE, self.data)
        return until
    def is_banned(self, user_id, chat_id):
        key = f"{chat_id}:{user_id}"
        if key not in self.data: return False
        if self.data[key].get("permanent"): return True
        until = datetime.fromisoformat(self.data[key]["until"])
        if datetime.now() > until:
            del self.data[key]
            save_data(BANS_FILE, self.data)
            return False
        return True
    def unban(self, user_id, chat_id):
        key = f"{chat_id}:{user_id}"
        if key in self.data:
            del self.data[key]
            save_data(BANS_FILE, self.data)

bans = BanSystem()

class CoachNotes:
    def __init__(self):
        self.data = load_data(NOTES_FILE, {"general": [], "players": {}})
    def add_general(self, text, author_id, author_name):
        self.data["general"].append({"text": text, "author_id": author_id, "author_name": author_name, "date": datetime.now().isoformat(), "id": len(self.data["general"]) + 1})
        save_data(NOTES_FILE, self.data)
        return len(self.data["general"])
    def add_player_note(self, user_id, text, author_id, author_name):
        uid = str(user_id)
        if uid not in self.data["players"]: self.data["players"][uid] = []
        self.data["players"][uid].append({"text": text, "author_id": author_id, "author_name": author_name, "date": datetime.now().isoformat(), "id": len(self.data["players"][uid]) + 1})
        save_data(NOTES_FILE, self.data)
        return len(self.data["players"][uid])
    def get_general(self):
        return self.data.get("general", [])
    def get_player_notes(self, user_id):
        return self.data.get("players", {}).get(str(user_id), [])
    def delete_note(self, note_id, user_id=None):
        if user_id:
            uid = str(user_id)
            if uid in self.data.get("players", {}):
                self.data["players"][uid] = [n for n in self.data["players"][uid] if n.get("id") != note_id]
        else:
            self.data["general"] = [n for n in self.data.get("general", []) if n.get("id") != note_id]
        save_data(NOTES_FILE, self.data)

coach_notes = CoachNotes()

class ScheduleSystem:
    def __init__(self):
        self.data = load_data(SCHEDULE_FILE, {"events": []})
    def add_event(self, chat_id, title, event_datetime, event_type, description="", created_by=None):
        event_id = len(self.data["events"]) + 1
        event = {"id": event_id, "chat_id": chat_id, "title": title, "datetime": event_datetime.isoformat(), "type": event_type, "description": description, "created_by": created_by, "created_at": datetime.now().isoformat(), "reminded_24h": False, "reminded_1h": False}
        self.data["events"].append(event)
        save_data(SCHEDULE_FILE, self.data)
        return event_id
    def get_upcoming(self, chat_id=None, hours=48):
        now = datetime.now()
        upcoming = []
        for e in self.data.get("events", []):
            if e.get("reminded_1h") and e.get("reminded_24h"): continue
            event_time = datetime.fromisoformat(e["datetime"])
            if chat_id and e.get("chat_id") != chat_id: continue
            if now <= event_time <= now + timedelta(hours=hours): upcoming.append(e)
        return upcoming
    def get_all(self, chat_id=None):
        events = self.data.get("events", [])
        if chat_id:
            events = [e for e in events if e.get("chat_id") == chat_id]
        return sorted(events, key=lambda x: x["datetime"])
    def mark_reminded(self, event_id, which="1h"):
        for e in self.data["events"]:
            if e["id"] == event_id:
                e[f"reminded_{which}"] = True
                break
        save_data(SCHEDULE_FILE, self.data)
    def delete_event(self, event_id):
        self.data["events"] = [e for e in self.data["events"] if e["id"] != event_id]
        save_data(SCHEDULE_FILE, self.data)

schedule = ScheduleSystem()

class PollSystem:
    def __init__(self):
        self.data = load_data(POLLS_FILE, {"polls": []})
    def create(self, chat_id, question, options, created_by, max_votes=1):
        poll_id = len(self.data["polls"]) + 1
        poll = {"id": poll_id, "chat_id": chat_id, "question": question, "options": {opt: {"votes": 0, "voters": []} for opt in options}, "created_by": created_by, "created_at": datetime.now().isoformat(), "max_votes": max_votes, "closed": False}
        self.data["polls"].append(poll)
        save_data(POLLS_FILE, self.data)
        return poll_id
    def get(self, poll_id):
        for p in self.data["polls"]:
            if p["id"] == poll_id: return p
        return None
    def vote(self, poll_id, option, user_id):
        poll = self.get(poll_id)
        if not poll or poll["closed"]: return False, "Опрос закрыт"
        if option not in poll["options"]: return False, "Нет такого варианта"
        total_votes = sum(1 for opt in poll["options"].values() if user_id in opt["voters"])
        if total_votes >= poll["max_votes"]: return False, "Ты уже проголосовал"
        if user_id in poll["options"][option]["voters"]: return False, "Ты уже выбрал этот вариант"
        poll["options"][option]["votes"] += 1
        poll["options"][option]["voters"].append(user_id)
        save_data(POLLS_FILE, self.data)
        return True, "OK"
    def close(self, poll_id):
        poll = self.get(poll_id)
        if poll: poll["closed"] = True; save_data(POLLS_FILE, self.data)
    def delete(self, poll_id):
        self.data["polls"] = [p for p in self.data["polls"] if p["id"] != poll_id]
        save_data(POLLS_FILE, self.data)

polls = PollSystem()

def detect_event_type(text):
    text_lower = text.lower()
    scores = {}
    for etype, info in EVENT_TYPES.items():
        score = 0
        for keyword in info["keywords"]:
            if keyword in text_lower: score += 1
        scores[etype] = score
    best = max(scores, key=scores.get)
    if scores[best] == 0: return "training"
    return best

def parse_datetime(text):
    text_lower = text.lower()
    now = datetime.now()
    if "сегодня" in text_lower:
        m = re.search(r"(\d{1,2}):(\d{2})", text)
        if m:
            h, mi = int(m.group(1)), int(m.group(2))
            return now.replace(hour=h, minute=mi, second=0, microsecond=0)
    if "завтра" in text_lower:
        m = re.search(r"(\d{1,2}):(\d{2})", text)
        if m:
            h, mi = int(m.group(1)), int(m.group(2))
            tomorrow = now + timedelta(days=1)
            return tomorrow.replace(hour=h, minute=mi, second=0, microsecond=0)
    if "послезавтра" in text_lower:
        m = re.search(r"(\d{1,2}):(\d{2})", text)
        if m:
            h, mi = int(m.group(1)), int(m.group(2))
            day_after = now + timedelta(days=2)
            return day_after.replace(hour=h, minute=mi, second=0, microsecond=0)
    m = re.search(r"(\d{1,2})[./](\d{1,2})\s+(\d{1,2}):(\d{2})", text)
    if m:
        d, mon, h, mi = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        year = now.year
        if mon < now.month or (mon == now.month and d < now.day): year += 1
        return datetime(year, mon, d, h, mi, 0)
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})\s+(\d{1,2}):(\d{2})", text)
    if m:
        d, mon, y, h, mi = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        return datetime(y, mon, d, h, mi, 0)
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        dt = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        if dt < now: dt += timedelta(days=1)
        return dt
    return None

def is_admin(user_id, chat_id=None):
    return admins_sys.is_admin(user_id, chat_id)

def get_mention(user):
    if user.username: return f"@{user.username}"
    return f"[{user.first_name}](tg://user?id={user.id})"

def format_duration(minutes):
    if minutes < 60: return f"{minutes} мин"
    elif minutes < 1440: return f"{minutes // 60} ч {minutes % 60} мин"
    else: return f"{minutes // 1440} д {(minutes % 1440) // 60} ч"

def format_datetime(dt):
    if isinstance(dt, str): dt = datetime.fromisoformat(dt)
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    wd = weekdays[dt.weekday()]
    return f"{wd}, {dt.day:02d}.{dt.month:02d} в {dt.hour:02d}:{dt.minute:02d}"

def build_poll_kb(poll_id, options, closed=False):
    kb = []
    for opt in options:
        if closed:
            kb.append([InlineKeyboardButton(text=f"{opt} (закрыто)", callback_data="noop")])
        else:
            kb.append([InlineKeyboardButton(text=f"☐ {opt}", callback_data=f"vote_{poll_id}_{opt}")])
    if not closed:
        kb.append([InlineKeyboardButton(text="🔒 Закрыть опрос", callback_data=f"closepoll_{poll_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def render_poll(poll):
    total = sum(opt["votes"] for opt in poll["options"].values())
    status = "🔒 ЗАКРЫТ" if poll["closed"] else "🟢 АКТИВЕН"
    text = f"📊 <b>Опрос #{poll['id']}</b> — {status}\n\n"
    text += f"❓ <b>{poll['question']}</b>\n\n"
    for opt, data in poll["options"].items():
        pct = round(data["votes"] / max(total, 1) * 100, 1)
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        text += f"{bar} {pct}% ({data['votes']}) — {opt}\n"
    text += f"\n📊 Всего голосов: {total}"
    return text

async def update_chat_admins(chat_id):
    try:
        members = await bot.get_chat_administrators(chat_id)
        admin_ids = []
        for member in members:
            if isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
                admin_ids.append(member.user.id)
        admins_sys.update_auto(chat_id, admin_ids)
        return admin_ids
    except Exception as e:
        print(f"Ошибка получения админов чата {chat_id}: {e}")
        return []

async def reminder_task():
    while True:
        try:
            now = datetime.now()
            for event in schedule.get_upcoming(hours=48):
                event_time = datetime.fromisoformat(event["datetime"])
                time_until = event_time - now
                etype = EVENT_TYPES.get(event["type"], {"emoji": "📅", "name": "Событие"})
                if timedelta(minutes=55) <= time_until <= timedelta(minutes=65) and not event.get("reminded_1h"):
                    text = f"""{etype['emoji']} <b>Напоминание!</b>

<b>{event['title']}</b>
📅 {format_datetime(event_time)}
🏷️ Тип: {etype['name']}

⏰ <b>Через 1 час!</b>"""
                    if event.get("description"): text += f"\n\n📝 {event['description']}"
                    try:
                        await bot.send_message(event["chat_id"], text, parse_mode="HTML")
                        schedule.mark_reminded(event["id"], "1h")
                    except Exception as e: print(f"Ошибка напоминания 1ч: {e}")
                elif timedelta(hours=23, minutes=55) <= time_until <= timedelta(hours=24, minutes=5) and not event.get("reminded_24h"):
                    text = f"""{etype['emoji']} <b>Напоминание на завтра!</b>

<b>{event['title']}</b>
📅 {format_datetime(event_time)}
🏷️ Тип: {etype['name']}

⏰ <b>Через 24 часа!</b>"""
                    if event.get("description"): text += f"\n\n📝 {event['description']}"
                    try:
                        await bot.send_message(event["chat_id"], text, parse_mode="HTML")
                        schedule.mark_reminded(event["id"], "24h")
                    except Exception as e: print(f"Ошибка напоминания 24ч: {e}")
        except Exception as e: print(f"Ошибка в reminder_task: {e}")
        await asyncio.sleep(60)


# ═══════════════════════════════════════════════════════════════
#  ОБРАБОТЧИКИ
# ═══════════════════════════════════════════════════════════════

@router.chat_member()
async def on_chat_member_update(event: ChatMemberUpdated):
    if event.new_chat_member.status == "member" and event.old_chat_member.status in ["left", "kicked"]:
        user = event.new_chat_member.user
        chat = event.chat
        await update_chat_admins(chat.id)
        if bans.is_banned(user.id, chat.id):
            await bot.ban_chat_member(chat.id, user.id)
            return
        mention = get_mention(user)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧤 Вратарь", callback_data="pos_gk")],
            [InlineKeyboardButton(text="🛡️ Защитник", callback_data="pos_def")],
            [InlineKeyboardButton(text="⚙️ Полузащитник", callback_data="pos_mid")],
            [InlineKeyboardButton(text="⚽ Нападающий", callback_data="pos_att")],
        ])
        welcome_text = f"""⚽ <b>Добро пожаловать в Aurum FC!</b> ⚽

Привет, {mention}! 👋

Ты попал в лучший футбольный клуб! 🏆
Чтобы мы могли вести твою статистику, пожалуйста, выбери свою игровую позицию:

<i>Если передумаешь — всегда можно сменить через /position</i>"""
        await bot.send_message(chat.id, welcome_text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "pos_gk")
async def pos_gk(callback: CallbackQuery):
    players.set_position(callback.from_user.id, "gk")
    await callback.message.edit_text(
        f"✅ Отлично, {get_mention(callback.from_user)}!\n"
        f"Твоя позиция: <b>🧤 Вратарь</b>\n\n"
        f"Теперь ты в системе Aurum FC! Используй /stats чтобы посмотреть свою статистику.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "pos_def")
async def pos_def(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛡️ Центральный защитник", callback_data="pos_cb")],
        [InlineKeyboardButton(text="⬅️ Левый защитник", callback_data="pos_lb")],
        [InlineKeyboardButton(text="➡️ Правый защитник", callback_data="pos_rb")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="pos_back")],
    ])
    await callback.message.edit_text("Выбери конкретную позицию защитника:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "pos_mid")
async def pos_mid(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Опорный", callback_data="pos_cdm")],
        [InlineKeyboardButton(text="⚙️ Центральный", callback_data="pos_cm")],
        [InlineKeyboardButton(text="🎨 Атакующий", callback_data="pos_cam")],
        [InlineKeyboardButton(text="⬅️ Левый", callback_data="pos_lm")],
        [InlineKeyboardButton(text="➡️ Правый", callback_data="pos_rm")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="pos_back")],
    ])
    await callback.message.edit_text("Выбери конкретную позицию полузащитника:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "pos_att")
async def pos_att(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Левый вингер", callback_data="pos_lw")],
        [InlineKeyboardButton(text="➡️ Правый вингер", callback_data="pos_rw")],
        [InlineKeyboardButton(text="⚽ Нападающий", callback_data="pos_st")],
        [InlineKeyboardButton(text="🎯 Форвард", callback_data="pos_cf")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="pos_back")],
    ])
    await callback.message.edit_text("Выбери конкретную позицию нападающего:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "pos_back")
async def pos_back(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧤 Вратарь", callback_data="pos_gk")],
        [InlineKeyboardButton(text="🛡️ Защитник", callback_data="pos_def")],
        [InlineKeyboardButton(text="⚙️ Полузащитник", callback_data="pos_mid")],
        [InlineKeyboardButton(text="⚽ Нападающий", callback_data="pos_att")],
    ])
    await callback.message.edit_text("⚽ <b>Выбери свою игровую позицию:</b>", reply_markup=kb, parse_mode="HTML")
    await callback.answer()

for pos_key, pos_name in POSITIONS.items():
    @router.callback_query(F.data == f"pos_{pos_key}")
    async def pos_handler(callback: CallbackQuery, pos=pos_key, name=pos_name):
        players.set_position(callback.from_user.id, pos)
        await callback.message.edit_text(
            f"✅ <b>Позиция выбрана!</b>\n\n"
            f"{get_mention(callback.from_user)}, твоя позиция: <b>{name}</b>\n\n"
            f"📊 Используй /stats для просмотра статистики\n"
            f"⚙️ /position — сменить позицию",
            parse_mode="HTML"
        )
        await callback.answer()

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    mention = get_mention(user)
    if message.chat.type != ChatType.PRIVATE:
        await update_chat_admins(message.chat.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧤 Вратарь", callback_data="pos_gk")],
        [InlineKeyboardButton(text="🛡️ Защитник", callback_data="pos_def")],
        [InlineKeyboardButton(text="⚙️ Полузащитник", callback_data="pos_mid")],
        [InlineKeyboardButton(text="⚽ Нападающий", callback_data="pos_att")],
    ])
    await message.answer(
        f"⚽ <b>Aurum FC Bot</b> ⚽\n\n"
        f"Привет, {mention}!\n"
        f"Я бот для управления статистикой, модерации и расписания клуба Aurum FC.\n\n"
        f"<b>Выбери свою позицию:</b>",
        reply_markup=kb, parse_mode="HTML"
    )

@router.message(Command("position"))
async def cmd_position(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧤 Вратарь", callback_data="pos_gk")],
        [InlineKeyboardButton(text="🛡️ Защитник", callback_data="pos_def")],
        [InlineKeyboardButton(text="⚙️ Полузащитник", callback_data="pos_mid")],
        [InlineKeyboardButton(text="⚽ Нападающий", callback_data="pos_att")],
    ])
    await message.answer("⚽ <b>Выбери новую позицию:</b>", reply_markup=kb, parse_mode="HTML")

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    stats = players.get(user_id)
    if not stats or not stats.get("position"):
        await message.answer("❌ Ты ещё не зарегистрирован!\nИспользуй /start или /position для выбора позиции.")
        return
    pos = POSITIONS.get(stats["position"], stats["position"])
    text = f"""📊 <b>Статистика игрока</b> — {get_mention(message.from_user)}

🏷️ <b>Позиция:</b> {pos}
⚽ <b>Голы:</b> {stats.get("goals", 0)}
🎯 <b>Передачи:</b> {stats.get("assists", 0)}
🏟️ <b>Матчи:</b> {stats.get("matches", 0)}
✅ <b>Победы:</b> {stats.get("wins", 0)}
🤝 <b>Ничьи:</b> {stats.get("draws", 0)}
❌ <b>Поражения:</b> {stats.get("losses", 0)}
🟨 <b>Жёлтые карточки:</b> {stats.get("yellow_cards", 0)}
🟥 <b>Красные карточки:</b> {stats.get("red_cards", 0)}

📈 <b>Винрейт:</b> {round(stats.get("wins", 0) / max(stats.get("matches", 1), 1) * 100, 1)}%"""
    await message.answer(text, parse_mode="HTML")

@router.message(Command("top"))
async def cmd_top(message: Message):
    all_players = players.get_all()
    if not all_players:
        await message.answer("📭 Пока нет зарегистрированных игроков.")
        return
    sorted_players = sorted(
        [(uid, data) for uid, data in all_players.items() if data.get("position")],
        key=lambda x: x[1].get("goals", 0), reverse=True
    )[:10]
    text = "🏆 <b>Топ бомбардиров Aurum FC</b>\n\n"
    for i, (uid, data) in enumerate(sorted_players, 1):
        pos = POSITIONS.get(data.get("position", ""), "?")
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        text += f"{medal} {pos} — {data.get('goals', 0)} голов\n"
    await message.answer(text, parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════
#  МОДЕРАЦИЯ
# ═══════════════════════════════════════════════════════════════

@router.message(Command("warn"))
async def cmd_warn(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы могут выдавать варны.")
        return
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение нарушителя.")
        return
    target = message.reply_to_message.from_user
    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else "Без причины"
    count = warns.add(target.id, message.chat.id, reason, message.from_user.id)
    text = f"⚠️ <b>Варн #{count}</b> для {get_mention(target)}\n"
    text += f"📋 Причина: <i>{reason}</i>\n"
    text += f"👮 Выдал: {get_mention(message.from_user)}"
    if count >= 3:
        text += "\n\n🚫 <b>3 варна — автоматический бан!</b>"
        await bot.ban_chat_member(message.chat.id, target.id)
        bans.add(target.id, message.chat.id, None, "3 варна", message.from_user.id)
    await message.answer(text, parse_mode="HTML")

@router.message(Command("unwarn"))
async def cmd_unwarn(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы.")
        return
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение.")
        return
    target = message.reply_to_message.from_user
    new_count = warns.remove(target.id, message.chat.id)
    await message.answer(f"✅ Варн снят с {get_mention(target)}\nТекущее количество варнов: {new_count}", parse_mode="HTML")

@router.message(Command("warns"))
async def cmd_warns(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    data = warns.get(target.id, message.chat.id)
    text = f"⚠️ <b>Варны</b> — {get_mention(target)}\nКоличество: <b>{data['count']}/3</b>\n\n"
    for i, w in enumerate(data.get("history", []), 1):
        text += f"{i}. {w['reason']} ({w['date'][:10]})\n"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("mute"))
async def cmd_mute(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы.")
        return
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение.\nФормат: /mute 30 причина")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer("❌ Формат: /mute <минуты> [причина]")
        return
    try:
        minutes = int(args[1])
    except ValueError:
        await message.answer("❌ Укажи число минут.")
        return
    reason = args[2] if len(args) > 2 else "Без причины"
    target = message.reply_to_message.from_user
    until = mutes.add(target.id, message.chat.id, minutes, reason, message.from_user.id)
    from aiogram.types import ChatPermissions
    await bot.restrict_chat_member(message.chat.id, target.id, ChatPermissions(can_send_messages=False), until_date=datetime.fromisoformat(until))
    await message.answer(
        f"🔇 <b>Мут</b> для {get_mention(target)}\n"
        f"⏱️ Длительность: {format_duration(minutes)}\n"
        f"📋 Причина: <i>{reason}</i>\n"
        f"👮 Выдал: {get_mention(message.from_user)}",
        parse_mode="HTML"
    )

@router.message(Command("unmute"))
async def cmd_unmute(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы.")
        return
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение.")
        return
    target = message.reply_to_message.from_user
    mutes.unmute(target.id, message.chat.id)
    from aiogram.types import ChatPermissions
    await bot.restrict_chat_member(message.chat.id, target.id, ChatPermissions(
        can_send_messages=True, can_send_photos=True, can_send_videos=True,
        can_send_audios=True, can_send_documents=True, can_send_polls=True,
        can_send_other_messages=True, can_add_web_page_previews=True,
        can_change_info=False, can_invite_users=True, can_pin_messages=False
    ))
    await message.answer(f"🔊 {get_mention(target)} размучен!", parse_mode="HTML")

@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы.")
        return
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение.\nФормат: /ban [минуты] причина")
        return
    args = message.text.split(maxsplit=2)
    target = message.reply_to_message.from_user
    minutes = None
    reason = "Без причины"
    if len(args) > 1:
        try:
            minutes = int(args[1])
            reason = args[2] if len(args) > 2 else "Без причины"
        except ValueError:
            reason = " ".join(args[1:])
    until = bans.add(target.id, message.chat.id, minutes, reason, message.from_user.id)
    if minutes:
        await bot.ban_chat_member(message.chat.id, target.id, until_date=datetime.fromisoformat(until))
        dur_text = format_duration(minutes)
    else:
        await bot.ban_chat_member(message.chat.id, target.id)
        dur_text = "НАВСЕГДА"
    await message.answer(
        f"🚫 <b>Бан</b> для {get_mention(target)}\n"
        f"⏱️ Длительность: {dur_text}\n"
        f"📋 Причина: <i>{reason}</i>\n"
        f"👮 Выдал: {get_mention(message.from_user)}",
        parse_mode="HTML"
    )

@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы.")
        return
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение.")
        return
    target = message.reply_to_message.from_user
    bans.unban(target.id, message.chat.id)
    await bot.unban_chat_member(message.chat.id, target.id)
    await message.answer(f"✅ {get_mention(target)} разбанен!", parse_mode="HTML")

@router.message(Command("kick"))
async def cmd_kick(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы.")
        return
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение.")
        return
    target = message.reply_to_message.from_user
    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else "Без причины"
    await bot.ban_chat_member(message.chat.id, target.id)
    await bot.unban_chat_member(message.chat.id, target.id)
    await message.answer(f"👢 {get_mention(target)} кикнут!\n📋 Причина: <i>{reason}</i>", parse_mode="HTML")

# ═══════════════════════════════════════════════════════════════
#  ЗАМЕТКИ ТРЕНЕРА
# ═══════════════════════════════════════════════════════════════

@router.message(Command("note"))
async def cmd_note(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только тренер/админ может делать заметки.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "📝 <b>Заметки тренера</b>\n\n"
            "Форматы:\n"
            "• <code>/note текст</code> — общая заметка\n"
            "• <code>/note</code> (ответом на сообщение игрока) — заметка об игроке\n\n"
            "Просмотр:\n"
            "• /notes — все общие заметки\n"
            "• /mynotes — мои заметки тренера\n"
            "• /playernotes (ответом) — заметки об игроке",
            parse_mode="HTML"
        )
        return
    text = args[1]
    author = message.from_user
    if message.reply_to_message:
        target = message.reply_to_message.from_user
        note_id = coach_notes.add_player_note(target.id, text, author.id, author.first_name)
        await message.answer(
            f"📝 <b>Заметка об игроке</b> {get_mention(target)} добавлена!\n"
            f"📋 #{note_id}: <i>{text[:100]}{'...' if len(text) > 100 else ''}</i>",
            parse_mode="HTML"
        )
    else:
        note_id = coach_notes.add_general(text, author.id, author.first_name)
        await message.answer(
            f"📝 <b>Общая заметка</b> #{note_id} добавлена!\n"
            f"📋 <i>{text[:100]}{'...' if len(text) > 100 else ''}</i>",
            parse_mode="HTML"
        )

@router.message(Command("notes"))
async def cmd_notes(message: Message):
    notes = coach_notes.get_general()
    if not notes:
        await message.answer("📝 Общих заметок пока нет.")
        return
    text = "📝 <b>Общие заметки тренера</b>\n\n"
    for n in notes[-10:]:
        date = n["date"][:10]
        text += f"<b>#{n['id']}</b> ({date}) — <i>{n['text'][:80]}{'...' if len(n['text']) > 80 else ''}</i>\n"
        text += f"   👤 {n['author_name']}\n\n"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("playernotes"))
async def cmd_player_notes(message: Message):
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение игрока.")
        return
    target = message.reply_to_message.from_user
    notes = coach_notes.get_player_notes(target.id)
    if not notes:
        await message.answer(f"📝 Заметок об {get_mention(target)} пока нет.")
        return
    text = f"📝 <b>Заметки об игроке</b> {get_mention(target)}\n\n"
    for n in notes[-10:]:
        date = n["date"][:10]
        text += f"<b>#{n['id']}</b> ({date}) — <i>{n['text'][:100]}{'...' if len(n['text']) > 100 else ''}</i>\n"
        text += f"   👤 {n['author_name']}\n\n"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("mynotes"))
async def cmd_my_notes(message: Message):
    all_notes = coach_notes.get_general()
    my_notes = [n for n in all_notes if n.get("author_id") == message.from_user.id]
    if not my_notes:
        await message.answer("📝 У тебя пока нет заметок.")
        return
    text = "📝 <b>Мои заметки</b>\n\n"
    for n in my_notes[-10:]:
        date = n["date"][:10]
        text += f"<b>#{n['id']}</b> ({date}) — <i>{n['text'][:100]}{'...' if len(n['text']) > 100 else ''}</i>\n\n"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("delnote"))
async def cmd_del_note(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Формат: /delnote <id>")
        return
    try:
        note_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    coach_notes.delete_note(note_id)
    await message.answer(f"✅ Заметка #{note_id} удалена.")


# ═══════════════════════════════════════════════════════════════
#  РАСПИСАНИЕ
# ═══════════════════════════════════════════════════════════════

@router.message(Command("schedule"))
async def cmd_schedule(message: Message):
    events = schedule.get_all(message.chat.id)
    if not events:
        await message.answer(
            "📅 <b>Расписание пусто</b>\n\n"
            "Добавить событие: <code>/addschedule Название | дата время | описание</code>\n"
            "Или: <code>/addschedule Матч против Львов | завтра 19:00 | Стадион Центральный</code>\n\n"
            "Бот <b>автоматически определит</b> тип события (матч/тренировка/лига)!",
            parse_mode="HTML"
        )
        return
    text = "📅 <b>Расписание Aurum FC</b>\n\n"
    now = datetime.now()
    for e in events[:15]:
        event_time = datetime.fromisoformat(e["datetime"])
        etype = EVENT_TYPES.get(e["type"], {"emoji": "📅", "name": "Событие"})
        status = "✅" if event_time > now else "✔️"
        text += f"{status} <b>#{e['id']}</b> {etype['emoji']} {e['title']}\n"
        text += f"   📅 {format_datetime(event_time)}\n"
        text += f"   🏷️ {etype['name']}\n"
        if e.get("description"):
            text += f"   📝 {e['description'][:50]}{'...' if len(e['description']) > 50 else ''}\n"
        text += "\n"
    text += "\n<i>Используй /addschedule чтобы добавить событие</i>"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("addschedule"))
async def cmd_add_schedule(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы могут добавлять в расписание.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "📅 <b>Добавить в расписание</b>\n\n"
            "Формат: <code>/addschedule Название | дата время | описание</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/addschedule Матч vs Динамо | сегодня 19:00 | Стадион Центральный</code>\n"
            "• <code>/addschedule Тренировка | завтра 18:30 | База Aurum</code>\n"
            "• <code>/addschedule Лига — 3 тур | 05.07 20:00 | Выездной матч</code>\n\n"
            "Бот <b>автоматически определит</b> тип события по названию!",
            parse_mode="HTML"
        )
        return
    parts = args[1].split(" | ")
    title = parts[0].strip()
    event_type = detect_event_type(title)
    etype_info = EVENT_TYPES.get(event_type, {"emoji": "📅", "name": "Событие"})
    event_dt = None
    description = ""
    if len(parts) >= 2:
        event_dt = parse_datetime(parts[1])
    if len(parts) >= 3:
        description = parts[2].strip()
    if not event_dt:
        event_dt = parse_datetime(args[1])
    if not event_dt:
        await message.answer(
            "❌ Не удалось распознать дату и время.\n"
            "Используй форматы: <code>сегодня 18:00</code>, <code>завтра 19:30</code>, <code>05.07 20:00</code>"
        )
        return
    if event_dt < datetime.now():
        await message.answer("❌ Дата события уже прошла! Укажи будущую дату.")
        return
    event_id = schedule.add_event(message.chat.id, title, event_dt, event_type, description, message.from_user.id)
    text = f"""✅ <b>Событие добавлено!</b>

{etype_info['emoji']} <b>{title}</b>
📅 {format_datetime(event_dt)}
🏷️ Тип: {etype_info['name']} (автоопределён)
📝 {description if description else 'Без описания'}

<i>Бот напомнит за 24 часа и за 1 час до события!</i>"""
    await message.answer(text, parse_mode="HTML")

@router.message(Command("delschedule"))
async def cmd_del_schedule(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Формат: /delschedule <id>")
        return
    try:
        event_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    schedule.delete_event(event_id)
    await message.answer(f"✅ Событие #{event_id} удалено из расписания.")

# ═══════════════════════════════════════════════════════════════
#  ГОЛОСОВАНИЯ
# ═══════════════════════════════════════════════════════════════

@router.message(Command("poll"))
async def cmd_poll(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "📊 <b>Создать опрос (голосование)</b>\n\n"
            "<b>Лёгкий формат:</b>\n"
            "<code>/poll Вопрос / вариант1 / вариант2 / вариант3</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/poll Кто лучший игрок матча? / Иван / Петр / Сергей</code>\n"
            "• <code>/poll Будем на тренировке? / Да / Нет / Не знаю</code>\n"
            "• <code>/poll Состав на матч / 4-4-2 / 4-3-3 / 3-5-2</code>\n\n"
            "Разделяй <b>/</b> — вопрос слева, варианты справа.",
            parse_mode="HTML"
        )
        return
    parts = [p.strip() for p in args[1].split(" / ")]
    if len(parts) < 2:
        await message.answer("❌ Нужен хотя бы 1 вариант ответа. Используй <code>/</code> для разделения.")
        return
    question = parts[0]
    options = parts[1:]
    if len(options) > 10:
        await message.answer("❌ Максимум 10 вариантов.")
        return
    poll_id = polls.create(message.chat.id, question, options, message.from_user.id)
    poll = polls.get(poll_id)
    text = render_poll(poll)
    kb = build_poll_kb(poll_id, options)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("vote_"))
async def on_vote(callback: CallbackQuery):
    parts = callback.data.split("_", 2)
    if len(parts) < 3:
        await callback.answer("Ошибка")
        return
    poll_id = int(parts[1])
    option = parts[2]
    poll = polls.get(poll_id)
    if not poll:
        await callback.answer("Опрос не найден")
        return
    success, msg = polls.vote(poll_id, option, callback.from_user.id)
    if not success:
        await callback.answer(msg)
        return
    await callback.answer(f"✅ Голос за «{option}» учтён!")
    poll = polls.get(poll_id)
    text = render_poll(poll)
    kb = build_poll_kb(poll_id, list(poll["options"].keys()), poll["closed"])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        pass

@router.callback_query(F.data.startswith("closepoll_"))
async def on_close_poll(callback: CallbackQuery):
    parts = callback.data.split("_")
    poll_id = int(parts[1])
    poll = polls.get(poll_id)
    if not poll:
        await callback.answer("Опрос не найден")
        return
    if callback.from_user.id != poll["created_by"] and not is_admin(callback.from_user.id, callback.message.chat.id):
        await callback.answer("❌ Только создатель или админ может закрыть опрос")
        return
    polls.close(poll_id)
    poll = polls.get(poll_id)
    text = render_poll(poll)
    kb = build_poll_kb(poll_id, list(poll["options"].keys()), closed=True)
    await callback.answer("🔒 Опрос закрыт!")
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        pass

@router.message(Command("polllist"))
async def cmd_poll_list(message: Message):
    active = [p for p in polls.data.get("polls", []) if not p.get("closed") and p.get("chat_id") == message.chat.id]
    if not active:
        await message.answer("📊 Активных опросов пока нет. Создай: <code>/poll Вопрос / вариант1 / вариант2</code>", parse_mode="HTML")
        return
    text = "📊 <b>Активные опросы:</b>\n\n"
    for p in active[-5:]:
        total = sum(opt["votes"] for opt in p["options"].values())
        text += f"<b>#{p['id']}</b> {p['question']}\n"
        text += f"   📊 {total} голосов\n\n"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("delpoll"))
async def cmd_del_poll(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Формат: /delpoll <id>")
        return
    try:
        poll_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    polls.delete(poll_id)
    await message.answer(f"✅ Опрос #{poll_id} удалён.")


# ═══════════════════════════════════════════════════════════════
#  СТАТИСТИКА (АДМИН)
# ═══════════════════════════════════════════════════════════════

@router.message(Command("addstat"))
async def cmd_addstat(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы.")
        return
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение игрока.")
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Формат: /addstat <тип> <значение>\nТипы: goals, assists, matches, wins, draws, losses, yellow_cards, red_cards")
        return
    stat_type = args[1]
    try:
        value = int(args[2])
    except ValueError:
        await message.answer("❌ Значение должно быть числом.")
        return
    target = message.reply_to_message.from_user
    players.add_stat(target.id, stat_type, value)
    stat_names = {"goals": "⚽ Голы", "assists": "🎯 Передачи", "matches": "🏟️ Матчи",
        "wins": "✅ Победы", "draws": "🤝 Ничьи", "losses": "❌ Поражения",
        "yellow_cards": "🟨 ЖК", "red_cards": "🟥 КК"}
    await message.answer(f"✅ Добавлено {value} к {stat_names.get(stat_type, stat_type)} для {get_mention(target)}", parse_mode="HTML")

@router.message(Command("setstat"))
async def cmd_setstat(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы.")
        return
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение игрока.")
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Формат: /setstat <тип> <значение>")
        return
    stat_type = args[1]
    try:
        value = int(args[2])
    except ValueError:
        await message.answer("❌ Значение должно быть числом.")
        return
    target = message.reply_to_message.from_user
    players.set_stat(target.id, stat_type, value)
    await message.answer(f"✅ Установлено {value} для {get_mention(target)} ({stat_type})", parse_mode="HTML")

@router.message(Command("playerstats"))
async def cmd_playerstats(message: Message):
    if not is_admin(message.from_user.id, message.chat.id):
        await message.answer("❌ Только админы.")
        return
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение игрока.")
        return
    target = message.reply_to_message.from_user
    stats = players.get(target.id)
    if not stats:
        await message.answer("❌ Игрок не найден в базе.")
        return
    pos = POSITIONS.get(stats.get("position", ""), "Не указана")
    text = f"""📊 <b>Полная статистика</b> — {get_mention(target)}

🏷️ Позиция: {pos}
⚽ Голы: {stats.get('goals', 0)}
🎯 Передачи: {stats.get('assists', 0)}
🏟️ Матчи: {stats.get('matches', 0)}
✅ Победы: {stats.get('wins', 0)}
🤝 Ничьи: {stats.get('draws', 0)}
❌ Поражения: {stats.get('losses', 0)}
🟨 ЖК: {stats.get('yellow_cards', 0)}
🟥 КК: {stats.get('red_cards', 0)}

📅 Зарегистрирован: {stats.get('registered', 'Неизвестно')[:10]}"""
    await message.answer(text, parse_mode="HTML")

# ═══════════════════════════════════════════════════════════════
#  УПРАВЛЕНИЕ АДМИНАМИ
# ═══════════════════════════════════════════════════════════════

@router.message(Command("admins"))
async def cmd_admins(message: Message):
    if message.chat.type == ChatType.PRIVATE:
        await message.answer("❌ Эта команда работает только в группах.")
        return
    chat_admins = await update_chat_admins(message.chat.id)
    all_admins = admins_sys.get_all(message.chat.id)
    text = "👮 <b>Администраторы Aurum FC</b>\n\n"
    text += f"<b>Автоопределённые ({len(chat_admins)}):</b>\n"
    for uid in chat_admins:
        text += f"• ID: {uid}\n"
    manual = set(admins_sys.manual)
    if OWNER_ID:
        manual.discard(OWNER_ID)
    if manual:
        text += f"\n<b>Ручное добавление ({len(manual)}):</b>\n"
        for uid in manual:
            text += f"• ID: {uid}\n"
    if OWNER_ID:
        text += f"\n<b>👑 Владелец:</b> {OWNER_ID}\n"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("addadmin"))
async def cmd_add_admin(message: Message):
    if not is_admin(message.from_user.id, message.chat.id if message.chat.type != ChatType.PRIVATE else None):
        await message.answer("❌ Недостаточно прав.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Формат: /addadmin <user_id>")
        return
    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    admins_sys.add_manual(user_id)
    await message.answer(f"✅ Пользователь {user_id} добавлен в админы.")

@router.message(Command("removeadmin"))
async def cmd_remove_admin(message: Message):
    if not is_admin(message.from_user.id, message.chat.id if message.chat.type != ChatType.PRIVATE else None):
        await message.answer("❌ Недостаточно прав.")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Формат: /removeadmin <user_id>")
        return
    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    admins_sys.remove_manual(user_id)
    await message.answer(f"✅ Пользователь {user_id} удалён из админов.")

# ═══════════════════════════════════════════════════════════════
#  ОБЩИЕ КОМАНДЫ
# ═══════════════════════════════════════════════════════════════

@router.message(Command("help"))
async def cmd_help(message: Message):
    text = """⚽ <b>Aurum FC Bot — Справка</b>

<b>🎮 Игрокам:</b>
/start — Регистрация / приветствие
/position — Сменить позицию
/stats — Моя статистика
/top — Топ бомбардиров

<b>⚠️ Модерация (админы):</b>
/warn [причина] — Выдать варн (ответом)
/unwarn — Снять варн
/warns — Проверить варны
/mute <мин> [причина] — Мут
/unmute — Размутить
/ban [мин] [причина] — Бан (без мин = навсегда)
/unban — Разбанить
/kick [причина] — Кик

<b>📝 Заметки тренера:</b>
/note текст — Общая заметка
/note (ответом) — Заметка об игроке
/notes — Все общие заметки
/playernotes (ответом) — Заметки об игроке
/mynotes — Мои заметки
/delnote <id> — Удалить заметку

<b>📅 Расписание:</b>
/schedule — Показать расписание
/addschedule Название | дата | описание — Добавить
/delschedule <id> — Удалить событие

<b>📊 Голосования:</b>
/poll Вопрос / вар1 / вар2 / вар3 — Создать опрос
/polllist — Активные опросы
/delpoll <id> — Удалить опрос

<b>📊 Статистика (админы):</b>
/addstat <тип> <знач> — Добавить стат
/setstat <тип> <знач> — Установить стат
/playerstats — Статистика игрока

<b>👮 Управление админами:</b>
/admins — Список админов
/addadmin <id> — Добавить админа
/removeadmin <id> — Удалить админа

<b>Типы статов:</b> goals, assists, matches, wins, draws, losses, yellow_cards, red_cards"""
    await message.answer(text, parse_mode="HTML")

@router.message(Command("info"))
async def cmd_info(message: Message):
    await message.answer(
        "⚽ <b>Aurum FC Bot</b> ⚽\n\n"
        "Бот для управления статистикой, модерации и расписания футбольного клуба.\n\n"
        "📊 Статистика игроков\n"
        "⚠️ Модерация: варны, муты, баны, кики\n"
        "📝 Заметки тренера\n"
        "📅 Расписание с автонапоминаниями\n"
        "📊 Голосования\n"
        "🏆 Топы и рейтинги\n\n"
        "Используй /help для списка команд.",
        parse_mode="HTML"
    )

@router.message()
async def check_mute(message: Message):
    if message.chat.type == ChatType.PRIVATE:
        return
    if mutes.is_muted(message.from_user.id, message.chat.id):
        info = mutes.get_info(message.from_user.id, message.chat.id)
        remaining = info["until_dt"] - datetime.now()
        mins_left = int(remaining.total_seconds() / 60)
        try:
            await message.delete()
        except:
            pass
        notif = await message.answer(
            f"🔇 {get_mention(message.from_user)} в муте ещё {format_duration(mins_left)}!",
            parse_mode="HTML"
        )
        await asyncio.sleep(5)
        try:
            await notif.delete()
        except:
            pass
        return

# ═══════════════════════════════════════════════════════════════
#  ЗАПУСК
# ═══════════════════════════════════════════════════════════════

from aiohttp import web

async def health(request):
    return web.Response(text="OK")

async def run_web():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Health server on port {port}")

async def main():
    print("⚽ Aurum FC Bot v3.0 запущен!")
    asyncio.create_task(reminder_task())
    asyncio.create_task(run_web())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
