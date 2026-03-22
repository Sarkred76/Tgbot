import logging


import json

import asyncio
import threading

import os


import random


import time


from typing import Optional, Dict, Any, List


from collections import Counter


from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaAnimation,
)


from telegram.ext import (
    Application, 
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)


from telegram.error import NetworkError, TimedOut

# ===== КОНФИГУРАЦИЯ =====


BOT_TOKEN = "8501838456:AAH2vwub2OgwerfCqUs-mRcczr4P5l6Rwcs"


INITIAL_ADMIN_ID = (
    "881692999"  # Первый администратор (будет добавлен в список при создании файла)
)


DATA_FILE = "/data/bot_data.json"


ANIMATED_FORMATS = (".mp4", ".gif", ".webm")


AUTO_ANIMATED_RARITIES = ["Animated!"]


# Бонусы по редкостям


RARITY_BONUSES = {
    "T1": {"cents": 100, "points": 100, "probability": 45},
    "T2": {"cents": 250, "points": 250, "probability": 25},
    "T3": {"cents": 500, "points": 500, "probability": 12},
    "T4": {"cents": 1000, "points": 1000, "probability": 8},
    "T5": {"cents": 2000, "points": 2000, "probability": 5},
    "T6": {"cents": 5000, "points": 5000, "probability": 3},
    "T7": {"cents": 10000, "points": 10000, "probability": 1.5},
    "T8": {"cents": 50000, "points": 50000, "probability": 0.5},
    "UpgradeT1": {"cents": 200, "points": 200, "probability": 100},
    "UpgradeT2": {"cents": 500, "points": 500, "probability": 100},
    "UpgradeT3": {"cents": 1000, "points": 1000, "probability": 100},
    "UpgradeT4": {"cents": 2000, "points": 2000, "probability": 100},
    "UpgradeT5": {"cents": 4000, "points": 4000, "probability": 100},
    "UpgradeT6": {"cents": 10000, "points": 10000, "probability": 100},
    "UpgradeT7": {"cents": 20000, "points": 20000, "probability": 100},
}


# Настройка логирования


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot_errors.log"), logging.StreamHandler()],
)


logger = logging.getLogger(__name__)


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====


def load_data() -> Dict[str, Any]:
    """Загружает данные из файла или создает новую структуру."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Инициализируем активные трейды если нет
            if "active_trades" not in data:
                data["active_trades"] = {}

            if "achievements" not in data:
                data["achievements"] = {
                    "Замок": {"cards": [], "reward_claimed": False},
                    "Оплот": {"cards": [], "reward_claimed": False},
                    "Башня": {"cards": [], "reward_claimed": False},
                    "Инферно": {"cards": [], "reward_claimed": False},
                    "Некрополис": {"cards": [], "reward_claimed": False},
                    "Темница": {"cards": [], "reward_claimed": False},
                    "Цитадель": {"cards": [], "reward_claimed": False},
                    "Крепость": {"cards": [], "reward_claimed": False},
                    "Сопряжение": {"cards": [], "reward_claimed": False},
                }
            
            for user_id, user_data in data.get("users", {}).items():
                if "last_card_time" not in user_data:
                    user_data["last_card_time"] = 0
                if "free_rolls" not in user_data:
                    user_data["free_rolls"] = 0
                if "last_dice_time" not in user_data:
                    user_data["last_dice_time"] = 0
                if "casino_attempts" not in user_data:
                    user_data["casino_attempts"] = 10
                if "last_casino_reset" not in user_data:
                    user_data["last_casino_reset"] = 0
                # ⭐ ДОБАВЛЯЕМ ОТСЛЕЖИВАНИЕ ДОСТИЖЕНИЙ ⭐
                if "claimed_achievements" not in user_data:
                    user_data["claimed_achievements"] = []
            
            return data
            
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
            return {
                "users": {},
                "cards": [],
                "season": 1,
                "admins": [INITIAL_ADMIN_ID],
                "active_trades": {},
                "achievements": {
                    "Замок": {"cards": [], "reward_claimed": False},
                    "Оплот": {"cards": [], "reward_claimed": False},
                    "Башня": {"cards": [], "reward_claimed": False},
                    "Инферно": {"cards": [], "reward_claimed": False},
                    "Некрополис": {"cards": [], "reward_claimed": False},
                    "Темница": {"cards": [], "reward_claimed": False},
                    "Цитадель": {"cards": [], "reward_claimed": False},
                    "Крепость": {"cards": [], "reward_claimed": False},
                    "Сопряжение": {"cards": [], "reward_claimed": False},
                }
            }
    
    return {
        "users": {},
        "cards": [],
        "season": 1,
        "admins": [INITIAL_ADMIN_ID],
        "active_trades": {},
        "achievements": {
            "Замок": {"cards": [], "reward_claimed": False},
            "Оплот": {"cards": [], "reward_claimed": False},
            "Башня": {"cards": [], "reward_claimed": False},
            "Инферно": {"cards": [], "reward_claimed": False},
            "Некрополис": {"cards": [], "reward_claimed": False},
            "Темница": {"cards": [], "reward_claimed": False},
            "Цитадель": {"cards": [], "reward_claimed": False},
            "Крепость": {"cards": [], "reward_claimed": False},
            "Сопряжение": {"cards": [], "reward_claimed": False},
        }
    }

def check_casino_reset(user_data: Dict) -> None:
    """Проверяет и сбрасывает попытки казино в полночь по МСК."""

    import datetime

    # Получаем текущее время по МСК

    msk_tz = datetime.timezone(datetime.timedelta(hours=3))

    now_msk = datetime.datetime.now(msk_tz)

    # Получаем дату последнего сброса

    last_reset = user_data.get("last_casino_reset", 0)

    # Если сегодня ещё не сбрасывали

    if (
        last_reset == 0
        or now_msk.day != datetime.datetime.fromtimestamp(last_reset, msk_tz).day
    ):

        user_data["casino_attempts"] = 10

        user_data["last_casino_reset"] = int(now_msk.timestamp())


def save_data(data: Dict[str, Any]) -> None:
    """Сохраняет данные в файл."""

    try:

        with open(DATA_FILE, "w", encoding="utf-8") as f:

            json.dump(data, f, ensure_ascii=False, indent=2)

    except Exception as e:

        logger.error(f"Ошибка сохранения данных: {e}")


def is_admin(user_id: str, data: Dict[str, Any]) -> bool:
    """Проверяет, является ли пользователь администратором."""

    admins = data.get("admins", [])

    return user_id in admins


def find_card_by_id(card_id: int, cards: List[Dict]) -> Optional[Dict]:
    """Находит карточку по ID."""

    for card in cards:

        if card["id"] == card_id:

            return card

    return None


def create_cards_keyboard(
    current_index: int, total_cards: int
) -> Optional[InlineKeyboardMarkup]:
    """Создает инлайн-клавиатуру для бесконечной навигации."""

    if total_cards <= 0:

        return None

    nav_buttons = [
        InlineKeyboardButton("<", callback_data=f"card_prev_{current_index}"),
        InlineKeyboardButton(
            f"{current_index + 1}/{total_cards}", callback_data="card_info"
        ),
        InlineKeyboardButton(">", callback_data=f"card_next_{current_index}"),
    ]

    return InlineKeyboardMarkup([nav_buttons])


def determine_media_type(url: str, rarity: str) -> str:
    """Определяет тип медиа на основе URL и редкости."""

    if rarity in AUTO_ANIMATED_RARITIES:

        return "animation"

    if any(url.lower().endswith(ext) for ext in ANIMATED_FORMATS):

        return "animation"

    return "photo"


def generate_card_caption(
    card: Dict,
    user_data: Optional[Dict] = None,
    count: int = 1,
    show_bonus: bool = False,
) -> str:
    """Генерирует описание карточки с количеством дубликатов."""
    if user_data is None:
        if count > 1:
            caption = f"{card['title']}\nРедкость: {card['rarity']}"
        else:
            caption = f"{card['title']}\nРедкость: {card['rarity']}"
    
    caption = f"💥 BOOM\n{card['title']}\nРедкость: {card['rarity']}"
    
    # ⭐ ДОБАВЛЯЕМ ФРАКЦИЮ ⭐
    if card.get("faction"):
        caption += f"\nФракция: {card['faction']}"
    
    # Показываем бонусы только при получении новой карты
    if show_bonus:
        bonus = RARITY_BONUSES.get(card["rarity"], {"cents": 0, "points": 0})
        caption += f"\n🪙 +{bonus['cents']} центов\n💊 +{bonus['points']} поинтов"
    
    # Добавляем количество, если есть дубликаты
    if count > 1:
        caption += f"\n📦 Количество: {count} шт."
    
    caption += (
        f"\n\nПоинтов в этом сезоне: {user_data['season_points']}\n"
        f"Поинтов за все время: {user_data['total_points']}"
    )
    return caption


async def send_card(
    update_or_chat_id: Update,
    card: Dict,
    context: ContextTypes.DEFAULT_TYPE,
    caption: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    chat_id: Optional[int] = None,
) -> None:
    """Отправляет карточку в зависимости от типа медиа."""

    if isinstance(update_or_chat_id, Update):

        chat_id = update_or_chat_id.effective_chat.id

    if chat_id is None:

        return

    if card.get("media_type") == "animation":

        await context.bot.send_animation(
            chat_id=chat_id,
            animation=card["image_url"],
            caption=caption,
            reply_markup=reply_markup,
        )

    else:

        await context.bot.send_photo(
            chat_id=chat_id,
            photo=card["image_url"],
            caption=caption,
            reply_markup=reply_markup,
        )


async def edit_card_message(
    query, card: Dict, caption: str, reply_markup: InlineKeyboardMarkup
) -> None:
    """Редактирует сообщение с карточкой."""

    if card.get("media_type") == "animation":

        media = InputMediaAnimation(media=card["image_url"], caption=caption)

    else:

        media = InputMediaPhoto(media=card["image_url"], caption=caption)

    await query.edit_message_media(media=media, reply_markup=reply_markup)


# ===== КОМАНДЫ ПОЛЬЗОВАТЕЛЯ =====


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""

    try:

        keyboard = [
            [KeyboardButton("💣 Получить карту")],
            [KeyboardButton("🎲 Бросить кубик")],
            [
                KeyboardButton("📂 Мои карты"),
                KeyboardButton("👤 Мой профиль"),
            ],  # ← Добавлена кнопка
            [KeyboardButton("🔨 Крафт"), KeyboardButton("🎮 Мини-игры")],
            [KeyboardButton("🏆 Топ игроков")],
            [KeyboardButton("🔄 Трейд")],  # ← ДОБАВЬТЕ
        ]

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "Добро пожаловать! Используйте кнопки ниже:", reply_markup=reply_markup
        )

    except Exception as e:

        logger.error(f"Ошибка в start: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список команд."""
    try:
        user_id = str(update.effective_user.id)
        
        # Безопасная проверка админа
        try:
            data = load_data()
            admin_list = data.get("admins", [])
            admin = user_id in admin_list
        except Exception as e:
            logger.error(f"Ошибка проверки админа: {e}")
            admin = False
        
        response = "📜 Доступные команды:\n\n"
        
        # Основные команды
        response += "🎮 Основные команды:\n"
        response += "💣 Получить карту - получить карточку\n"
        response += "📂 Мои карты - посмотреть коллекцию\n"
        response += "👤 Мой профиль - статистика игрока\n"
        response += "🏆 Топ игроков - рейтинг по поинтам\n"
        response += "🎲 Бросить кубик - получить бесплатные попытки\n"
        response += "🎮 Мини-игры - казино и другие игры\n"
        response += "🔨 Крафт - скрафтить новую карту из 10 дубликатов\n"
        response += "🔄 Трейд - обмен картами с игроками\n\n"
        response += "🏆 Достижения - награды за сбор карт фракций\n"
        
        # Команды для всех
        response += "📝 Команды:\n"
        response += "/start - начать работу с ботом\n"
        response += "/help - показать это сообщение\n"
        response += "/profile - мой профиль\n"
        response += "/dice - бросить кубик\n"
        response += "/craft - крафт карт\n"
        response += "/top - топ игроков\n"
        response += "/trade - трейд карт\n"
        response += "/trade_accept - принять трейд\n"
        response += "/trade_decline - отклонить трейд\n"
        
        # Админ-команды
        if admin:
            response += "\n\n⚙️ Админ-команды:\n"
            response += "/add_card - добавить карточку в систему\n"
            response += "/edit_card - редактировать карту\n"
            response += "/card_info - информация о карте\n"
            response += "/add_card_to_player - добавить карту игроку\n"
            response += "/add_rolls_to_player - добавить попытки игроку\n"
            response += "/reset_season_points [ID] - сбросить поинты за сезон\n"
            response += "/cards - список всех карт\n"
            response += "/disabled_cards - выключенные карты\n"
            response += "/toggle_card [ID] - вкл/выкл карту\n"
            response += "/delete_card [ID] - удалить карту\n"
            response += "/broadcast [текст] - рассылка всем игрокам\n"
            response += "/reset_all_cards - сбросить все карты\n"
            response += "/reset_user [ID] - сбросить карты игрока\n"
            response += "/check_cards - статистика карт\n"
            response += "/list_admins - список админов\n"
            response += "/add_admin [ID] - добавить админа\n"
            response += "/remove_admin [ID] - удалить админа\n"
            
        response += "\n\n💡 Нужна помощь?\n"
        response += "Напишите администратору бота."
        
        # ⭐ УБРАЛИ parse_mode="Markdown" ⭐
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Ошибка в help: {e}")
        await update.message.reply_text("❌ Ошибка при показе помощи")

