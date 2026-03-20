import logging


import json

import asyncio

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

            for user_id, user_data in data.get("users", {}).items():

                if "last_card_time" not in user_data:

                    user_data["last_card_time"] = 0

                if "free_rolls" not in user_data:

                    user_data["free_rolls"] = 0

                if "last_dice_time" not in user_data:

                    user_data["last_dice_time"] = 0

                # ⭐ ДОБАВЬТЕ ЭТИ СТРОКИ ⭐

                if "casino_attempts" not in user_data:

                    user_data["casino_attempts"] = 10

                if "last_casino_reset" not in user_data:

                    user_data["last_casino_reset"] = 0

                # =================================

            return data

        except Exception as e:

            logger.error(f"Ошибка загрузки данных: {e}")

    return {"users": {}, "cards": [], "season": 1, "admins": [INITIAL_ADMIN_ID]}


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

            return f"{card['title']}\nРедкость: {card['rarity']}\n📦 Количество: {count} шт."

        return f"{card['title']}\nРедкость: {card['rarity']}"

    caption = f"💥 BOOM\n" f"{card['title']}\n\n" f"Редкость: {card['rarity']}\n"

    # Показываем бонусы только при получении новой карты

    if show_bonus:

        bonus = RARITY_BONUSES.get(card["rarity"], {"cents": 0, "points": 0})

        caption += f"🪙 +{bonus['cents']} центов\n" f"💊 +{bonus['points']} поинтов\n"

    # Добавляем количество, если есть дубликаты

    if count > 1:

        caption += f"📦 Количество: {count} шт.\n"

    caption += (
        f"\nПоинтов в этом сезоне: {user_data['season_points']}\n"
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

        user_id = str(update.effective_user.id)

        data = load_data()

        user_data = data["users"].get(user_id)

        if not user_data:

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

        # Формируем статистику по редкостям

        rarity_text = ""

        for rarity in [
            "T1",
            "T2",
            "T3",
            "T4",
            "T5",
            "T6",
            "T7",
            "T8",
            "UpgradeT1",
            "UpgradeT2",
            "UpgradeT3",
            "UpgradeT4",
            "UpgradeT5",
            "UpgradeT6",
            "UpgradeT7",
        ]:

            if rarity in rarity_stats:

                rarity_text += f"• {rarity}: {rarity_stats[rarity]} шт.\n"

        if not rarity_text:

            rarity_text = "Пока нет карт\n"

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
        )

        await update.message.reply_text(profile_text, parse_mode="Markdown")

    except Exception as e:

        logger.error(f"Ошибка показа профиля: {e}")

        await update.message.reply_text("❌ Произошла ошибка при загрузке профиля")


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

        if len(lines) < 4:

            await update.message.reply_text(
                "ℹ️ Формат:\n/add_card\nURL\nНазвание\nРедкость"
            )

            return

        url = lines[1].strip()

        title = lines[2].strip()

        rarity = lines[3].strip()

        if rarity not in RARITY_BONUSES:

            await update.message.reply_text(
                f"⚠️ Допустимые редкости: {', '.join(RARITY_BONUSES.keys())}"
            )

            return

        data = load_data()

        # Вычисляем новый ID: если карт нет, то 1, иначе max+1

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
            "available": True,
            "media_type": media_type,
        }

        data["cards"].append(new_card)

        save_data(data)

        await update.message.reply_text(
            f"✅ Карточка #{new_id} добавлена!\n"
            f"🏷 {title}\n"
            f"🌟 {rarity}\n"
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

        # Формируем список карточек

        cards_list = []

        for card in data["cards"]:

            status = "✅" if card["available"] else "❌"

            card_info = (
                f"{status} ID: {card['id']}\n"
                f"📺 Тип: {'Анимация' if card.get('media_type') == 'animation' else 'Фото'}\n"
                f"🏷 {card['title']}\n"
                f"🌟 {card['rarity']}\n"
                f"🔗 {card['image_url'][:30]}...\n"
            )

            cards_list.append(card_info)

        # Разбиваем на сообщения по 4000 символов (с запасом)

        MAX_LENGTH = 4000

        current_message = "📋 Все карточки:\n\n"

        for card_info in cards_list:

            # Если добавление следующей карты превысит лимит

            if len(current_message) + len(card_info) + 2 > MAX_LENGTH:

                # Отправляем текущее сообщение

                await update.message.reply_text(current_message)

                # Начинаем новое

                current_message = "📋 Все карточки (продолжение):\n\n" + card_info

            else:

                current_message += card_info + "\n"

        # Отправляем последнее сообщение

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
                "ℹ️ **Формат команды:**\n\n"
                "/edit_card [ID] [параметр] [новое_значение]\n\n"
                "**Параметры:**\n"
                "• title - название карты\n"
                "• url - URL изображения\n"
                "• rarity - редкость (T1-T8, UpgradeT1-UpgradeT7)\n"
                "• available - статус (true/false)\n\n"
                "**Примеры:**\n"
                "/edit_card 45 title Новая карта\n"
                "/edit_card 45 url https://example.com/img.jpg\n"
                "/edit_card 45 rarity T3\n"
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

        valid_params = ["title", "url", "rarity", "available"]

        if param not in valid_params:

            await update.message.reply_text(
                f"⚠️ Неверный параметр! Доступные: {', '.join(valid_params)}"
            )

            return

        # Сохраняем старое значение

        old_value = card.get(param, "не задано")

        # Обновляем значение

        if param == "available":  # Преобразуем в boolean

            new_value = new_value.lower() in ["true", "1", "yes", "вкл", "on"]

            card[param] = new_value

        elif param == "rarity":

            # Проверяем валидность редкости

            if new_value not in RARITY_BONUSES:

                await update.message.reply_text(
                    f"⚠️ Недопустимая редкость!\n"
                    f"Доступные: {', '.join(RARITY_BONUSES.keys())}"
                )

                return

            card[param] = new_value

            # Обновляем media_type

            card["media_type"] = determine_media_type(
                card.get("image_url", ""), new_value
            )

        elif param == "url":

            card["image_url"] = new_value

            # Обновляем media_type

            card["media_type"] = determine_media_type(new_value, card.get("rarity", ""))

        else:

            card[param] = new_value

        save_data(data)

        await update.message.reply_text(
            f"✅ **Карта #{card_id} обновлена!**\n\n"
            f"📝 Параметр: {param}\n"
            f"❌ Было: {old_value}\n"
            f"✅ Стало: {new_value}\n\n"
            f"🏷 {card.get('title')}\n"
            f"🌟 {card.get('rarity')}\n"
            f"{'✅ Включена' if card.get('available') else '❌ Выключена'}",
            parse_mode="Markdown",
        )

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
            f"Редкость: {new_card['rarity']}"
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

        await asyncio.sleep(5)

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

        application = Application.builder().token(BOT_TOKEN).build()

        # Регистрируем обработчики

        handlers = [
            CommandHandler("start", start),
            CommandHandler("profile", my_profile),
            CommandHandler("dice", dice),
            CommandHandler("craft", craft),
            CommandHandler("help", help_command),
            CommandHandler("top", top_players),
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
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            CallbackQueryHandler(handle_callback, pattern=r"^card_.*"),
            CallbackQueryHandler(mycards_callback, pattern=r"^mycards_.*"),
            CallbackQueryHandler(craft_callback, pattern=r"^craft_.*"),  # Кнопки крафта
            CallbackQueryHandler(dice_callback, pattern=r"^dice_.*"),
            CallbackQueryHandler(casino_callback, pattern=r"^casino_.*"),
            CallbackQueryHandler(top_callback, pattern=r"^top_.*"),
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