async def show_user_cards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню выбора редкости для просмотра коллекции."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text("У вас пока нет карточек!")
            else:
                await update.message.reply_text("У вас пока нет карточек!")
            return
        
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        unique_card_ids = list(card_counts.keys())
        
        # Считаем карты по редкостям
        rarity_cards = {}
        for card_id in unique_card_ids:
            card = find_card_by_id(card_id, data["cards"])
            if card:
                rarity = card.get("rarity", "T1")
                if rarity not in rarity_cards:
                    rarity_cards[rarity] = []
                rarity_cards[rarity].append((card_id, card_counts[card_id]))
        
        if not rarity_cards:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text("У вас пока нет карточек!")
            else:
                await update.message.reply_text("У вас пока нет карточек!")
            return
        
        # Создаём клавиатуру с редкостями
        keyboard = []
        
        # Обычные редкости T1-T8
        for rarity in ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"]:
            if rarity in rarity_cards:
                keyboard.append([
                    InlineKeyboardButton(
                        rarity,
                        callback_data=f"mycards_rarity_{rarity}"
                    )
                ])
        
        # Upgrade редкости
        upgrade_rarities = [r for r in rarity_cards.keys() if r.startswith("Upgrade")]
        if upgrade_rarities:
            keyboard.append([])
            for rarity in sorted(upgrade_rarities):
                keyboard.append([
                    InlineKeyboardButton(
                        rarity,
                        callback_data=f"mycards_rarity_{rarity}"
                    )
                ])
        
        # Кнопка "Все карты"
        keyboard.append([])
        keyboard.append([
            InlineKeyboardButton(
                "📋 Все карты",
                callback_data="mycards_all"
            )
        ])
        
        # ⭐ ПРОВЕРКА: callback или сообщение ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            # ⭐ УДАЛЯЕМ СТАРОЕ СООБЩЕНИЕ (с фото) И ОТПРАВЛЯЕМ НОВОЕ ⭐
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="📂 **Выберите редкость для просмотра:**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "📂 **Выберите редкость для просмотра:**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Ошибка при показе меню карт: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("Произошла ошибка")

async def show_cards_by_rarity(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    rarity: str,
    start_index: int = 0
) -> None:
    """Показывает карты конкретной редкости."""
    try:
        query = update.callback_query if hasattr(update, 'callback_query') else None
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            if query:
                await query.edit_message_text("У вас нет карточек!")
            else:
                await update.message.reply_text("У вас нет карточек!")
            return
        
        user_card_ids = user_data["cards"]
        card_counts = Counter(user_card_ids)
        
        # Фильтруем карты по редкости
        rarity_cards = []
        for card_id, count in card_counts.items():
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("rarity") == rarity:
                rarity_cards.append((card_id, count))
        
        if not rarity_cards:
            if query:
                await query.edit_message_text(f"У вас нет карт редкости {rarity}!")
            else:
                await update.message.reply_text(f"У вас нет карт редкости {rarity}!")
            return
        
        # Сортируем карты по ID
        rarity_cards.sort(key=lambda x: x[0])
        total_cards = len(rarity_cards)
        
        # Обработка навигации
        if start_index < 0:
            start_index = 0
        elif start_index >= total_cards:
            start_index = total_cards - 1
        
        card_id, count = rarity_cards[start_index]
        card = find_card_by_id(card_id, data["cards"])
        
        if not card:
            if query:
                await query.edit_message_text("Ошибка: карта не найдена")
            else:
                await update.message.reply_text("Ошибка: карта не найдена")
            return
        
        # Создаём клавиатуру навигации
        nav_buttons = []
        
        # Кнопка "Назад"
        if start_index > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    "<", 
                    callback_data=f"mycards_nav_{rarity}_{start_index - 1}"
                )
            )
        
        # Номер карты
        nav_buttons.append(
            InlineKeyboardButton(
                f"{start_index + 1}/{total_cards}", 
                callback_data="card_info"
            )
        )
        
        # Кнопка "Вперёд"
        if start_index < total_cards - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    ">", 
                    callback_data=f"mycards_nav_{rarity}_{start_index + 1}"
                )
            )
        
        # Кнопка "Назад к списку редкостей"
        keyboard = [nav_buttons]
        keyboard.append([
            InlineKeyboardButton(
                "📋 Назад к редкостям", 
                callback_data="mycards_back_to_rarities"
            )
        ])
        
        # Генерируем описание
        caption = generate_card_caption(card, user_data, count=count, show_bonus=False)
        
        if query:
            try:
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(
                    media=media, 
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as edit_error:
                logger.error(f"Ошибка редактирования: {edit_error}")
                try:
                    await query.message.delete()
                except:
                    pass
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=card["image_url"],
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await send_card(update, card, context, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Ошибка при показе карт редкости {rarity}: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("Произошла ошибка")
            

async def mycards_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок просмотра карт по редкостям."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if query.data == "mycards_all":
            # Показываем все карты (старая логика)
            if not user_data or not user_data.get("cards"):
                await query.edit_message_text("У вас пока нет карточек!")
                return
            
            user_card_ids = user_data["cards"]
            card_counts = Counter(user_card_ids)
            unique_card_ids = list(card_counts.keys())
            
            if not unique_card_ids:
                await query.edit_message_text("У вас пока нет карточек!")
                return
            
            card = find_card_by_id(unique_card_ids[0], data["cards"])
            if not card:
                await query.edit_message_text("Ошибка: карта не найдена")
                return
            
            keyboard = create_cards_keyboard(0, len(unique_card_ids))
            count = card_counts[card["id"]]
            caption = generate_card_caption(card, user_data, count=count, show_bonus=False)
            
            try:
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=keyboard)
            except Exception as edit_error:
                logger.error(f"Ошибка редактирования: {edit_error}")
                try:
                    await query.message.delete()
                except:
                    pass
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=card["image_url"],
                    caption=caption,
                    reply_markup=keyboard
                )
        
        elif query.data == "mycards_back_to_rarities":
            # ⭐ ВОЗВРАЩАЕМСЯ К ВЫБОРУ РЕДКОСТЕЙ ⭐
            # Удаляем сообщение с картой и показываем меню редкостей
            try:
                await query.message.delete()
            except:
                pass
            await show_user_cards(update, context)
        
        elif query.data.startswith("mycards_rarity_"):
            # Выбор редкости
            rarity = query.data.replace("mycards_rarity_", "")
            await show_cards_by_rarity(update, context, rarity, start_index=0)
        
        elif query.data.startswith("mycards_nav_"):
            # Навигация по картам конкретной редкости
            parts = query.data.replace("mycards_nav_", "").split("_")
            rarity = parts[0]
            index = int(parts[1]) if len(parts) > 1 else 0
            await show_cards_by_rarity(update, context, rarity, start_index=index)
        
    except Exception as e:
        logger.error(f"Ошибка в mycards_callback: {e}")
        await query.answer("Произошла ошибка", show_alert=True)


async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает профиль пользователя."""
    try:
        # ⭐ ОПРЕДЕЛЯЕМ: callback query или команда ⭐
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            user_id = str(query.from_user.id)
            chat_id = query.message.chat_id
            is_callback = True
        else:
            user_id = str(update.effective_user.id)
            chat_id = update.effective_chat.id
            is_callback = False
        
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data:
            if is_callback:
                await query.edit_message_text("❌ Вы ещё не начали игру!\nНажмите /start")
            else:
                await update.message.reply_text("❌ Вы ещё не начали игру!\nНажмите /start")
            return
        
        # Считаем уникальные карты пользователя
        user_card_ids = user_data.get("cards", [])
        unique_cards = len(set(user_card_ids))
        
        # Считаем общее количество доступных карт в игре
        total_available_cards = len(
            [card for card in data["cards"] if card.get("available", True)]
        )
        
        # Процент коллекции
        collection_percent = (
            round((unique_cards / total_available_cards * 100), 1)
            if total_available_cards > 0
            else 0
        )
        
        # Считаем карты по редкостям
        card_counts = Counter(user_card_ids)
        rarity_stats = {}
        for card_id in set(user_card_ids):
            card = find_card_by_id(card_id, data["cards"])
            if card:
                rarity = card.get("rarity", "T1")
                rarity_stats[rarity] = rarity_stats.get(rarity, 0) + 1
        
        # Формируем статистику по редкостям
        rarity_text = ""
        for rarity in [
            "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8",
            "UpgradeT1", "UpgradeT2", "UpgradeT3", "UpgradeT4",
            "UpgradeT5", "UpgradeT6", "UpgradeT7",
        ]:
            if rarity in rarity_stats:
                rarity_text += f"• {rarity}: {rarity_stats[rarity]} шт.\n"
        
        if not rarity_text:
            rarity_text = "Пока нет карт\n"
        
        claimed_count = len(user_data.get("claimed_achievements", []))
        
        profile_text = (
            f"👤 **Профиль пользователя**\n\n"
            f"🆔 ID: `{user_id}`\n"
            f"👤 Имя: {user_data.get('first_name', 'Неизвестно')}\n\n"
            f"💰 **Баланс:**\n"
            f"🪙 Центы: {user_data.get('cents', 0)}\n"
            f"💊 Поинты (сезон): {user_data.get('season_points', 0)}\n"
            f"💎 Поинты (всего): {user_data.get('total_points', 0)}\n\n"
            f"🃏 **Коллекция:**\n"
            f"📦 Собрано карт: {unique_cards}/{total_available_cards}\n"
            f"📊 Заполненность: {collection_percent}%\n"
            f"🔢 Всего получено: {len(user_card_ids)} (с дубликатами)\n\n"
            f"📈 **По редкостям:**\n"
            f"{rarity_text}\n"
            f"🎲 **Бесплатные попытки:** {user_data.get('free_rolls', 0)}\n"
            f"🏆 **Достижения:** {claimed_count}/9\n"
        )
        
        keyboard = [[InlineKeyboardButton("🏆 Достижения", callback_data="achievements_menu")]]
        
        # ⭐ ОТПРАВЛЯЕМ В ЗАВИСИМОСТИ ОТ ТИПА ⭐
        if is_callback:
            # Удаляем старое сообщение и отправляем новое
            try:
                await query.message.delete()
            except:
                pass
            await context.bot.send_message(
                chat_id=chat_id,
                text=profile_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                profile_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Ошибка показа профиля: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Произошла ошибка", show_alert=True)
        else:
            await update.message.reply_text("❌ Произошла ошибка при загрузке профиля")
            

async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок профиля."""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "achievements_menu":
            await achievements_menu(update, context)
        elif query.data == "profile_back":
            await my_profile(update, context)  # ← Вызывает универсальную my_profile
        elif query.data.startswith("achievement_claim_"):
            await claim_achievement(update, context)
        elif query.data == "achievement_claimed":
            await query.answer("✅ Вы уже получили эту награду!", show_alert=True)
        elif query.data == "achievement_progress":
            await query.answer("📊 Собирайте карты для завершения!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Ошибка profile_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик инлайн-кнопок навигации."""

    try:

        query = update.callback_query

        await query.answer()

        user_id = str(query.from_user.id)

        data = load_data()

        user_data = data["users"].get(user_id)

        if not user_data or not user_data.get("cards"):

            await query.edit_message_text("У вас больше нет карточек!")

            return

        user_card_ids = user_data["cards"]

        card_counts = Counter(user_card_ids)

        unique_card_ids = list(card_counts.keys())

        total_cards = len(unique_card_ids)

        if query.data and ("card_prev" in query.data or "card_next" in query.data):

            action = "prev" if "prev" in query.data else "next"

            current_index = int(query.data.split("_")[-1])

            new_index = (
                (current_index - 1) % total_cards
                if action == "prev"
                else (current_index + 1) % total_cards
            )

            card = find_card_by_id(unique_card_ids[new_index], data["cards"])

            if not card:

                await query.edit_message_text("Карточка не найдена!")

                return

            count = card_counts[card["id"]]

            caption = generate_card_caption(
                card, user_data, count=count, show_bonus=False
            )

            keyboard = create_cards_keyboard(new_index, total_cards)

            # ⭐ ДОБАВЬТЕ ЛОГИРОВАНИЕ ⭐

            logger.info(
                f"Попытка показать карту #{card['id']}: {card['image_url'][:100]}"
            )

            try:

                media = InputMediaPhoto(media=card["image_url"], caption=caption)

                await query.edit_message_media(media=media, reply_markup=keyboard)

            except Exception as edit_error:

                logger.error(
                    f"❌ Ошибка редактирования карты #{card['id']}: {edit_error}"
                )

                logger.error(f"URL: {card['image_url']}")

                # Отправляем как новое сообщение

                try:

                    await query.message.delete()

                except:

                    pass

                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=card["image_url"],
                    caption=caption,
                    reply_markup=keyboard,
                )

    except Exception as e:

        logger.error(f"Ошибка в callback: {e}")

        await query.answer("Произошла ошибка", show_alert=True)


def get_card_with_fixed_rarity(cards: List[Dict]) -> Optional[Dict]:
    """


    Двухэтапный выбор:


    1. Выбираем редкость по фиксированному шансу


    2. Из всех карт этой редкости выбираем случайную


    """

    if not cards:

        return None

    # Группируем карты по редкостям

    cards_by_rarity = {}

    for card in cards:

        rarity = card.get("rarity", "T1")

        if rarity not in cards_by_rarity:

            cards_by_rarity[rarity] = []

        cards_by_rarity[rarity].append(card)

    # Создаём список редкостей с весами

    available_rarities = []

    weights = []

    for rarity, rarity_cards in cards_by_rarity.items():

        if rarity_cards:  # Если есть карты такой редкости

            probability = RARITY_BONUSES.get(rarity, {"probability": 0}).get(
                "probability", 0
            )

            if probability > 0:

                available_rarities.append(rarity)

                weights.append(probability)

    if not available_rarities:

        return None

    # Этап 1: Выбираем редкость по фиксированному шансу

    total_weight = sum(weights)

    if total_weight == 0:

        return None

    # Нормализуем веса до 100%

    normalized_weights = [w / total_weight for w in weights]

    # Выбираем редкость

    chosen_rarity = random.choices(available_rarities, weights=normalized_weights, k=1)[
        0
    ]

    # Этап 2: Выбираем случайную карту из этой редкости

    rarity_cards = cards_by_rarity[chosen_rarity]

    return random.choice(rarity_cards)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений (кнопки)."""

    try:

        user_id = str(update.effective_user.id)

        data = load_data()

        text = update.message.text

                # ⭐ ПРОВЕРКА: если пользователь в шаге выбора партнёра для трейда ⭐
        if user_id in context.user_data:
            trade_info = context.user_data[user_id]
            if trade_info.get("step") == "select_partner":
                await process_partner_selection(update, context)
                return

        user_data = None

        if text == "💣 Получить карту":

            user_data = data["users"].get(user_id)

            if not user_data:

                user_data = {
                    "username": update.effective_user.username or "",
                    "first_name": update.effective_user.first_name or "",
                    "last_name": update.effective_user.last_name or "",
                    "cards": [],
                    "total_points": 0,
                    "season_points": 0,
                    "cents": 0,
                    "last_card_time": 0,
                    "free_rolls": 0,
                    "last_dice_time": 0,
                    "card_notification_sent": False, 
                }

                data["users"][user_id] = user_data

            COOLDOWN_SECONDS = 1 * 60 * 60

            current_time = int(time.time())

            time_passed = current_time - user_data.get("last_card_time", 0)

            # ⭐ ПРОВЕРКА: является ли пользователь админом ⭐

            is_admin_user = is_admin(user_id, data)

            # ⭐ ПРОВЕРКА: есть ли бесплатные попытки ⭐

            free_rolls = user_data.get("free_rolls", 0)

            use_free_roll = False

            # ⭐ АДМИНЫ ПРОПУСКАЮТ КУЛДАУН ⭐

            if is_admin_user:

                # Админы всегда могут получить карту (без кулдауна)

                pass

            elif time_passed >= COOLDOWN_SECONDS:

                # Обычная попытка (кулдаун прошёл)

                pass

            elif free_rolls > 0:

                # Используем бесплатную попытку

                use_free_roll = True

            else:

                # Нет бесплатных попыток и кулдаун не прошёл

                remaining = COOLDOWN_SECONDS - time_passed

                hours = remaining // 3600

                minutes = (remaining % 3600) // 60

                seconds = remaining % 60

                time_text = ""

                if hours > 0:

                    time_text += f"{hours} ч "

                if minutes > 0:

                    time_text += f"{minutes} мин "

                time_text += f"{seconds} сек"

                await update.message.reply_text(
                    f"⏳ До следующей карты: {time_text}\n\n"
                    f"🎲 Или бросьте кубик для бесплатной попытки!"
                )

                return

            # Собираем доступные карты

            available_cards = [
                card
                for card in data["cards"]
                if card["available"]
                and card.get("rarity")
                not in [
                    "UpgradeT1",
                    "UpgradeT2",
                    "UpgradeT3",
                    "UpgradeT4",
                    "UpgradeT5",
                    "UpgradeT6",
                    "UpgradeT7",
                ]
            ]

            if not available_cards:

                await update.message.reply_text("⏳ Ожидайте новых карточек!")

                return

            card = get_card_with_fixed_rarity(available_cards)

            if not card:

                await update.message.reply_text("⏳ Ожидайте новых карточек!")

                return

            bonus = RARITY_BONUSES.get(card["rarity"], {"cents": 0, "points": 0})

            user_data["total_points"] += bonus["points"]

            user_data["season_points"] += bonus["points"]

            user_data["cents"] += bonus["cents"]

            user_data["cards"].append(card["id"])

            # ⭐ ОБНОВЛЕНИЕ ВРЕМЕНИ И БЕСПЛАТНЫХ ПОПЫТОК ⭐

            if use_free_roll:

                user_data["free_rolls"] -= 1  # Тратим бесплатную попытку

                # Время НЕ обновляем!

            elif not is_admin_user:

                # ⭐ Админам НЕ обновляем время (чтобы кулдаун не сбрасывался) ⭐

                user_data["last_card_time"] = current_time

            asyncio.create_task(send_notification_after_delay(user_id, context)) 

            

            save_data(data)

            caption = generate_card_caption(card, user_data, count=1, show_bonus=True)

            await send_card(update, card, context, caption=caption)

        elif text == "🎮 Мини-игры":

            await mini_games(update, context)

        elif text == "🎲 Бросить кубик":

            await dice(update, context)

        elif text == "👤 Мой профиль":

            await my_profile(update, context)

        elif text == "🔨 Крафт":

            await craft(update, context)

        elif text == "📂 Мои карты":

            await show_user_cards(update, context)

        elif text == "🏆 Топ игроков":  # ← ДОБАВЬТЕ ЭТОТ БЛОК
            
            await top_players(update, context)

        elif text == "🔄 Трейд":  # ← ДОБАВЬТЕ
            
            await trade_menu(update, context)

    except (NetworkError, TimedOut) as e:

        logger.warning(f"Сетевая ошибка: {e}")

    except Exception as e:

        logger.error(f"Ошибка обработки сообщения: {e}")


# ===== АДМИН-КОМАНДЫ =====


async def add_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавление новой карточки (многострочно)."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        full_text = update.message.text
        lines = full_text.split("\n")
        
        # ⭐ НОВЫЙ ФОРМАТ: 5 строк (с фракцией) ⭐
        if len(lines) < 5:
            await update.message.reply_text(
                "ℹ️ Формат:\n"
                "/add_card\n"
                "URL\n"
                "Название\n"
                "Редкость\n"
                "Фракция (или 'нет')"
            )
            return
        
        url = lines[1].strip()
        title = lines[2].strip()
        rarity = lines[3].strip()
        faction = lines[4].strip()
        
        if rarity not in RARITY_BONUSES:
            await update.message.reply_text(
                f"⚠️ Допустимые редкости: {', '.join(RARITY_BONUSES.keys())}"
            )
            return
        
        data = load_data()
        
        # Вычисляем новый ID
        if data["cards"]:
            new_id = max(card["id"] for card in data["cards"]) + 1
        else:
            new_id = 1
        
        media_type = determine_media_type(url, rarity)
        
        new_card = {
            "id": new_id,
            "image_url": url,
            "title": title,
            "rarity": rarity,
            "faction": faction if faction.lower() != "нет" else None,  # ⭐ ФРАКЦИЯ ⭐
            "available": True,
            "media_type": media_type,
        }
        
        data["cards"].append(new_card)
        save_data(data)
        
        faction_text = f"\n⚔️ {faction}" if faction.lower() != "нет" else ""
        
        await update.message.reply_text(
            f"✅ Карточка #{new_id} добавлена!\n"
            f"🏷 {title}\n"
            f"🌟 {rarity}{faction_text}\n"
            f"📺 {'Анимация' if media_type == 'animation' else 'Фото'}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка добавления карточки: {e}")
        await update.message.reply_text("❌ Ошибка при добавлении")


async def list_cards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Список всех карточек (с разбивкой на части)."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        if not data["cards"]:
            await update.message.reply_text("📭 Нет добавленных карточек.")
            return
        
        cards_list = []
        for card in data["cards"]:
            status = "✅" if card["available"] else "❌"
            faction_text = f"⚔️ {card.get('faction', '—')}" if card.get('faction') else "⚔️ —"
            
            card_info = (
                f"{status} ID: {card['id']}\n"
                f"📺 Тип: {'Анимация' if card.get('media_type') == 'animation' else 'Фото'}\n"
                f"🏷 {card['title']}\n"
                f"🌟 {card['rarity']}\n"
                f"{faction_text}\n"  # ⭐ ДОБАВЛЯЕМ ФРАКЦИЮ ⭐
                f"🔗 {card['image_url'][:30]}...\n"
            )
            cards_list.append(card_info)
        
        # Разбиваем на сообщения по 4000 символов
        MAX_LENGTH = 4000
        current_message = "📋 Все карточки:\n"
        
        for card_info in cards_list:
            if len(current_message) + len(card_info) + 2 > MAX_LENGTH:
                await update.message.reply_text(current_message)
                current_message = "📋 Все карточки (продолжение):\n" + card_info
            else:
                current_message += card_info + "\n"
        
        if current_message.strip():
            await update.message.reply_text(current_message)
            
    except Exception as e:
        logger.error(f"Ошибка показа карточек: {e}")
        await update.message.reply_text("❌ Ошибка при получении списка")


async def toggle_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Включение/выключение карточки."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        if not context.args:

            await update.message.reply_text("ℹ️ Используйте: /toggle_card [ID]")

            return

        try:

            card_id = int(context.args[0])

        except ValueError:

            await update.message.reply_text("ℹ️ ID должен быть числом!")

            return

        for card in data["cards"]:

            if card["id"] == card_id:

                card["available"] = not card["available"]

                save_data(data)

                await update.message.reply_text(
                    f"ℹ️ Карточка #{card_id} {'включена' if card['available'] else 'выключена'}"
                )

                return

        await update.message.reply_text(f"⚠️ Карточка #{card_id} не найдена")

    except Exception as e:

        logger.error(f"Ошибка переключения карточки: {e}")

        await update.message.reply_text("❌ Ошибка при изменении")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Рассылка сообщения всем пользователям."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        if not context.args:

            await update.message.reply_text("ℹ️ Используйте: /broadcast [текст]")

            return

        message_text = " ".join(context.args)

        users = data.get("users", {})

        if not users:

            await update.message.reply_text("ℹ️ Нет пользователей для рассылки!")

            return

        status = await update.message.reply_text(
            f"📢 Рассылка для {len(users)} пользователей..."
        )

        success, failed = 0, 0

        for i, user_id in enumerate(users.keys(), 1):

            try:

                await context.bot.send_message(chat_id=user_id, text=message_text)

                success += 1

            except Exception as e:

                failed += 1

            if i % 5 == 0 or i == len(users):

                await status.edit_text(
                    f"📢 Отправлено {i}/{len(users)}\n✅ Успешно: {success} | ❌ Ошибок: {failed}"
                )

        await status.edit_text(
            f"✅ Рассылка завершена!\nВсего: {len(users)}\nУспешно: {success}\nОшибок: {failed}"
        )

    except Exception as e:

        logger.error(f"Ошибка рассылки: {e}")

        await update.message.reply_text("❌ Ошибка при рассылке")


async def reset_all_cards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сброс всех карточек у всех пользователей."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        reset_count = 0

        for user_data in data["users"].values():

            if "cards" in user_data:

                user_data["cards"] = []

                reset_count += 1

        save_data(data)

        await update.message.reply_text(
            f"✅ Сброшены карточки у {reset_count} пользователей!"
        )

    except Exception as e:

        logger.error(f"Ошибка сброса карточек: {e}")

        await update.message.reply_text("❌ Ошибка при сбросе")


async def delete_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Полное удаление карточки из системы."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        if not context.args:

            await update.message.reply_text("ℹ️ Используйте: /delete_card [ID]")

            return

        try:

            card_id = int(context.args[0])

        except ValueError:

            await update.message.reply_text("ℹ️ ID должен быть числом!")

            return

        removed_users = 0

        # Удаляем из общего списка карт

        data["cards"] = [card for card in data["cards"] if card["id"] != card_id]

        # Удаляем из коллекций пользователей

        for user_data in data["users"].values():

            if "cards" in user_data and card_id in user_data["cards"]:

                user_data["cards"] = [
                    cid for cid in user_data["cards"] if cid != card_id
                ]

                removed_users += 1

        save_data(data)

        await update.message.reply_text(
            f"✅ Карточка #{card_id} удалена!\n"
            f"Удалена у {removed_users} пользователей."
        )

    except Exception as e:

        logger.error(f"Ошибка удаления карточки: {e}")

        await update.message.reply_text("❌ Ошибка при удалении")


async def reset_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сброс карточек конкретного пользователя."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        if not context.args:

            await update.message.reply_text("ℹ️ Используйте: /reset_user [ID]")

            return

        target_user_id = context.args[0]

        if target_user_id in data["users"]:

            data["users"][target_user_id]["cards"] = []

            save_data(data)

            await update.message.reply_text(
                f"✅ Карточки пользователя {target_user_id} сброшены!"
            )

        else:

            await update.message.reply_text(
                f"ℹ️ Пользователь {target_user_id} не найден"
            )

    except Exception as e:

        logger.error(f"Ошибка сброса пользователя: {e}")

        await update.message.reply_text("❌ Ошибка при сбросе")


async def check_cards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Статистика карточек."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        available = sum(1 for card in data["cards"] if card["available"])

        await update.message.reply_text(
            f"📊 Статистика:\n"
            f"Всего карточек: {len(data['cards'])}\n"
            f"Доступно: {available}\n"
            f"Пользователей: {len(data['users'])}"
        )

    except Exception as e:

        logger.error(f"Ошибка проверки статистики: {e}")

        await update.message.reply_text("❌ Ошибка при проверке")


# ===== НОВЫЕ КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ АДМИНАМИ =====


async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список администраторов."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        admins = data.get("admins", [])

        if not admins:

            await update.message.reply_text("Список администраторов пуст.")

            return

        response = "👥 Администраторы:\n"

        for admin_id in admins:

            # Попробуем получить username из данных пользователя (если есть)

            user_info = data["users"].get(admin_id, {})

            name = user_info.get("username") or user_info.get("first_name") or admin_id

            response += f"• {admin_id} (@{name})\n"

        await update.message.reply_text(response)

    except Exception as e:

        logger.error(f"Ошибка при показе админов: {e}")

        await update.message.reply_text(
            "❌ Ошибка при получении списка администраторов"
        )


async def edit_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Редактирование параметров карты."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # Проверяем аргументы
        if not context.args or len(context.args) < 3:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/edit_card [ID] [параметр] [новое_значение]\n\n"
                "**Параметры:**\n"
                "• title - название карты\n"
                "• url - URL изображения\n"
                "• rarity - редкость (T1-T8, UpgradeT1-UpgradeT7)\n"
                "• faction - фракция (текст)\n"  # ← НОВЫЙ ПАРАМЕТР
                "• available - статус (true/false)\n\n"
                "**Примеры:**\n"
                "/edit_card 45 title Новая карта\n"
                "/edit_card 45 url https://example.com/img.jpg\n"
                "/edit_card 45 rarity T3\n"
                "/edit_card 45 faction Демоны\n"  # ← НОВЫЙ ПРИМЕР
                "/edit_card 45 available false",
                parse_mode="Markdown",
            )
            return
        
        card_id = int(context.args[0])
        param = context.args[1].lower()
        new_value = " ".join(context.args[2:])
        
        # Находим карту
        card = find_card_by_id(card_id, data["cards"])
        if not card:
            await update.message.reply_text(f"⚠️ Карта #{card_id} не найдена")
            return
        
        # Обновляем параметр
        valid_params = ["title", "url", "rarity", "faction", "available"]  # ← ДОБАВИЛИ faction
        if param not in valid_params:
            await update.message.reply_text(
                f"⚠️ Неверный параметр! Доступные: {', '.join(valid_params)}"
            )
            return
        
        # Сохраняем старое значение
        old_value = card.get(param, "не задано")
        
        # Обновляем значение
        if param == "available":
            new_value = new_value.lower() in ["true", "1", "yes", "вкл", "on"]
            card[param] = new_value
        elif param == "rarity":
            if new_value not in RARITY_BONUSES:
                await update.message.reply_text(
                    f"⚠️ Недопустимая редкость!\n"
                    f"Доступные: {', '.join(RARITY_BONUSES.keys())}"
                )
                return
            card[param] = new_value
            card["media_type"] = determine_media_type(card.get("image_url", ""), new_value)
        elif param == "url":
            card["image_url"] = new_value
            card["media_type"] = determine_media_type(new_value, card.get("rarity", ""))
        else:
            # title или faction
            card[param] = new_value
        
        save_data(data)
        
        # Формируем ответ
        response = (
            f"✅ **Карта #{card_id} обновлена!**\n"
            f"📝 Параметр: {param}\n"
            f"❌ Было: {old_value}\n"
            f"✅ Стало: {new_value}\n"
            f"🏷 {card.get('title')}\n"
            f"🌟 {card.get('rarity')}"
        )
        
        # Добавляем фракцию в ответ, если она есть
        if card.get("faction"):
            response += f"\n⚔️ {card['faction']}"
        
        response += f"\n{'✅ Включена' if card.get('available') else '❌ Выключена'}"
        
        await update.message.reply_text(response, parse_mode="Markdown")
        
    except ValueError:
        await update.message.reply_text("⚠️ ID должен быть числом!")
    except Exception as e:
        logger.error(f"Ошибка редактирования карты: {e}")
        await update.message.reply_text("❌ Ошибка при редактировании")


async def card_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает подробную информацию о карте."""
    try:
        if not context.args:
            await update.message.reply_text("ℹ️ Используйте: /card_info [ID]")
            return
        
        card_id = int(context.args[0])
        data = load_data()
        
        card = find_card_by_id(card_id, data["cards"])
        if not card:
            await update.message.reply_text(f"⚠️ Карта #{card_id} не найдена")
            return
        
        # Считаем у скольких игроков есть эта карта
        players_count = 0
        for user_data in data["users"].values():
            if card_id in user_data.get("cards", []):
                players_count += 1
        
        info_text = (
            f"📊 **Информация о карте #{card_id}**\n\n"
            f"🏷 **Название:** {card.get('title')}\n"
            f"🌟 **Редкость:** {card.get('rarity')}\n"
        )
        
        # ⭐ ДОБАВЛЯЕМ ФРАКЦИЮ ⭐
        if card.get("faction"):
            info_text += f"⚔️ **Фракция:** {card['faction']}\n"
        
        info_text += (
            f"📺 **Тип:** {'Анимация' if card.get('media_type') == 'animation' else 'Фото'}\n"
            f"{'✅ **Статус:** Включена\n' if card.get('available') else '❌ **Статус:** Выключена\n'}"
            f"🔗 **URL:** `{card.get('image_url')}`\n\n"
            f"👥 **Есть у игроков:** {players_count}\n"
        )
        
        await update.message.reply_text(info_text, parse_mode="Markdown")
        
    except ValueError:
        await update.message.reply_text("⚠️ ID должен быть числом!")
    except Exception as e:
        logger.error(f"Ошибка показа инфо карты: {e}")
        await update.message.reply_text("❌ Ошибка")


async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет нового администратора."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        if not context.args:

            await update.message.reply_text(
                "ℹ️ Используйте: /add_admin [ID пользователя]"
            )

            return

        new_admin_id = context.args[0]

        admins = data.setdefault("admins", [])

        if new_admin_id in admins:

            await update.message.reply_text(
                f"ℹ️ Пользователь {new_admin_id} уже администратор."
            )

            return

        admins.append(new_admin_id)

        save_data(data)

        await update.message.reply_text(
            f"✅ Пользователь {new_admin_id} добавлен в администраторы."
        )

    except Exception as e:

        logger.error(f"Ошибка добавления админа: {e}")

        await update.message.reply_text("❌ Ошибка при добавлении администратора")


async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет администратора."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        if not context.args:

            await update.message.reply_text(
                "ℹ️ Используйте: /remove_admin [ID пользователя]"
            )

            return

        admin_id = context.args[0]

        admins = data.get("admins", [])

        if admin_id not in admins:

            await update.message.reply_text(
                f"ℹ️ Пользователь {admin_id} не является администратором."
            )

            return

        # Нельзя удалить последнего админа (по желанию)

        if len(admins) == 1:

            await update.message.reply_text(
                "⚠️ Нельзя удалить последнего администратора!"
            )

            return

        admins.remove(admin_id)

        save_data(data)

        await update.message.reply_text(
            f"✅ Пользователь {admin_id} удалён из администраторов."
        )

    except Exception as e:

        logger.error(f"Ошибка удаления админа: {e}")

        await update.message.reply_text("❌ Ошибка при удалении администратора")


async def craft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Крафт 10 одинаковых карт в новую карту редкости Upgrade."""

    try:

        user_id = str(update.effective_user.id)

        data = load_data()

        user_data = data["users"].get(user_id)

        if not user_data or not user_data.get("cards"):

            await update.message.reply_text("❌ У вас нет карточек для крафта!")

            return

        # Считаем количество каждой карты

        card_counts = Counter(user_data["cards"])

        # Находим карты, которых 10 или больше

        craftable_cards = {
            card_id: count for card_id, count in card_counts.items() if count >= 10
        }

        if not craftable_cards:

            await update.message.reply_text(
                "❌ Нет карт для крафта!\n\n"
                "📋 Для крафта нужно 10 одинаковых карт.\n"
                "🔹 10x T1 → UpgradeT1\n"
                "🔹 10x T2 → UpgradeT2\n"
                "🔹 10x T3 → UpgradeT3\n"
                "🔹 10x T4 → UpgradeT4\n"
                "🔹 10x T5 → UpgradeT5\n"
                "🔹 10x T6 → UpgradeT6\n"
                "🔹 10x T7 → UpgradeT7\n\n"
                "Собирайте дубликаты и попробуйте снова!"
            )

            return

        # Фильтруем только карты, которые можно крафтить (T1-T7)

        craftable_by_rarity = {}

        for card_id, count in craftable_cards.items():

            card = find_card_by_id(card_id, data["cards"])

            if card and card.get("rarity") in [
                "T1",
                "T2",
                "T3",
                "T4",
                "T5",
                "T6",
                "T7",
            ]:

                craftable_by_rarity[card_id] = {
                    "count": count,
                    "rarity": card["rarity"],
                    "title": card["title"],
                }

        if not craftable_by_rarity:

            await update.message.reply_text(
                "❌ Для крафта подходят только карты редкости T1-T7!"
            )

            return

        # Если есть несколько карт для крафта — показываем выбор

        if len(craftable_by_rarity) > 0:

            keyboard = []

            for card_id, info in list(craftable_by_rarity.items())[:5]:

                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"{info['title']} ({info['count']} шт.) → Upgrade{info['rarity']}",
                            callback_data=f"craft_{card_id}",
                        )
                    ]
                )

            keyboard.append(
                [InlineKeyboardButton("❌ Отмена", callback_data="craft_cancel")]
            )

            await update.message.reply_text(
                "🔨 Выберите карту для крафта:\n\n"
                "10 карт будут удалены, вы получите 1 случайную карту улучшенной редкости",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

            return

        # Если только одна карта — крафтим сразу

        card_id = list(craftable_by_rarity.keys())[0]

        await process_craft(update, context, user_id, card_id, data, query=None)

    except Exception as e:

        logger.error(f"Ошибка крафта: {e}")

        await update.message.reply_text("❌ Произошла ошибка при крафте")


async def process_craft(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: str,
    card_id: int,
    data: Dict,
    query=None,
) -> None:
    """Обрабатывает крафт конкретной карты."""

    try:

        user_data = data["users"].get(user_id)

        # Проверяем, что у пользователя ещё есть 10+ карт

        card_counts = Counter(user_data["cards"])

        if card_counts.get(card_id, 0) < 10:

            if query:

                await query.edit_message_text("❌ Недостаточно карт для крафта!")

            else:

                await update.message.reply_text("❌ Недостаточно карт для крафта!")

            return

        # Находим информацию о карте

        card = find_card_by_id(card_id, data["cards"])

        if not card:

            if query:

                await query.edit_message_text("❌ Карта не найдена!")

            else:

                await update.message.reply_text("❌ Карта не найдена!")

            return

        # Определяем целевую редкость (T1-T7)

        source_rarity = card.get("rarity", "")

        rarity_map = {
            "T1": "UpgradeT1",
            "T2": "UpgradeT2",
            "T3": "UpgradeT3",
            "T4": "UpgradeT4",
            "T5": "UpgradeT5",
            "T6": "UpgradeT6",
            "T7": "UpgradeT7",
        }

        if source_rarity not in rarity_map:

            if query:

                await query.edit_message_text(
                    f"❌ Карты редкости {source_rarity} нельзя скрафтить!"
                )

            else:

                await update.message.reply_text(
                    f"❌ Карты редкости {source_rarity} нельзя скрафтить!"
                )

            return

        target_rarity = rarity_map[source_rarity]

        # Находим все карты целевой редкости

        upgrade_cards = [
            c
            for c in data["cards"]
            if c.get("rarity") == target_rarity and c.get("available", True)
        ]

        if not upgrade_cards:

            if query:

                await query.edit_message_text(
                    f"❌ В системе нет карт редкости {target_rarity}!\n"
                    "Попросите администратора добавить такие карты."
                )

            else:

                await update.message.reply_text(
                    f"❌ В системе нет карт редкости {target_rarity}!\n"
                    "Попросите администратора добавить такие карты."
                )

            return

        # Удаляем 10 карт из коллекции

        removed = 0

        new_cards_list = []

        for cid in user_data["cards"]:

            if cid == card_id and removed < 10:

                removed += 1

            else:

                new_cards_list.append(cid)

        user_data["cards"] = new_cards_list

        # Выбираем случайную карту улучшенной редкости

        new_card = random.choice(upgrade_cards)

        user_data["cards"].append(new_card["id"])

        # ⭐ НАЧИСЛЯЕМ НАГРАДЫ ЗА КАРТУ ⭐

        bonus = RARITY_BONUSES.get(new_card["rarity"], {"cents": 0, "points": 0})

        user_data["total_points"] += bonus["points"]

        user_data["season_points"] += bonus["points"]

        user_data["cents"] += bonus["cents"]

        # ========================================

        save_data(data)

        # Отправляем результат

        result_text = (
            f"✅ Крафт успешен!\n\n"
            f"🔨 Использовано: 10x {card['title']} ({card['rarity']})\n"
            f"🎁 Получено: {new_card['title']}\n"
            f"🪙 +{bonus['cents']} центов\n"
            f"💊 +{bonus['points']} поинтов\n\n"
        )

        if query:

            await query.edit_message_text(result_text)

            caption = generate_card_caption(
                new_card, user_data, count=1, show_bonus=False
            )

            await send_card(
                update,
                new_card,
                context,
                caption=caption,
                chat_id=query.message.chat_id,
            )

        else:

            await update.message.reply_text(result_text)

            caption = generate_card_caption(
                new_card, user_data, count=1, show_bonus=False
            )

            await send_card(update, new_card, context, caption=caption)

    except Exception as e:

        logger.error(f"Ошибка обработки крафта: {e}")

        if query:

            await query.answer("❌ Произошла ошибка", show_alert=True)

        else:

            await update.message.reply_text("❌ Произошла ошибка при крафте")


async def craft_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок крафта."""

    try:

        query = update.callback_query

        await query.answer()

        if query.data == "craft_cancel":

            await query.edit_message_text("❌ Крафт отменён")

            return

        if query.data.startswith("craft_"):

            user_id = str(query.from_user.id)

            card_id = int(query.data.split("_")[1])

            data = load_data()

            # Передаём query в process_craft вместо удаления

            await process_craft(update, context, user_id, card_id, data, query)

    except Exception as e:

        logger.error(f"Ошибка callback крафта: {e}")

        await query.answer("❌ Произошла ошибка", show_alert=True)


async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Бросок кубика для получения бесплатных попыток."""

    try:

        user_id = str(update.effective_user.id)

        data = load_data()

        user_data = data["users"].get(user_id)

        if not user_data:

            user_data = {
                "username": update.effective_user.username or "",
                "first_name": update.effective_user.first_name or "",
                "last_name": update.effective_user.last_name or "",
                "cards": [],
                "total_points": 0,
                "season_points": 0,
                "cents": 0,
                "last_card_time": 0,
                "free_rolls": 0,
                "last_dice_time": 0,
            }

            data["users"][user_id] = user_data

        # Проверка кулдауна (6 часов)

        DICE_COOLDOWN = 6 * 60 * 60

        current_time = int(time.time())

        time_passed = current_time - user_data.get("last_dice_time", 0)

        if time_passed < DICE_COOLDOWN:

            remaining = DICE_COOLDOWN - time_passed

            hours = remaining // 3600

            minutes = (remaining % 3600) // 60

            await update.message.reply_text(
                f"⏳ Следующий бросок через: {hours} ч {minutes} мин\n\n"
                f"🎲 У вас есть {user_data.get('free_rolls', 0)} бесплатных попыток"
            )

            return

        # ⭐ ОТПРАВЛЯЕМ НАСТОЯЩИЙ КУБИК TELEGRAM ⭐

        sent_dice = await context.bot.send_dice(
            chat_id=update.effective_chat.id, emoji="🎲"  # Именно кубик!
        )

        # ⭐ ПОЛУЧАЕМ РЕАЛЬНОЕ ЗНАЧЕНИЕ ИЗ КУБИКА ⭐

        dice_value = sent_dice.dice.value  # Значение от 1 до 6

        # Добавляем бесплатные попытки (ровно столько, сколько выпало)

        user_data["free_rolls"] = user_data.get("free_rolls", 0) + dice_value

        admin_list = data.get("admins", [])
        is_admin_user = user_id in admin_list
        if not is_admin_user:
        
            user_data["last_dice_time"] = current_time

        save_data(data)

        await asyncio.sleep(4)

        await update.message.reply_text(
            f"🎲 Выпало: {dice_value}!\n\n"
            f"✨ Получено бесплатных попыток: {dice_value}\n"
            f"📊 Всего бесплатных попыток: {user_data['free_rolls']}\n\n"
            f"⏳ Следующий бросок через 6 часов"
        )

    except Exception as e:

        logger.error(f"Ошибка броска кубика: {e}")

        await update.message.reply_text("❌ Произошла ошибка")


async def dice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки кубика."""

    await dice(update, context)


async def mini_games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню мини-игр."""

    try:

        keyboard = [[InlineKeyboardButton("🎰 Казино", callback_data="casino_menu")]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🎮 **Мини-игры**\n\n" "Выберите игру:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    except Exception as e:

        logger.error(f"Ошибка в mini_games: {e}")


async def casino_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню казино."""

    try:

        query = update.callback_query

        await query.answer()

        user_id = str(query.from_user.id)

        data = load_data()

        user_data = data["users"].get(user_id)

        if not user_data:

            await query.edit_message_text("❌ Вы ещё не начали игру!")

            return

        # Проверяем сброс попыток

        check_casino_reset(user_data)

        save_data(data)

        attempts = user_data.get("casino_attempts", 10)

        cents = user_data.get("cents", 0)

        keyboard = [
            [InlineKeyboardButton("🎰 Играть (2000¢)", callback_data="casino_play")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎰 **Казино**\n\n"
            f"📜 **Правила:**\n"
            f"• Стоимость игры: 2000 центов\n"
            f"• Крутите слот и получите 3 одинаковых значения\n"
            f"• При победе: 10 бесплатных попыток получения карт\n"
            f"• Попыток сегодня: {attempts}/10\n"
            f"• Сброс в 00:00 МСК\n\n"
            f"💰 Ваш баланс: {cents} центов\n"
            f"🎲 Осталось попыток: {attempts}",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    except Exception as e:

        logger.error(f"Ошибка в casino_menu: {e}")


async def casino_play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Игра в казино."""

    try:

        query = update.callback_query

        await query.answer()

        user_id = str(query.from_user.id)

        data = load_data()

        user_data = data["users"].get(user_id)

        if not user_data:

            await query.edit_message_text("❌ Вы ещё не начали игру!")

            return

        # ⭐ ПРОВЕРКА: является ли пользователь админом ⭐

        is_admin_user = is_admin(user_id, data)

        # Проверяем сброс попыток

        check_casino_reset(user_data)

        attempts = user_data.get("casino_attempts", 0)

        cents = user_data.get("cents", 0)

        # ⭐ АДМИНЫ ПРОПУСКАЮТ ПРОВЕРКИ ⭐

        if not is_admin_user:

            # Проверяем попытки

            if attempts <= 0:

                await query.edit_message_text(
                    "❌ **Лимит попыток исчерпан!**\n\n"
                    "Приходите завтра после 00:00 МСК 🕛",
                    parse_mode="Markdown",
                )

                return

            # Проверяем баланс

            if cents < 2000:

                await query.edit_message_text(
                    f"❌ **Недостаточно центов!**\n\n"
                    f"Нужно: 2000¢\n"
                    f"У вас: {cents}¢\n\n"
                    f"Собирайте карты и получайте больше наград! 💰",
                    parse_mode="Markdown",
                )

                return

            # Списываем центы и попытки

            user_data["cents"] -= 2000

            user_data["casino_attempts"] -= 1

        save_data(data)

        # ⭐ ОТПРАВЛЯЕМ СЛОТ TELEGRAM ⭐

        sent_slot = await context.bot.send_dice(
            chat_id=query.message.chat_id, emoji="🎰"
        )

        # ⭐ ПОЛУЧАЕМ ЗНАЧЕНИЕ (1-64) ⭐

        slot_value = sent_slot.dice.value

        # ⭐ ПРОВЕРЯЕМ ПОБЕДУ (только 1, 22, 43, 64) ⭐

        is_win = slot_value in [1, 22, 43, 64]

        if is_win:

            # Добавляем 10 бесплатных попыток

            await asyncio.sleep(2)

            user_data["free_rolls"] = user_data.get("free_rolls", 0) + 10

            save_data(data)

            await query.message.reply_text(
                f"🎉 **ДЖЕКПОТ!** 🎉\n\n"
                f"✨ **3 одинаковых символа!**\n"
                f"🎁 Получено: 10 бесплатных попыток\n"
                f"📊 Всего попыток: {user_data['free_rolls']}\n\n"
                f"🎲 Осталось попыток в казино: {user_data['casino_attempts']}",
                parse_mode="Markdown",
            )

        else:

            await asyncio.sleep(2)

            await query.message.reply_text(
                f"😔 Не повезло! Попробуйте ещё раз.\n\n"
                f"💰 Списано: 2000¢\n"
                f"🎲 Осталось попыток: {user_data['casino_attempts']}\n"
                f"💵 Ваш баланс: {user_data['cents']}¢",
                parse_mode="Markdown",
            )

    except Exception as e:

        logger.error(f"Ошибка в casino_play: {e}")

        await query.answer("❌ Произошла ошибка", show_alert=True)


async def casino_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    try:

        query = update.callback_query

        await query.answer()

        if query.data == "casino_menu":

            await casino_menu(update, context)

        elif query.data == "casino_play":

            await casino_play(update, context)

    except Exception as e:

        logger.error(f"Ошибка casino_callback: {e}")

        await query.answer("❌ Произошла ошибка", show_alert=True)


async def add_card_to_player(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Добавляет определённую карту определённому игроку."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        # Проверяем аргументы

        if not context.args or len(context.args) < 2:

            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n\n"
                "/add_card_to_player [ID_игрока] [ID_карты] [количество]\n\n"
                "**Примеры:**\n"
                "/add_card_to_player 881692999 45 - добавить 1 карту\n"
                "/add_card_to_player 881692999 45 5 - добавить 5 карт",
                parse_mode="Markdown",
            )

            return

        target_user_id = context.args[0]

        card_id = int(context.args[1])

        count = int(context.args[2]) if len(context.args) > 2 else 1

        # Проверяем существование игрока

        if target_user_id not in data["users"]:

            await update.message.reply_text(f"⚠️ Игрок {target_user_id} не найден!")

            return

        # Проверяем существование карты

        card = find_card_by_id(card_id, data["cards"])

        if not card:

            await update.message.reply_text(f"⚠️ Карта #{card_id} не найдена!")

            return

        # Добавляем карту(ы) в коллекцию игрока

        user_data = data["users"][target_user_id]

        if "cards" not in user_data:

            user_data["cards"] = []

        for _ in range(count):

            user_data["cards"].append(card_id)

        save_data(data)

        await update.message.reply_text(
            f"✅ **Карта добавлена!**\n\n"
            f"👤 Игрок: {target_user_id}\n"
            f"🃏 Карта: {card['title']} (#{card_id})\n"
            f"🌟 Редкость: {card['rarity']}\n"
            f"📦 Количество: {count} шт.\n\n"
            f"Всего карт у игрока: {len(user_data['cards'])}",
            parse_mode="Markdown",
        )

    except ValueError:

        await update.message.reply_text("⚠️ ID должен быть числом!")

    except Exception as e:

        logger.error(f"Ошибка добавления карты игроку: {e}")

        await update.message.reply_text("❌ Ошибка при добавлении карты")


async def add_rolls_to_player(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Добавляет определённое количество бесплатных попыток игроку."""

    try:

        data = load_data()

        if not is_admin(str(update.effective_user.id), data):

            await update.message.reply_text("🚫 Только для администратора!")

            return

        # Проверяем аргументы

        if not context.args or len(context.args) < 2:

            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n\n"
                "/add_rolls_to_player [ID_игрока] [количество]\n\n"
                "**Примеры:**\n"
                "/add_rolls_to_player 881692999 10 - добавить 10 попыток\n"
                "/add_rolls_to_player 881692999 100 - добавить 100 попыток",
                parse_mode="Markdown",
            )

            return

        target_user_id = context.args[0]

        rolls_count = int(context.args[1])

        # Проверяем существование игрока

        if target_user_id not in data["users"]:

            # Создаём нового игрока если не существует

            user_data = {
                "username": "",
                "first_name": "Admin Granted",
                "last_name": "",
                "cards": [],
                "total_points": 0,
                "season_points": 0,
                "cents": 0,
                "last_card_time": 0,
                "free_rolls": 0,
                "last_dice_time": 0,
                "casino_attempts": 10,
                "last_casino_reset": 0,
            }

            data["users"][target_user_id] = user_data

            created = True

        else:

            user_data = data["users"][target_user_id]

            created = False

        # Добавляем попытки

        old_rolls = user_data.get("free_rolls", 0)

        user_data["free_rolls"] = old_rolls + rolls_count

        save_data(data)

        await update.message.reply_text(
            f"✅ **Попытки добавлены!**\n\n"
            f"👤 Игрок: {target_user_id}\n"
            f"🎲 Добавлено: {rolls_count}\n"
            f"📊 Было: {old_rolls}\n"
            f"📈 Стало: {user_data['free_rolls']}\n\n"
            f"{'🆕 Игрок создан!' if created else ''}",
            parse_mode="Markdown",
        )

    except ValueError:

        await update.message.reply_text("⚠️ Количество должно быть числом!")

    except Exception as e:

        logger.error(f"Ошибка добавления попыток игроку: {e}")

        await update.message.reply_text("❌ Ошибка при добавлении попыток")

async def top_players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает топ-10 игроков по поинтам в сезоне."""
    try:
        data = load_data()
        users = data.get("users", {})
        
        # Сортируем пользователей по season_points
        sorted_users = sorted(
            users.items(),
            key=lambda x: x[1].get("season_points", 0),
            reverse=True
        )
        
        # Берём топ-10
        top_10 = sorted_users[:10]
        
        # Формируем сообщение
        message_text = "🏆 **Топ игроков этого сезона**\n\n"
        
        for rank, (user_id, user_data) in enumerate(top_10, 1):
            # Получаем имя из профиля Telegram
            first_name = user_data.get("first_name", "Игрок")
            last_name = user_data.get("last_name", "")
            
            # Формируем полное имя
            if last_name:
                username = f"{first_name} {last_name}"
            else:
                username = first_name
            
            points = user_data.get("season_points", 0)
            
            # Медали для топ-3
            if rank == 1:
                medal = "🥇"
            elif rank == 2:
                medal = "🥈"
            elif rank == 3:
                medal = "🥉"
            else:
                medal = f"{rank}."
            
            message_text += f"{medal} **{username}** — {points} поинтов\n"
        
        # Показываем место текущего пользователя
        current_user_id = str(update.effective_user.id)
        current_user_data = users.get(current_user_id, {})
        current_points = current_user_data.get("season_points", 0)
        
        # Находим место пользователя
        user_rank = None
        for rank, (user_id, _) in enumerate(sorted_users, 1):
            if user_id == current_user_id:
                user_rank = rank
                break
        
        # Если пользователя нет в топе
        if not user_rank:
            user_rank = len(sorted_users) + 1
        
        message_text += "\n\n" + "─" * 30 + "\n\n"
        
        if user_rank <= 10:
            message_text += f"✅ **Ваше место:** {user_rank}\n"
        else:
            message_text += f"📍 **Ваше место:** {user_rank}\n"
        
        message_text += f"💊 **Ваши поинты:** {current_points}"
        
        # УБРАНА КНОПКА ОБНОВЛЕНИЯ
        await update.message.reply_text(
            message_text,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в top_players: {e}")
        await update.message.reply_text("❌ Ошибка при загрузке топа")


async def top_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки обновления топа."""
    try:
        query = update.callback_query
        await query.answer()
        
        # Просто вызываем top_players заново
        await top_players(update, context)
        
    except Exception as e:
        logger.error(f"Ошибка в top_callback: {e}")
        await query.answer("❌ Ошибка при обновлении", show_alert=True)

async def reset_season_points(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сбрасывает поинты за сезон у конкретного игрока."""
    try:
        data = load_data()
        
        # Проверка на админа
        user_id = str(update.effective_user.id)
        if not is_admin(user_id, data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        # Проверяем аргументы
        if not context.args:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n\n"
                "/reset_season_points [ID_игрока]\n\n"
                "**Пример:**\n"
                "/reset_season_points 881692999",
                parse_mode="Markdown"
            )
            return
        
        target_user_id = context.args[0]
        
        # Проверяем существование игрока
        if target_user_id not in data["users"]:
            await update.message.reply_text(f"⚠️ Игрок {target_user_id} не найден!")
            return
        
        # Сохраняем старые поинты
        old_points = data["users"][target_user_id].get("season_points", 0)
        
        # Сбрасываем поинты
        data["users"][target_user_id]["season_points"] = 0
        
        save_data(data)
        
        # Получаем имя игрока
        player_data = data["users"][target_user_id]
        player_name = player_data.get("first_name", "Игрок")
        if player_data.get("last_name"):
            player_name += f" {player_data['last_name']}"
        
        await update.message.reply_text(
            f"✅ **Сезонные поинты сброшены!**\n\n"
            f"👤 Игрок: {player_name}\n"
            f"🆔 ID: {target_user_id}\n"
            f"📊 Было поинтов: {old_points}\n"
            f"📈 Стало поинтов: 0\n\n"
            f"⚠️ Общие поинты (total_points) не изменены.",
            parse_mode="HTML"
        )
        
        logger.info(f"Админ {user_id} сбросил сезонные поинты игроку {target_user_id} ({old_points} → 0)")
        
    except Exception as e:
        logger.error(f"Ошибка reset_season_points: {e}")
        await update.message.reply_text("❌ Ошибка при сбросе поинтов")

async def trade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Меню трейда."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data or not user_data.get("cards"):
            await update.message.reply_text("❌ У вас нет карт для трейда!")
            return
        
        keyboard = [
            [InlineKeyboardButton("1 ↔ 1", callback_data="trade_1v1")],
            [InlineKeyboardButton("❌ Отмена", callback_data="trade_cancel")],
        ]
        
        await update.message.reply_text(
            "🔄 **Трейд карт**\n\n"
            "Выберите тип обмена:\n"
            "• 1 ↔ 1 - обмен 1 карты на 1\n"
            "📝 После выбора нужно будет указать игрока и выбрать карты.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в trade_menu: {e}")
        await update.message.reply_text("❌ Ошибка при открытии меню трейда")


async def select_trade_partner(update: Update, context: ContextTypes.DEFAULT_TYPE, trade_type: str) -> None:
    """Запрос ID или @никнейма партнёра."""
    try:
        user_id = str(update.effective_user.id)
        
        # Получаем query из callback_query
        if hasattr(update, 'callback_query') and update.callback_query:
            query = update.callback_query
            await query.answer()
            message = query.message
        else:
            message = update.message
        
        # Сохраняем тип трейда во временное хранилище
        context.user_data[user_id] = {
            "trade_type": trade_type,
            "step": "select_partner"
        }
        
        await message.reply_text(
            "👤 **Введите @никнейм игрока**\n\n"
            "Пример:\n"
            "• @username\n\n",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка select_trade_partner: {e}")
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.answer("❌ Ошибка при выборе партнёра", show_alert=True)
        else:
            await update.message.reply_text("❌ Ошибка при выборе партнёра")


async def process_partner_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка выбора партнёра."""
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text.strip()
        
        # Проверяем, есть ли активный трейд
        if user_id not in context.user_data:
            return
        
        trade_info = context.user_data[user_id]
        if trade_info.get("step") != "select_partner":
            return
        
        
        # Определяем партнёра
        if text.startswith("@"):
            # Поиск по username
            partner_id = None
            data = load_data()
            for uid, udata in data["users"].items():
                if udata.get("username") == text[1:]:
                    partner_id = uid
                    break
        else:
            if user_id in context.user_data:
                del context.user_data[user_id]
            await query.edit_message_text("Неправильно введён @никнейм_игрока, начните трейд заново")
            return
        
        # Проверяем существование партнёра
        data = load_data()
        if partner_id not in data["users"]:
            await update.message.reply_text("⚠️ Игрок не найден!")
            return
        
        if partner_id == user_id:
            await update.message.reply_text("⚠️ Нельзя трейдиться с самим собой!")
            return
        
        # Сохраняем партнёра
        trade_info["partner_id"] = partner_id
        trade_info["step"] = "select_cards"
        
        # Получаем количество карт для трейда
        trade_type = trade_info["trade_type"]  # "1v1", "2v2", "3v3"
        cards_count = int(trade_type.split("v")[0])
        trade_info["cards_count"] = cards_count
        trade_info["selected_cards"] = []
        
        await update.message.reply_text(
            f"✅ Партнёр: {partner_id}\n\n"
            f"🃏 Выберите {cards_count} карт для обмена.\n\n"
            "Используйте кнопки для навигации:\n"
            "• [<] [>] - листать карты\n"
            "• [✅ Выбрать] - добавить карту\n"
            "• [➡️ Далее] - завершить выбор",
            parse_mode="Markdown"
        )
        
        # Показываем первую карту
        user_data = data["users"][user_id]
        user_card_ids = user_data.get("cards", [])
        
        if len(user_card_ids) < cards_count:
            await update.message.reply_text("❌ Недостаточно карт для трейда!")
            del context.user_data[user_id]
            return
        
        trade_info["user_card_ids"] = user_card_ids
        trade_info["current_index"] = 0
        
        card = find_card_by_id(user_card_ids[0], data["cards"])
        if card:
            caption = f"{card['title']}\nРедкость: {card['rarity']}\n\n0/{cards_count} выбрано"
            keyboard = [
                [
                    InlineKeyboardButton("<", callback_data="trade_prev_0"),
                    InlineKeyboardButton("✅ Выбрать", callback_data="trade_select_0"),
                    InlineKeyboardButton(">", callback_data="trade_next_0"),
                ],
                [InlineKeyboardButton("➡️ Далее", callback_data="trade_finish_select")],
            ]
            await update.message.reply_photo(
                photo=card["image_url"],
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
    except Exception as e:
        logger.error(f"Ошибка process_partner_selection: {e}")
        await update.message.reply_text("❌ Ошибка при выборе партнёра")


async def trade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок трейда."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        
        # ⭐ ОБРАБОТКА ВЫБОРА ТИПА ТРЕЙДА
        if query.data in ["trade_1v1", "trade_2v2", "trade_3v3"]:
            trade_type = query.data.split("_")[1]  # "1v1", "2v2", "3v3"
            await select_trade_partner(update, context, trade_type)
            return
        
        # Отмена
        if query.data == "trade_cancel":
            if user_id in context.user_data:
                del context.user_data[user_id]
            await query.edit_message_text("❌ Трейд отменён")
            return
        
        # Проверяем сессию для остальных кнопок
        if user_id not in context.user_data:
            await query.edit_message_text("❌ Сессия трейда истекла!")
            return
        
        trade_info = context.user_data[user_id]
        data = load_data()
        
        # Навигация
        if query.data.startswith("trade_prev_") or query.data.startswith("trade_next_"):
            action = "prev" if "prev" in query.data else "next"
            current_index = trade_info.get("current_index", 0)
            user_card_ids = trade_info.get("user_card_ids", [])
            
            if not user_card_ids:
                await query.answer("❌ Карты не найдены!", show_alert=True)
                return
            
            if action == "prev":
                current_index = (current_index - 1) % len(user_card_ids)
            else:
                current_index = (current_index + 1) % len(user_card_ids)
            
            trade_info["current_index"] = current_index
            
            card = find_card_by_id(user_card_ids[current_index], data["cards"])
            if card:
                selected_count = len(trade_info.get("selected_cards", []))
                cards_count = trade_info.get("cards_count", 1)
                
                # ⭐ СЧИТАЕМ КОЛИЧЕСТВО КАРТЫ В КОЛЛЕКЦИИ ⭐
                card_counts = Counter(user_card_ids)
                card_in_collection = card_counts.get(card["id"], 1)
                
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"📦 В коллекции: {card_in_collection} шт.\n\n"
                    f"{selected_count}/{cards_count} выбрано"
                )
                
                is_selected = current_index in trade_info.get("selected_cards", [])
                select_text = "❌ Убрать" if is_selected else "✅ Выбрать"
                
                keyboard = [
                    [
                        InlineKeyboardButton("<", callback_data=f"trade_prev_{current_index}"),
                        InlineKeyboardButton(select_text, callback_data=f"trade_select_{current_index}"),
                        InlineKeyboardButton(">", callback_data=f"trade_next_{current_index}"),
                    ],
                    [InlineKeyboardButton("➡️ Далее", callback_data="trade_finish_select")],
                ]
                
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Выбор карты
        elif query.data.startswith("trade_select_"):
            card_index = int(query.data.split("_")[-1])
            selected_cards = trade_info.get("selected_cards", [])
            cards_count = trade_info.get("cards_count", 1)
            user_card_ids = trade_info.get("user_card_ids", [])
            
            if card_index in selected_cards:
                selected_cards.remove(card_index)
            else:
                if len(selected_cards) >= cards_count:
                    await query.answer("❌ Максимум карт выбрано!", show_alert=True)
                    return
                selected_cards.append(card_index)
            
            trade_info["selected_cards"] = selected_cards
            
            # Обновляем отображение
            current_index = trade_info.get("current_index", 0)
            card = find_card_by_id(user_card_ids[current_index], data["cards"])
            if card:
                # ⭐ СЧИТАЕМ КОЛИЧЕСТВО КАРТЫ В КОЛЛЕКЦИИ ⭐
                card_counts = Counter(user_card_ids)
                card_in_collection = card_counts.get(card["id"], 1)
                
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"📦 В коллекции: {card_in_collection} шт.\n\n"
                    f"{len(selected_cards)}/{cards_count} выбрано"
                )
                
                is_selected = current_index in selected_cards
                select_text = "❌ Убрать" if is_selected else "✅ Выбрать"
                
                keyboard = [
                    [
                        InlineKeyboardButton("<", callback_data=f"trade_prev_{current_index}"),
                        InlineKeyboardButton(select_text, callback_data=f"trade_select_{current_index}"),
                        InlineKeyboardButton(">", callback_data=f"trade_next_{current_index}"),
                    ],
                    [InlineKeyboardButton("➡️ Далее", callback_data="trade_finish_select")],
                ]
                
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Завершение выбора
        elif query.data == "trade_finish_select":
            selected_cards = trade_info.get("selected_cards", [])
            cards_count = trade_info.get("cards_count", 1)
            user_card_ids = trade_info.get("user_card_ids", [])
            
            if len(selected_cards) != cards_count:
                await query.answer(f"❌ Выберите ровно {cards_count} карт!", show_alert=True)
                return
            
            # Переходим к подтверждению
            trade_info["step"] = "confirm"
            
            # Формируем список карт для отображения
            selected_card_ids = [user_card_ids[i] for i in selected_cards]
            trade_info["selected_card_ids"] = selected_card_ids
            
            # Удаляем сообщение с картами и отправляем текстовое
            try:
                await query.message.delete()
            except:
                pass
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    f"✅ Вы выбрали {cards_count} карт(ы)\n\n"
                    f"👤 Партнёр: {trade_info['partner_id']}\n\n"
                    f"📩 Отправляю запрос на обмен..."
                ),
                parse_mode="Markdown"
            )
            
            # В конце функции trade_callback, где сохраняем трейд для партнёра:

            # Отправляем запрос партнёру
            partner_id = trade_info["partner_id"]

            # ⭐ СОХРАНЯЕМ ТРЕЙД В ФАЙЛ (вместо context.user_data) ⭐
            data = load_data()
            data["active_trades"][partner_id] = {
                "from_user": user_id,
                "cards_offered": selected_card_ids,
                "trade_type": trade_info["trade_type"],
                "timestamp": int(time.time())
            }
            save_data(data)

            logger.info(f"Трейд сохранён в файл: {user_id} → {partner_id}")

            context.user_data[user_id] = {
                "step": "waiting_for_receiver_response",
                "trade_partner": partner_id,
                "selected_card_ids": selected_card_ids,  # Карты, которые отправитель предлагает
            }

            # Уведомляем партнёра
            try:
                # Получаем имя отправителя
                sender_data = data["users"].get(user_id, {})
                sender_name = sender_data.get("first_name", "Игрок")
                if sender_data.get("last_name"):
                    sender_name += f" {sender_data['last_name']}"
                if sender_data.get("username"):
                    sender_name = f"@{sender_data['username']}"
    
                # Получаем информацию о картах
                cards_info = []
                for card_id in selected_card_ids:
                    card = find_card_by_id(card_id, data["cards"])
                    if card:
                        cards_info.append(f"• {card['title']} ({card['rarity']})")
    
                cards_text = "\n".join(cards_info) if cards_info else "Нет карт"
    
                # ⭐ ДОБАВЛЯЕМ ИНЛАЙН-КНОПКИ ⭐
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Принять", callback_data=f"trade_accept_btn_{user_id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"trade_decline_btn_{user_id}"),
                    ]
                ]
    
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=(
                        f"🔄 **Вам предложили обмен!**\n\n"
                        f"👤 От: {sender_name}\n"
                        f"🃏 Карт в обмене: {cards_count}\n\n"
                        f"📋 **Карты отправителя:**\n"
                        f"{cards_text}\n\n"
                        f"Нажмите кнопку для действия:"
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            except Exception as notify_error:
                logger.error(f"Не удалось уведомить партнёра: {notify_error}")
                await query.message.reply_text("⚠️ Не удалось уведомить партнёра")
    
    except Exception as e:
        logger.error(f"Ошибка trade_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def trade_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок Принять/Отклонить трейд."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        
        # ⭐ ЧИТАЕМ ТРЕЙД ИЗ ФАЙЛА ⭐
        data = load_data()
        
        if user_id not in data.get("active_trades", {}):
            logger.warning(f"Трейд не найден для пользователя {user_id}")
            await query.edit_message_text("❌ Трейд не найден или истёк!")
            return
        
        trade_info = data["active_trades"][user_id]
        from_user = trade_info["from_user"]
        cards_offered = trade_info["cards_offered"]
        
        logger.info(f"trade_button_callback: {user_id} принимает трейд от {from_user}")
        
        # Принятие трейда
        if query.data.startswith("trade_accept_btn_"):
            # Проверяем, что отправитель существует
            if from_user not in data["users"]:
                del data["active_trades"][user_id]
                save_data(data)
                await query.edit_message_text("❌ Игрок, который отправил трейд, больше не существует!")
                return
            
            # Проверяем, что карты ещё существуют у отправителя
            if not cards_offered:
                del data["active_trades"][user_id]
                save_data(data)
                await query.edit_message_text("❌ Карты для обмена больше не доступны!")
                return
            
            # Получаем имя отправителя
            sender_data = data["users"].get(from_user, {})
            sender_name = sender_data.get("first_name", "Игрок")
            if sender_data.get("last_name"):
                sender_name += f" {sender_data['last_name']}"
            
            # ⭐ СОХРАНЯЕМ ВРЕМЕННО В context.user_data ДЛЯ НАВИГАЦИИ ⭐
            context.user_data[user_id] = {
                "step": "view_offered_cards",
                "trade_partner": from_user,
                "received_cards": cards_offered,
                "current_offer_index": 0
            }
            
            # Удаляем трейд из активных (чтобы не принять дважды)
            del data["active_trades"][user_id]
            save_data(data)
            
            await query.edit_message_text(
                f"✅ **Запрос принят от {sender_name}**\n\n"
                f"🃏 Карт в обмене: {len(cards_offered)}\n\n"
                f"📋 **Просмотрите карты ниже:**\n"
                f"Используйте [<] [>] для навигации",
                parse_mode="Markdown"
            )
            
            # Показываем первую карту
            card = find_card_by_id(cards_offered[0], data["cards"])
            if card:
                card_counts = Counter(cards_offered)
                card_in_offer = card_counts.get(card["id"], 1)
                
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"📦 В предложении: {card_in_offer} шт.\n\n"
                    f"1/{len(cards_offered)}"
                )
                
                keyboard = []
                nav_buttons = []
                
                if len(cards_offered) > 1:
                    nav_buttons.append(
                        InlineKeyboardButton("<", callback_data="trade_offer_prev_0")
                    )
                
                nav_buttons.append(
                    InlineKeyboardButton(
                        f"1/{len(cards_offered)}",
                        callback_data="trade_offer_info"
                    )
                )
                
                if len(cards_offered) > 1:
                    nav_buttons.append(
                        InlineKeyboardButton(">", callback_data="trade_offer_next_0")
                    )
                
                keyboard.append(nav_buttons)
                keyboard.append([
                    InlineKeyboardButton("✅ Принять обмен", callback_data="trade_offer_accept"),
                    InlineKeyboardButton("❌ Отклонить", callback_data="trade_offer_decline"),
                ])
                
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=card["image_url"],
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        
        # Отклонение трейда
        elif query.data.startswith("trade_decline_btn_"):
            del data["active_trades"][user_id]
            save_data(data)
            
            await query.edit_message_text("❌ Трейд отклонён")
            
            # Уведомляем отправителя
            try:
                await context.bot.send_message(
                    chat_id=from_user,
                    text=f"❌ Игрок отклонил ваш запрос на обмен."
                )
            except:
                pass
        
    except Exception as e:
        logger.error(f"Ошибка trade_button_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def trade_accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Принятие трейда с просмотром карт."""
    try:
        user_id = str(update.effective_user.id)
        data = load_data()
        
        # Проверяем, существует ли пользователь в базе
        if user_id not in data["users"]:
            await update.message.reply_text("❌ Вы не зарегистрированы в системе!")
            return
        
        # Проверяем, есть ли входящий трейд
        if user_id not in context.user_data:
            await update.message.reply_text("❌ У вас нет активных запросов на трейд!")
            return
        
        if "incoming_trade" not in context.user_data[user_id]:
            await update.message.reply_text("❌ У вас нет активных запросов на трейд!")
            return
        
        trade_info = context.user_data[user_id]["incoming_trade"]
        from_user = trade_info["from_user"]
        cards_offered = trade_info["cards_offered"]
        
        # Проверяем, что отправитель существует
        if from_user not in data["users"]:
            await update.message.reply_text("❌ Игрок, который отправил трейд, больше не существует!")
            del context.user_data[user_id]["incoming_trade"]
            return
        
        # Получаем имя отправителя
        sender_data = data["users"].get(from_user, {})
        sender_name = sender_data.get("first_name", "Игрок")
        if sender_data.get("last_name"):
            sender_name += f" {sender_data['last_name']}"
        
        # Проверяем, что карты ещё существуют у отправителя
        if not cards_offered:
            await update.message.reply_text("❌ Карты для обмена больше не доступны!")
            del context.user_data[user_id]["incoming_trade"]
            return
        
        # Сохраняем информацию для просмотра карт
        context.user_data[user_id]["step"] = "view_offered_cards"
        context.user_data[user_id]["trade_partner"] = from_user
        context.user_data[user_id]["received_cards"] = cards_offered
        context.user_data[user_id]["current_offer_index"] = 0
        
        await update.message.reply_text(
            f"✅ **Запрос на обмен от {sender_name}**\n\n"
            f"🃏 Карт в обмене: {len(cards_offered)}\n\n"
            f"📋 **Просмотрите карты ниже:**\n"
            f"Используйте [<] [>] для навигации\n"
            f"Когда будете готовы, нажмите [✅ Принять обмен]",
            parse_mode="Markdown"
        )
        
        # Показываем первую карту
        card = find_card_by_id(cards_offered[0], data["cards"])
        if card:
            card_counts = Counter(cards_offered)
            card_in_offer = card_counts.get(card["id"], 1)
            
            caption = (
                f"{card['title']}\n"
                f"Редкость: {card['rarity']}\n"
                f"📦 В предложении: {card_in_offer} шт.\n\n"
                f"1/{len(cards_offered)}"
            )
            
            keyboard = []
            nav_buttons = []
            
            if len(cards_offered) > 1:
                nav_buttons.append(
                    InlineKeyboardButton("<", callback_data="trade_offer_prev_0")
                )
            
            nav_buttons.append(
                InlineKeyboardButton(
                    f"1/{len(cards_offered)}",
                    callback_data="trade_offer_info"
                )
            )
            
            if len(cards_offered) > 1:
                nav_buttons.append(
                    InlineKeyboardButton(">", callback_data="trade_offer_next_0")
                )
            
            keyboard.append(nav_buttons)
            keyboard.append([
                InlineKeyboardButton("✅ Принять обмен", callback_data="trade_accept_confirm"),
                InlineKeyboardButton("❌ Отклонить", callback_data="trade_decline_from_view"),
            ])
            
            await update.message.reply_photo(
                photo=card["image_url"],
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text("❌ Ошибка при загрузке карты!")
        
    except KeyError as e:
        logger.error(f"KeyError в trade_accept: {e}")
        await update.message.reply_text(f"❌ Ошибка данных: {e}")
    except Exception as e:
        logger.error(f"Ошибка trade_accept: {e}")
        await update.message.reply_text("❌ Ошибка при принятии трейда")
        
async def trade_decline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отклонение трейда."""
    try:
        user_id = str(update.effective_user.id)
        
        if user_id not in context.user_data or "incoming_trade" not in context.user_data[user_id]:
            await update.message.reply_text("❌ У вас нет активных запросов на трейд!")
            return
        
        trade_info = context.user_data[user_id]["incoming_trade"]
        from_user = trade_info["from_user"]
        
        del context.user_data[user_id]["incoming_trade"]
        
        await update.message.reply_text("❌ Трейд отклонён")
        
        # Уведомляем отправителя
        try:
            await context.bot.send_message(
                chat_id=from_user,
                text=f"❌ Игрок отклонил ваш запрос на обмен."
            )
        except:
            pass
        
    except Exception as e:
        logger.error(f"Ошибка trade_decline: {e}")
        await update.message.reply_text("❌ Ошибка при отклонении трейда")


async def trade_offer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок просмотра карт предложения."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        
        # Читаем из context.user_data (туда сохранили после принятия)
        if user_id not in context.user_data:
            await query.edit_message_text("❌ Сессия трейда истекла!")
            return
        
        trade_info = context.user_data[user_id]
        if trade_info.get("step") != "view_offered_cards":
            return
        
        cards_offered = trade_info.get("received_cards", [])
        if not cards_offered:
            await query.answer("❌ Карты не найдены!", show_alert=True)
            return
        
        # Навигация
        if query.data.startswith("trade_offer_prev_") or query.data.startswith("trade_offer_next_"):
            action = "prev" if "prev" in query.data else "next"
            current_index = trade_info.get("current_offer_index", 0)
            
            if action == "prev":
                current_index = (current_index - 1) % len(cards_offered)
            else:
                current_index = (current_index + 1) % len(cards_offered)
            
            trade_info["current_offer_index"] = current_index
            
            card = find_card_by_id(cards_offered[current_index], data["cards"])
            if card:
                card_counts = Counter(cards_offered)
                card_in_offer = card_counts.get(card["id"], 1)
                
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"📦 В предложении: {card_in_offer} шт.\n\n"
                    f"{current_index + 1}/{len(cards_offered)}"
                )
                
                keyboard = []
                nav_buttons = []
                
                if len(cards_offered) > 1:
                    nav_buttons.append(
                        InlineKeyboardButton("<", callback_data=f"trade_offer_prev_{current_index}")
                    )
                
                nav_buttons.append(
                    InlineKeyboardButton(
                        f"{current_index + 1}/{len(cards_offered)}",
                        callback_data="trade_offer_info"
                    )
                )
                
                if len(cards_offered) > 1:
                    nav_buttons.append(
                        InlineKeyboardButton(">", callback_data=f"trade_offer_next_{current_index}")
                    )
                
                keyboard.append(nav_buttons)
                keyboard.append([
                    InlineKeyboardButton("✅ Принять обмен", callback_data="trade_accept_confirm"),
                    InlineKeyboardButton("❌ Отклонить", callback_data="trade_decline_from_view"),
                ])
                
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Принятие обмена
        elif query.data == "trade_offer_accept":
            # Переходим к выбору своих карт
            context.user_data[user_id]["step"] = "select_return_cards"
            from_user = trade_info.get("trade_partner")
            cards_count = len(cards_offered)
            
            await query.message.reply_text(
                f"✅ Запрос принят!\n\n"
                f"🃏 Теперь выберите {cards_count} карт для обмена\n\n"
                "Используйте кнопки для выбора...",
                parse_mode="Markdown"
            )
            
            # Показываем карты пользователя для выбора
            user_data = data["users"][user_id]
            user_card_ids = user_data.get("cards", [])
            
            if len(user_card_ids) < cards_count:
                await query.message.reply_text(
                    f"❌ Недостаточно карт для трейда!\n"
                    f"У вас: {len(user_card_ids)} карт, нужно: {cards_count}"
                )
                if "incoming_trade" in context.user_data.get(user_id, {}):
                    del context.user_data[user_id]["incoming_trade"]
                return
            
            context.user_data[user_id]["user_card_ids"] = user_card_ids
            context.user_data[user_id]["cards_count"] = cards_count
            context.user_data[user_id]["selected_cards"] = []
            context.user_data[user_id]["current_index"] = 0
            
            # Показываем первую карту
            if not user_card_ids:
                await query.message.reply_text("❌ У вас нет карт!")
                return
            
            card = find_card_by_id(user_card_ids[0], data["cards"])
            if card:
                caption = f"{card['title']}\nРедкость: {card['rarity']}\n\n0/{cards_count} выбрано"
                keyboard = [
                    [
                        InlineKeyboardButton("<", callback_data="trade_return_prev_0"),
                        InlineKeyboardButton("✅ Выбрать", callback_data="trade_return_select_0"),
                        InlineKeyboardButton(">", callback_data="trade_return_next_0"),
                    ],
                    [InlineKeyboardButton("➡️ Завершить обмен", callback_data="trade_return_finish")],
                ]
                await query.message.reply_photo(
                    photo=card["image_url"],
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        
        # Отклонение обмена
        elif query.data == "trade_offer_decline":
            if "incoming_trade" in context.user_data.get(user_id, {}):
                trade_info = context.user_data[user_id]["incoming_trade"]
                from_user = trade_info["from_user"]
                
                del context.user_data[user_id]["incoming_trade"]
                
                await query.edit_message_text("❌ Трейд отклонён")
                
                # Уведомляем отправителя
                try:
                    await context.bot.send_message(
                        chat_id=from_user,
                        text=f"❌ Игрок отклонил ваш запрос на обмен."
                    )
                except:
                    pass
        
    except Exception as e:
        logger.error(f"Ошибка trade_offer_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def trade_return_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопок выбора карт для ответного трейда."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)  # Это ПОЛУЧАТЕЛЬ (Игрок Б)
        
        if user_id not in context.user_data:
            await query.edit_message_text("❌ Сессия трейда истекла!")
            return
        
        trade_info = context.user_data[user_id]
        if trade_info.get("step") != "select_return_cards":
            return
        
        data = load_data()
        user_card_ids = trade_info.get("user_card_ids", [])
        
        # Навигация
        if query.data.startswith("trade_return_prev_") or query.data.startswith("trade_return_next_"):
            action = "prev" if "prev" in query.data else "next"
            current_index = trade_info.get("current_index", 0)
            
            if not user_card_ids:
                await query.answer("❌ Карты не найдены!", show_alert=True)
                return
            
            if action == "prev":
                current_index = (current_index - 1) % len(user_card_ids)
            else:
                current_index = (current_index + 1) % len(user_card_ids)
            
            trade_info["current_index"] = current_index
            
            card = find_card_by_id(user_card_ids[current_index], data["cards"])
            if card:
                selected_count = len(trade_info.get("selected_cards", []))
                cards_count = trade_info.get("cards_count", 1)
                
                card_counts = Counter(user_card_ids)
                card_in_collection = card_counts.get(card["id"], 1)
                
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"📦 В коллекции: {card_in_collection} шт.\n\n"
                    f"{selected_count}/{cards_count} выбрано"
                )
                
                is_selected = current_index in trade_info.get("selected_cards", [])
                select_text = "❌ Убрать" if is_selected else "✅ Выбрать"
                
                keyboard = [
                    [
                        InlineKeyboardButton("<", callback_data=f"trade_return_prev_{current_index}"),
                        InlineKeyboardButton(select_text, callback_data=f"trade_return_select_{current_index}"),
                        InlineKeyboardButton(">", callback_data=f"trade_return_next_{current_index}"),
                    ],
                    [InlineKeyboardButton("➡️ Завершить обмен", callback_data="trade_return_finish")],
                ]
                
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # Выбор карты
        elif query.data.startswith("trade_return_select_"):
            card_index = int(query.data.split("_")[-1])
            selected_cards = trade_info.get("selected_cards", [])
            cards_count = trade_info.get("cards_count", 1)
            
            if card_index in selected_cards:
                selected_cards.remove(card_index)
            else:
                if len(selected_cards) >= cards_count:
                    await query.answer("❌ Максимум карт выбрано!", show_alert=True)
                    return
                selected_cards.append(card_index)
            
            trade_info["selected_cards"] = selected_cards
            
            current_index = trade_info.get("current_index", 0)
            card = find_card_by_id(user_card_ids[current_index], data["cards"])
            if card:
                card_counts = Counter(user_card_ids)
                card_in_collection = card_counts.get(card["id"], 1)
                
                caption = (
                    f"{card['title']}\n"
                    f"Редкость: {card['rarity']}\n"
                    f"📦 В коллекции: {card_in_collection} шт.\n\n"
                    f"{len(selected_cards)}/{cards_count} выбрано"
                )
                
                is_selected = current_index in selected_cards
                select_text = "❌ Убрать" if is_selected else "✅ Выбрать"
                
                keyboard = [
                    [
                        InlineKeyboardButton("<", callback_data=f"trade_return_prev_{current_index}"),
                        InlineKeyboardButton(select_text, callback_data=f"trade_return_select_{current_index}"),
                        InlineKeyboardButton(">", callback_data=f"trade_return_next_{current_index}"),
                    ],
                    [InlineKeyboardButton("➡️ Завершить обмен", callback_data="trade_return_finish")],
                ]
                
                media = InputMediaPhoto(media=card["image_url"], caption=caption)
                await query.edit_message_media(media=media, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # ⭐ ЗАВЕРШЕНИЕ ВЫБОРА КАРТ ⭐
        elif query.data == "trade_return_finish":
            selected_cards = trade_info.get("selected_cards", [])
            cards_count = trade_info.get("cards_count", 1)
            
            if len(selected_cards) != cards_count:
                await query.answer(f"❌ Выберите ровно {cards_count} карт!", show_alert=True)
                return
            
            # Получаем выбранные карты
            selected_card_ids = [user_card_ids[i] for i in selected_cards]
            received_cards = trade_info.get("received_cards", [])  # Карты от отправителя
            partner_id = trade_info.get("trade_partner")  # ID отправителя (Игрок А)
            
                # ⭐ СОХРАНЯЕМ В ФАЙЛ ВМЕСТО context.user_data ⭐
            data = load_data()
            data["active_trades"][partner_id] = {
                "from_user": partner_id,
                "receiver_id": user_id,
                "sender_cards": received_cards,  # Карты отправителя
                "receiver_cards": selected_card_ids,  # Карты получателя
                "step": "waiting_sender_confirm",
                "timestamp": int(time.time())
            }
            save_data(data)

            # Отправляем уведомление отправителю (Игрок А)
            try:
                sender_data = data["users"].get(partner_id, {})
                sender_name = sender_data.get("first_name", "Игрок")
                if sender_data.get("last_name"):
                    sender_name += f" {sender_data['last_name']}"
                
                # Информация о картах получателя
                return_cards_info = []
                for card_id in selected_card_ids:
                    card = find_card_by_id(card_id, data["cards"])
                    if card:
                        return_cards_info.append(f"• {card['title']} ({card['rarity']})")
        
                return_cards_text = "\n".join(return_cards_info) if return_cards_info else "Нет карт"
        
                # Информация о картах отправителя (что он получит)
                offered_cards_info = []
                for card_id in received_cards:
                    card = find_card_by_id(card_id, data["cards"])
                    if card:
                        offered_cards_info.append(f"• {card['title']} ({card['rarity']})")
        
                offered_cards_text = "\n".join(offered_cards_info) if offered_cards_info else "Нет карт"
                
                # Инлайн-кнопки для подтверждения
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Подтвердить обмен", callback_data=f"trade_final_confirm_{user_id}"),
                        InlineKeyboardButton("❌ Отменить", callback_data=f"trade_final_decline_{user_id}"),
                    ]
                ]
                
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=(
                        f"🔄 **Игрок готов к обмену!**\n\n"
                        f"👤 {sender_name} предлагает:\n"
                        f"{return_cards_text}\n\n"
                        f"📋 **Ваше предложение:**\n"
                        f"{offered_cards_text}\n\n"
                        f"Нажмите кнопку для подтверждения:"
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
                
                # ⭐ ИСПРАВЛЕНИЕ: удаляем фото и отправляем текстовое сообщение ⭐
                try:
                    await query.message.delete()
                except:
                    pass
                await query.message.reply_text(
                    "✅ Ваш ответ отправлен!\n\n"
                    "⏳ Ожидайте подтверждения от отправителя..."
                )
                
            except Exception as notify_error:
                logger.error(f"Не удалось уведомить отправителя: {notify_error}")
                await query.answer("❌ Ошибка при отправке подтверждения", show_alert=True)
        
    except Exception as e:
        logger.error(f"Ошибка trade_return_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)


async def trade_final_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик финального подтверждения трейда."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)  # Это ОТПРАВИТЕЛЬ (Игрок А)
        data = load_data()
        
        # ⭐ ЧИТАЕМ ИЗ ФАЙЛА ВМЕСТО context.user_data ⭐
        if user_id not in data.get("active_trades", {}):
            await query.edit_message_text("❌ Трейд не найден или истёк!")
            return
        
        trade_info = data["active_trades"][user_id]
        
        # Проверяем шаг
        if trade_info.get("step") != "waiting_sender_confirm":
            await query.edit_message_text("❌ Трейд не ожидает подтверждения!")
            return
        
        partner_id = trade_info.get("receiver_id") or trade_info.get("from_user")  # ID получателя (Игрок Б)
        received_cards = trade_info.get("sender_cards", [])  # Карты, которые отправитель предлагает
        selected_return_cards = trade_info.get("receiver_cards", [])  # Карты, которые выбрал получатель
        
        # Подтверждение обмена
        if query.data.startswith("trade_final_confirm_"):
            if not selected_return_cards:
                await query.edit_message_text("❌ Ошибка: карты партнёра не найдены!")
                return
            
            # Выполняем обмен
            user_data = data["users"][user_id]
            partner_data = data["users"][partner_id]
            
            # Удаляем карты у отправителя
            for card_id in received_cards:
                if card_id in user_data["cards"]:
                    user_data["cards"].remove(card_id)
            
            # Добавляем карты от получателя отправителю
            user_data["cards"].extend(selected_return_cards)
            
            # Удаляем карты у получателя
            for card_id in selected_return_cards:
                if card_id in partner_data["cards"]:
                    partner_data["cards"].remove(card_id)
            
            # Добавляем карты от отправителя получателю
            partner_data["cards"].extend(received_cards)
            
            save_data(data)
            
            # Очищаем трейд
            del data["active_trades"][user_id]
            save_data(data)
            
            # Очищаем context.user_data
            if user_id in context.user_data:
                del context.user_data[user_id]
            if partner_id in context.user_data:
                del context.user_data[partner_id]
            
            await query.edit_message_text(
                "✅ **Обмен завершён!**\n\n"
                f"🃏 Вы отдали: {len(received_cards)} карт\n"
                f"🃏 Вы получили: {len(selected_return_cards)} карт",
                parse_mode="Markdown"
            )
            
            # Уведомляем получателя
            try:
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=(
                        "✅ **Обмен завершён!**\n\n"
                        f"🃏 Вы отдали: {len(selected_return_cards)} карт\n"
                        f"🃏 Вы получили: {len(received_cards)} карт"
                    ),
                    parse_mode="Markdown"
                )
            except:
                pass
        
        # Отмена обмена
        elif query.data.startswith("trade_final_decline_"):
            # Очищаем трейд
            del data["active_trades"][user_id]
            save_data(data)
            
            # Очищаем context.user_data
            if user_id in context.user_data:
                del context.user_data[user_id]
            if partner_id in context.user_data:
                del context.user_data[partner_id]
            
            await query.edit_message_text("❌ Обмен отменён")
            
            # Уведомляем получателя
            try:
                await context.bot.send_message(
                    chat_id=partner_id,
                    text="❌ Отправитель отменил обмен."
                )
            except:
                pass
        
    except Exception as e:
        logger.error(f"Ошибка trade_final_callback: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def achievements_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Меню достижений."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data:
            await query.edit_message_text("❌ Вы ещё не начали игру!")
            return
        
        # Получаем карты пользователя
        user_card_ids = user_data.get("cards", [])
        claimed_achievements = user_data.get("claimed_achievements", [])
        
        # Считаем карты по фракциям
        faction_cards = {}
        for card_id in user_card_ids:
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("faction"):
                faction = card["faction"]
                if faction not in faction_cards:
                    faction_cards[faction] = set()
                faction_cards[faction].add(card_id)
        
        # Список фракций
        factions = [
            "Замок", "Оплот", "Башня", "Инферно",
            "Некрополис", "Темница", "Цитадель", "Крепость", "Сопряжение"
        ]
        
        # Создаём клавиатуру
        keyboard = []
        for i, faction in enumerate(factions, 1):
            faction_data = data["achievements"].get(faction, {"cards": []})
            total_cards = len(faction_data.get("cards", []))
            user_cards_count = len(faction_cards.get(faction, set()))
            
            # Проверяем, собрано ли достижение
            is_complete = user_cards_count >= total_cards and total_cards > 0
            is_claimed = faction in claimed_achievements
            
            if is_complete and not is_claimed:
                status = "🎁 ЗАБРАТЬ"
                callback = f"achievement_claim_{i}"
            elif is_claimed:
                status = "✅ Получено"
                callback = "achievement_claimed"
            else:
                status = f"📊 {user_cards_count}/{total_cards}"
                callback = "achievement_progress"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{i}. {faction} - {status}",
                    callback_data=callback
                )
            ])
        
        # ⭐ КНОПКА НАЗАД ⭐
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="profile_back")])
        
        await query.edit_message_text(
            "🏆 **Достижения**\n\n"
            "Соберите все карты каждой фракции,\n"
            "чтобы получить награду!\n\n"
            "🎁 **Награда за достижение:**\n"
            "• 20 бесплатных попыток\n"
            "• 20000 центов\n\n"
            "Выберите достижение:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в achievements_menu: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def claim_achievement(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Получение награды за достижение."""
    try:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        data = load_data()
        user_data = data["users"].get(user_id)
        
        if not user_data:
            await query.edit_message_text("❌ Вы ещё не начали игру!")
            return
        
        # Получаем номер достижения из callback_data
        achievement_num = int(query.data.split("_")[-1])
        
        factions = [
            "Замок", "Оплот", "Башня", "Инферно",
            "Некрополис", "Темница", "Цитадель", "Крепость", "Сопряжение"
        ]
        
        if achievement_num < 1 or achievement_num > len(factions):
            await query.edit_message_text("❌ Неверное достижение!")
            return
        
        faction = factions[achievement_num - 1]
        claimed_achievements = user_data.get("claimed_achievements", [])
        
        # Проверяем, не получена ли уже награда
        if faction in claimed_achievements:
            await query.edit_message_text("❌ Вы уже получили награду за это достижение!")
            return
        
        # Получаем карты пользователя
        user_card_ids = user_data.get("cards", [])
        
        # Считаем карты по фракциям
        faction_cards = set()
        for card_id in user_card_ids:
            card = find_card_by_id(card_id, data["cards"])
            if card and card.get("faction") == faction:
                faction_cards.add(card_id)
        
        # Проверяем, собрано ли достижение
        faction_data = data["achievements"].get(faction, {"cards": []})
        total_cards = len(faction_data.get("cards", []))
        
        if len(faction_cards) < total_cards or total_cards == 0:
            await query.edit_message_text(
                f"❌ Достижение не завершено!\n\n"
                f"📊 Собрано: {len(faction_cards)}/{total_cards}\n"
                f"🏷 Фракция: {faction}"
            )
            return
        
        # ⭐ ВЫДАЁМ НАГРАДУ ⭐
        user_data["free_rolls"] = user_data.get("free_rolls", 0) + 20
        user_data["cents"] = user_data.get("cents", 0) + 20000
        claimed_achievements.append(faction)
        user_data["claimed_achievements"] = claimed_achievements
        
        save_data(data)
        
        await query.edit_message_text(
            f"🎉 **Достижение получено!**\n\n"
            f"🏆 {achievement_num}. {faction}\n\n"
            f"🎁 **Награда:**\n"
            f"• 🎲 +20 бесплатных попыток\n"
            f"• 🪙 +20000 центов\n\n"
            f"Поздравляем!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад к достижениям", callback_data="achievements_menu")
            ]]),
            parse_mode="Markdown"
        )
        
        logger.info(f"Пользователь {user_id} получил достижение: {faction}")
        
    except Exception as e:
        logger.error(f"Ошибка claim_achievement: {e}")
        await query.answer("❌ Произошла ошибка", show_alert=True)

async def set_achievement_cards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Добавляет карты в достижение фракции."""
    try:
        data = load_data()
        if not is_admin(str(update.effective_user.id), data):
            await update.message.reply_text("🚫 Только для администратора!")
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "ℹ️ **Формат команды:**\n"
                "/set_achievement_cards [Фракция] [ID_карты1] [ID_карты2] ...\n\n"
                "**Пример:**\n"
                "/set_achievement_cards Замок 1 2 3 4 5",
                parse_mode="Markdown"
            )
            return
        
        faction = context.args[0]
        card_ids = [int(x) for x in context.args[1:]]
        
        valid_factions = [
            "Замок", "Оплот", "Башня", "Инферно",
            "Некрополис", "Темница", "Цитадель", "Крепость", "Сопряжение"
        ]
        
        if faction not in valid_factions:
            await update.message.reply_text(
                f"⚠️ Недопустимая фракция!\n"
                f"Доступные: {', '.join(valid_factions)}"
            )
            return
        
        # Проверяем существование карт
        for card_id in card_ids:
            if not find_card_by_id(card_id, data["cards"]):
                await update.message.reply_text(f"⚠️ Карта #{card_id} не найдена!")
                return
        
        # Сохраняем карты достижения
        data["achievements"][faction]["cards"] = card_ids
        save_data(data)
        
        await update.message.reply_text(
            f"✅ **Достижение обновлено!**\n\n"
            f"🏷 Фракция: {faction}\n"
            f"🃏 Карт: {len(card_ids)}\n"
            f"📋 ID: {', '.join(map(str, card_ids))}",
            parse_mode="Markdown"
        )
        
        logger.info(f"Админ обновил достижение {faction}: {card_ids}")
        
    except ValueError:
        await update.message.reply_text("⚠️ ID карт должны быть числами!")
    except Exception as e:
        logger.error(f"Ошибка set_achievement_cards: {e}")
        await update.message.reply_text("❌ Ошибка при настройке достижения")


        
        # Сохраняем данные если были отправлены уведомления
        if notified_count > 0:
            save_data(data)
            logger.info(f"Отправлено {notified_count} уведомлений")
        
    except Exception as e:
        logger.error(f"Ошибка в send_card_notifications: {e}")


async def send_notification_after_delay(user_id: str, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(61 * 60)  # Ждём 61 минуту
    await context.bot.send_message(
        chat_id=user_id,
        text="🎉 Вы снова можете получить карту!"
    )


# ===== ЗАПУСК БОТА =====


def main() -> None:

    try:

        if BOT_TOKEN == "ВАШ_ТОКЕН_БОТА" or INITIAL_ADMIN_ID == "ВАШ_ID_АДМИНА":

            print("ЗАМЕНИТЕ BOT_TOKEN И INITIAL_ADMIN_ID НА РЕАЛЬНЫЕ ЗНАЧЕНИЯ!")

            input("Нажмите Enter для выхода...")

            return

        if not os.path.exists(DATA_FILE):

            save_data(load_data())

            print("Создан новый файл данных")

        # Регистрируем обработчики
        application = Application.builder().token(BOT_TOKEN).build()

        handlers = [
            CommandHandler("start", start),
            CommandHandler("profile", my_profile),
            CommandHandler("dice", dice),
            CommandHandler("craft", craft),
            CommandHandler("help", help_command),
            CommandHandler("top", top_players),
            CommandHandler("trade", trade_menu),  # ← ДОБАВЬТЕ
            CommandHandler("add_card", add_card),
            CommandHandler("add_card_to_player", add_card_to_player),
            CommandHandler("add_rolls_to_player", add_rolls_to_player),
            CommandHandler("edit_card", edit_card),
            CommandHandler("card_info", card_info),
            CommandHandler("cards", list_cards),
            CommandHandler("toggle_card", toggle_card),
            CommandHandler("broadcast", broadcast),
            CommandHandler("reset_all_cards", reset_all_cards),
            CommandHandler("reset_season_points", reset_season_points), 
            CommandHandler("delete_card", delete_card),
            CommandHandler("reset_user", reset_user),
            CommandHandler("check_cards", check_cards),
            CommandHandler("list_admins", list_admins),
            CommandHandler("add_admin", add_admin),
            CommandHandler("remove_admin", remove_admin),
            CommandHandler("set_achievement_cards", set_achievement_cards),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            CallbackQueryHandler(handle_callback, pattern=r"^card_.*"),
            CallbackQueryHandler(mycards_callback, pattern=r"^mycards_.*"),
            CallbackQueryHandler(craft_callback, pattern=r"^craft_.*"),  # Кнопки крафта
            CallbackQueryHandler(dice_callback, pattern=r"^dice_.*"),
            CallbackQueryHandler(casino_callback, pattern=r"^casino_.*"),
            CallbackQueryHandler(top_callback, pattern=r"^top_.*"),
            CallbackQueryHandler(trade_button_callback, pattern=r"^trade_(accept|decline)_btn_.*"),
            CallbackQueryHandler(trade_offer_callback, pattern=r"^trade_offer_.*"),
            CallbackQueryHandler(trade_return_callback, pattern=r"^trade_return_.*"),
            CallbackQueryHandler(trade_final_callback, pattern=r"^trade_final_(confirm|decline)_.*"),
            CallbackQueryHandler(trade_callback, pattern=r"^trade_.*"),
            CallbackQueryHandler(profile_callback, pattern=r"^(achievements_menu|profile_back|achievement_.*)"),
     
        ]

        for handler in handlers:
            application.add_handler(handler) 

        
        print("Бот успешно запущен! Ctrl+C для остановки")
        logger.info("Бот запущен")

        
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:

        logger.critical(f"Критическая ошибка: {e}")

        print(f"Ошибка запуска: {e}")

        input("Нажмите Enter для выхода...")


if __name__ == "__main__":

    main()
