import random
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils import executor

# **ВАЖНО**: Замените эти значения на ваши токены после отзыва старых
API_TOKEN = '7533727337:AAH4ofJAsTe9tXolmEjysny89fYe6QHEMkE'
OPENAI_API_KEY = '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'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

rooms = {}
user_states = {}

logging.basicConfig(level=logging.INFO, filename="bot_debug.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")


def generate_room_code():
    """Генерация уникального кода комнаты."""
    return ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890", k=6))


def main_menu():
    """Создание главного меню с кнопками."""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Создать комнату", callback_data="create_room"))
    markup.add(InlineKeyboardButton("Присоединиться к комнате", callback_data="join_room"))
    markup.add(InlineKeyboardButton("Информация о игре", callback_data="game_info"))
    markup.add(InlineKeyboardButton("Проверить баланс", callback_data="check_balance"))
    return markup


def back_to_main_menu():
    """Кнопка для возврата в главное меню."""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Назад в главное меню", callback_data="back_to_main"))
    return markup


def start_game_button(room_code):
    """Кнопка для начала игры."""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Начать игру", callback_data=f"start_game_{room_code}"))
    return markup


@dp.message_handler(commands=['start'])
async def start(message: Message):
    """Обработчик команды /start."""
    user_states.pop(message.from_user.id, None)
    await message.reply("Привет! Выберите действие:", reply_markup=main_menu())
    logging.info(f"Пользователь {message.from_user.id} начал взаимодействие с ботом.")


@dp.callback_query_handler(lambda callback: callback.data == "create_room")
async def create_room(callback: CallbackQuery):
    """Обработчик создания комнаты."""
    room_code = generate_room_code()
    rooms[room_code] = {
        'host': callback.from_user.id,
        'players': [],
        'teams': {},
        'market_price': 1,
        'fundamental_price': 1,
        'choices': {},
        'out_players': set(),
        'gpt_enabled': False,
        'gpt_is_host': False,
        'balances': {},
        'purchased_stocks': {},
        'insiders': {},
        'round': 0,
        'false_count': 0
    }
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Подключить GPT", callback_data=f"enable_gpt_{room_code}"))
    markup.add(InlineKeyboardButton("Без GPT", callback_data=f"disable_gpt_{room_code}"))
    await callback.message.edit_text(
        f"Комната создана! Код: {room_code}\nВыберите режим игры:", reply_markup=markup
    )
    logging.info(f"Комната {room_code} создана пользователем {callback.from_user.id}")


@dp.callback_query_handler(lambda callback: callback.data.startswith("enable_gpt_"))
async def enable_gpt(callback: CallbackQuery):
    """Включение GPT в комнате."""
    room_code = callback.data.split("_")[-1]
    room = rooms.get(room_code)
    if room:
        room['gpt_enabled'] = True
        logging.info(f"GPT включён в комнате {room_code}")
        await set_insider_price_mode(callback, room_code)
    else:
        logging.error(f"Комната {room_code} не найдена при включении GPT")
        await callback.answer("Комната не найдена.", show_alert=True)


@dp.callback_query_handler(lambda callback: callback.data.startswith("disable_gpt_"))
async def disable_gpt(callback: CallbackQuery):
    """Отключение GPT в комнате."""
    room_code = callback.data.split("_")[-1]
    room = rooms.get(room_code)
    if room:
        room['gpt_enabled'] = False
        logging.info(f"GPT отключён в комнате {room_code}")
        await set_insider_price_mode(callback, room_code)
        host_id = room['host']
        if host_id not in room['players']:
            room['players'].append(host_id)
            room['teams'][host_id] = "Host"
            room['balances'][host_id] = 0
            room['purchased_stocks'][host_id] = 0
            room['insiders'][host_id] = 0
            logging.info(f"Хост {host_id} добавлен как игрок в комнате {room_code} при отключении GPT")
    else:
        logging.error(f"Комната {room_code} не найдена при отключении GPT")
        await callback.answer("Комната не найдена.", show_alert=True)


async def set_insider_price_mode(callback: CallbackQuery, room_code):
    """Выбор режима цены инсайда."""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Цена инсайда = цене акции", callback_data=f"insider_same_{room_code}"))
    markup.add(InlineKeyboardButton("Цена инсайда = 150% цены акции", callback_data=f"insider_150_{room_code}"))
    await callback.message.edit_text(
        f"Выберите режим цены инсайда для комнаты {room_code}:", reply_markup=markup
    )
    logging.info(f"Выбор режима цены инсайда в комнате {room_code}")


@dp.callback_query_handler(lambda callback: callback.data.startswith("insider_same_"))
async def insider_same(callback: CallbackQuery):
    """Установка режима цены инсайда = цена акции."""
    room_code = callback.data.split("_")[-1]
    room = rooms.get(room_code)
    if room:
        room['insider_price_mode'] = "same"
        logging.info(f"Режим цены инсайда 'same' установлен в комнате {room_code}")
        await finalize_room_setup(callback, room_code)
    else:
        logging.error(f"Комната {room_code} не найдена при установке режима инсайда 'same'")
        await callback.answer("Комната не найдена.", show_alert=True)


@dp.callback_query_handler(lambda callback: callback.data.startswith("insider_150_"))
async def insider_150(callback: CallbackQuery):
    """Установка режима цены инсайда = 150% цены акции."""
    room_code = callback.data.split("_")[-1]
    room = rooms.get(room_code)
    if room:
        room['insider_price_mode'] = "150%"
        logging.info(f"Режим цены инсайда '150%' установлен в комнате {room_code}")
        await finalize_room_setup(callback, room_code)
    else:
        logging.error(f"Комната {room_code} не найдена при установке режима инсайда '150%'")
        await callback.answer("Комната не найдена.", show_alert=True)


async def finalize_room_setup(callback: CallbackQuery, room_code):
    """Завершение настройки комнаты."""
    await callback.message.edit_text(
        f"Настройки комнаты завершены. Комната {room_code} готова к игре. Поделитесь кодом, чтобы другие могли присоединиться."
    )
    await bot.send_message(callback.from_user.id, "Ожидайте подключения игроков.")
    logging.info(f"Комната {room_code} готова к игре")


@dp.callback_query_handler(lambda callback: callback.data == "join_room")
async def join_room(callback: CallbackQuery):
    """Обработчик присоединения к комнате."""
    user_id = callback.from_user.id
    user_states[user_id] = "awaiting_room_code"
    await callback.message.edit_text("Введите код комнаты:", reply_markup=back_to_main_menu())
    logging.info(f"Пользователь {user_id} пытается присоединиться к комнате")


@dp.callback_query_handler(lambda callback: callback.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Обработчик возврата в главное меню."""
    user_id = callback.from_user.id
    user_states.pop(user_id, None)
    await callback.message.edit_text("Вы вернулись в главное меню.", reply_markup=main_menu())
    await callback.answer()
    logging.info(f"Пользователь {user_id} вернулся в главное меню")


@dp.callback_query_handler(lambda callback: callback.data == "check_balance")
async def check_balance(callback: CallbackQuery):
    """Обработчик проверки баланса игрока."""
    user_id = callback.from_user.id
    room_code = None
    for code, room in rooms.items():
        if user_id == room['host'] or user_id in room['players']:
            room_code = code
            break
    if not room_code:
        await callback.answer("Вы не состоите ни в одной комнате.", show_alert=True)
        logging.info(f"Пользователь {user_id} запросил баланс, но не состоит в комнате")
        return
    room = rooms.get(room_code)
    if not room:
        await callback.answer("Комната не найдена.", show_alert=True)
        logging.error(f"Комната {room_code} не найдена при проверке баланса пользователем {user_id}")
        return
    balance = room['balances'].get(user_id, 0)
    stocks = room['purchased_stocks'].get(user_id, 0)
    insiders = room['insiders'].get(user_id, 0)
    await bot.send_message(
        user_id,
        f"**Ваш баланс:** {balance} единиц\n"
        f"**Количество акций:** {stocks}\n"
        f"**Количество инсайдов:** {insiders}",
        parse_mode='Markdown'
    )
    await callback.answer()
    logging.info(f"Пользователь {user_id} проверил баланс: Баланс={balance}, Акции={stocks}, Инсайды={insiders}")


@dp.message_handler()
async def process_message(message: Message):
    """Обработка сообщений пользователей."""
    user_id = message.from_user.id
    user_state = user_states.get(user_id)

    if user_state == "awaiting_room_code":
        room_code = message.text.strip().upper()
        if room_code in rooms:
            room = rooms[room_code]
            if len(room['players']) >= 5:
                await message.reply("Комната уже заполнена! Максимум 5 игроков.", reply_markup=back_to_main_menu())
                logging.info(f"Пользователь {user_id} попытался присоединиться к заполненной комнате {room_code}")
                return

            if user_id == room['host'] and not room['gpt_enabled']:
                await message.reply("Вы уже являетесь хостом и игроком в этой комнате.",
                                    reply_markup=back_to_main_menu())
                logging.info(f"Хост {user_id} попытался присоединиться к своей комнате {room_code} как игрок")
                return
            if user_id == room['host']:
                await message.reply("Вы уже являетесь хостом и игроком в этой комнате.",
                                    reply_markup=back_to_main_menu())
                logging.info(f"Хост {user_id} попытался присоединиться к своей комнате {room_code} как игрок")
                return
            if user_id in room['players']:
                await message.reply("Вы уже присоединились к этой комнате.", reply_markup=back_to_main_menu())
                logging.info(
                    f"Пользователь {user_id} попытался присоединиться к комнате {room_code}, но уже участвует")
                return
            room['players'].append(user_id)
            room['balances'][user_id] = 0
            room['purchased_stocks'][user_id] = 0
            room['insiders'][user_id] = 0
            user_states[user_id] = f"awaiting_team_name_{room_code}"
            await message.reply("Введите название вашей команды:", reply_markup=back_to_main_menu())
            logging.info(f"Пользователь {user_id} присоединился к комнате {room_code}")
        else:
            await message.reply("Комната с таким кодом не найдена.", reply_markup=back_to_main_menu())
            logging.info(f"Пользователь {user_id} ввёл неверный код комнаты: {room_code}")

    elif user_state and user_state.startswith("awaiting_team_name_"):
        room_code = user_state.split("_")[-1]
        room = rooms.get(room_code)
        team_name = message.text.strip()
        if room:
            if team_name in room['teams'].values():
                await message.reply("Это название команды уже занято. Пожалуйста, выберите другое.",
                                    reply_markup=back_to_main_menu())
                logging.info(f"Пользователь {user_id} попытался выбрать занятое название команды: {team_name}")
                return
            room['teams'][user_id] = team_name

            host_id = room['host']
            await bot.send_message(
                host_id,
                f"Игрок подключился: {message.from_user.full_name}\nКоманда: {team_name}."
            )
            await message.reply(f"Вы успешно присоединились к комнате {room_code}!", reply_markup=back_to_main_menu())
            user_states.pop(user_id)
            logging.info(f"Пользователь {user_id} выбрал команду '{team_name}' в комнате {room_code}")

            if len(room['players']) == 5:
                if room['gpt_enabled']:
                    if "ChatGPT" not in room['players']:
                        room['players'].append("ChatGPT")
                        room['teams']["ChatGPT"] = "Нейросеть"
                        room['balances']["ChatGPT"] = 0
                        room['purchased_stocks']["ChatGPT"] = 0
                        room['insiders']["ChatGPT"] = 0
                        await bot.send_message(host_id, "Нейросеть подключена как игрок.")
                        logging.info(f"Нейросеть подключена как игрок в комнате {room_code}")
                await bot.send_message(
                    host_id,
                    "Все игроки подключились! Вы можете начать игру, нажав кнопку ниже.",
                    reply_markup=start_game_button(room_code)
                )
                logging.info(f"Все игроки подключились к комнате {room_code}. Хосту предложено начать игру.")
        else:
            await message.reply("Произошла ошибка. Комната не найдена.", reply_markup=back_to_main_menu())
            logging.error(f"Пользователь {user_id} пытается выбрать команду в несуществующей комнате {room_code}")


@dp.callback_query_handler(lambda callback: callback.data.startswith("host_play_gpt_"))
async def host_play_gpt(callback: CallbackQuery):
    """Хост выбирает играть вместо GPT."""
    room_code = callback.data.split("_")[-1]
    room = rooms.get(room_code)
    if room:
        if room['gpt_enabled']:
            if "ChatGPT" in room['players']:
                room['players'].remove("ChatGPT")
                del room['teams']["ChatGPT"]
                del room['balances']["ChatGPT"]
                del room['purchased_stocks']["ChatGPT"]
                del room['insiders']["ChatGPT"]
                logging.info(f"Нейросеть удалена из комнаты {room_code} по выбору хоста")
            host_id = room['host']
            if host_id not in room['players']:
                room['players'].append(host_id)
                room['teams'][host_id] = "Host"
                room['balances'][host_id] = 0
                room['purchased_stocks'][host_id] = 0
                room['insiders'][host_id] = 0
                room['gpt_is_host'] = True
                await bot.send_message(host_id, "Вы будете играть вместо GPT.")
                await callback.message.edit_text(
                    f"Хост играет вместо GPT. Комната {room_code} готова к игре. Поделитесь кодом, чтобы другие могли присоединиться."
                )
                await bot.send_message(callback.from_user.id, "Ожидайте подключения игроков.")
                logging.info(f"Хост {host_id} выбрал играть вместо GPT в комнате {room_code}")
                if len(room['players']) == 5:
                    await bot.send_message(
                        host_id,
                        "Все игроки подключились! Вы можете начать игру, нажав кнопку ниже.",
                        reply_markup=start_game_button(room_code)
                    )
                    logging.info(f"Все игроки подключились к комнате {room_code}. Хосту предложено начать игру.")
    else:
        await callback.answer("Комната не найдена.", show_alert=True)
        logging.error(f"Комната {room_code} не найдена при выборе хоста играть вместо GPT")


@dp.callback_query_handler(lambda callback: callback.data.startswith("host_not_play_gpt_"))
async def host_not_play_gpt(callback: CallbackQuery):
    """Хост выбирает не играть вместо GPT."""
    room_code = callback.data.split("_")[-1]
    room = rooms.get(room_code)
    if room:
        if room['gpt_enabled']:
            if "ChatGPT" in room['players']:
                room['players'].remove("ChatGPT")
                del room['teams']["ChatGPT"]
                del room['balances']["ChatGPT"]
                del room['purchased_stocks']["ChatGPT"]
                del room['insiders']["ChatGPT"]
                logging.info(f"Нейросеть удалена из комнаты {room_code} по выбору хоста не играть вместо GPT")
            host_id = room['host']
            if host_id not in room['players']:
                room['players'].append(host_id)
                room['teams'][host_id] = "Host"
                room['balances'][host_id] = 0
                room['purchased_stocks'][host_id] = 0
                room['insiders'][host_id] = 0
                room['gpt_is_host'] = False
                await bot.send_message(host_id, "Вы будете играть как обычный игрок.")
                await callback.message.edit_text(
                    f"Хост теперь играет как обычный игрок. Комната {room_code} готова к игре. Поделитесь кодом, чтобы другие могли присоединиться."
                )
                await bot.send_message(callback.from_user.id, "Ожидайте подключения игроков.")
                logging.info(f"Хост {host_id} выбрал играть как обычный игрок в комнате {room_code}")
                if len(room['players']) == 5:
                    await bot.send_message(
                        host_id,
                        "Все игроки подключились! Вы можете начать игру, нажав кнопку ниже.",
                        reply_markup=start_game_button(room_code)
                    )
                    logging.info(f"Все игроки подключились к комнате {room_code}. Хосту предложено начать игру.")
    else:
        await callback.answer("Комната не найдена.", show_alert=True)
        logging.error(f"Комната {room_code} не найдена при выборе хоста не играть вместо GPT")


@dp.callback_query_handler(lambda callback: callback.data.startswith("start_game_"))
async def start_game_handler(callback: CallbackQuery):
    """Начало игры."""
    room_code = callback.data.split("_")[-1]
    room = rooms.get(room_code)
    if not room:
        await callback.message.edit_text("Комната не найдена!")
        logging.error(f"Попытка начать игру в несуществующей комнате {room_code}")
        return

    if len(room['players']) < 5:
        await callback.message.edit_text("Не все игроки подключились. Ожидайте.")
        logging.info(f"Попытка начать игру в комнате {room_code}, но не все игроки подключились")
        return

    if room['round'] == 0:
        room['round'] = 1
    else:
        room['round'] += 1

    await callback.message.edit_text("Игра началась! Следите за ходом игры.")
    logging.info(f"Игра началась в комнате {room_code}, раунд {room['round']}")
    await next_round(room_code)


async def next_round(room_code):
    """Запуск следующего раунда игры."""
    room = rooms.get(room_code)
    if not room:
        logging.error(f"Комната {room_code} не найдена при запуске раунда")
        return

    room['choices'] = {}
    room['false_count'] = 0

    for player_id in room['players']:
        await bot.send_message(
            player_id,
            f"Раунд {room['round']} начался!"
        )
        logging.info(f"Раунд {room['round']} начался для игрока {player_id} в комнате {room_code}")

    for player_id in room['players']:
        if player_id in room['out_players']:
            await process_choice(room_code, player_id, "sell_all")
            logging.info(f"Игрок {player_id} автоматически выбрал 'SELL ALL' в комнате {room_code}")
            continue

        if player_id == "ChatGPT":
            choice = random.choice(["buy", "sell_all"])
            await process_choice(room_code, player_id, choice)
            logging.info(f"GPT выбрал '{choice.upper()}' в комнате {room_code}")
        else:
            insider_price_mode = room.get('insider_price_mode', 'same')
            if insider_price_mode == "same":
                current_insider_price = room['market_price']
            elif insider_price_mode == "150%":
                current_insider_price = room['market_price'] * 1.5
            else:
                current_insider_price = 50

            current_insider_price = round(current_insider_price)

            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("Купить инсайд", callback_data=f"buy_insider_{player_id}_{room_code}"),
                InlineKeyboardButton("Не покупать инсайд", callback_data=f"not_buy_insider_{player_id}_{room_code}")
            )
            await bot.send_message(player_id,
                                   f"Раунд {room['round']}: Хотите ли вы купить инсайд за {current_insider_price} единиц?",
                                   reply_markup=markup)
            logging.info(f"Запрос на покупку инсайда отправлен игроку {player_id} в комнате {room_code}")

    await send_game_status(room_code)
    logging.info(f"Информация о состоянии игры отправлена хосту {room['host']} в комнате {room_code}")


async def send_game_status(room_code):
    """Отправка хосту текущего состояния игры."""
    room = rooms.get(room_code)
    if not room:
        logging.error(f"Комната {room_code} не найдена при отправке статуса игры")
        return

    host_id = room['host']
    balances = "\n".join([
        f"{room['teams'].get(p, 'Неизвестно')}: {b}"
        for p, b in room['balances'].items()
    ])
    team_status = "\n".join([
        f"{room['teams'].get(p, 'Неизвестно')}: {'Нейросеть' if p == 'ChatGPT' else p}" for p in room['players']
    ])
    purchased = "\n".join([
        f"{room['teams'].get(p, 'Неизвестно')}: {room['purchased_stocks'].get(p, 0)} акций"
        for p in room['players']
    ])
    insiders = "\n".join([
        f"{room['teams'].get(p, 'Неизвестно')}: {insider_count} инсайдов"
        for p, insider_count in room.get('insiders', {}).items()
    ])
    await bot.send_message(
        host_id,
        f"Раунд: {room['round']}\n"
        f"Рыночная цена: {room['market_price']}\n"
        f"Фундаментальная цена: {room['fundamental_price']}\n"
        f"Баланс игроков:\n{balances}\n"
        f"Купленные акции:\n{purchased}\n"
        f"Купленные инсайды:\n{insiders}\n"
        f"Команды и игроки:\n{team_status}\n"
        "Ожидание решений игроков..."
    )
    logging.info(f"Статус игры отправлен хосту {host_id} в комнате {room_code}")


@dp.callback_query_handler(lambda callback: callback.data.startswith("buy_insider_") or
                                            callback.data.startswith("not_buy_insider_"))
async def handle_insider_decision(callback: CallbackQuery):
    """Обработка решений игроков относительно покупки инсайда."""
    try:
        if callback.data.startswith("buy_insider_"):
            await buy_insider(callback)
        elif callback.data.startswith("not_buy_insider_"):
            await not_buy_insider(callback)
    except Exception as e:
        logging.error(f"Ошибка при обработке решения инсайда: {e}")
        await callback.answer("Произошла ошибка при обработке вашего выбора.", show_alert=True)


async def buy_insider(callback: CallbackQuery):
    """Обработка запроса игрока на покупку инсайда."""
    data = callback.data.split("_")

    if len(data) != 4:
        await callback.answer("Некорректный формат данных.", show_alert=True)
        logging.warning(f"Некорректный формат данных в buy_insider: {callback.data}")
        return

    player_id_str = data[2]
    room_code = data[3]

    try:
        player_id = int(player_id_str)
    except ValueError:
        player_id = player_id_str

    room = rooms.get(room_code)
    if not room:
        await callback.answer("Комната не найдена.", show_alert=True)
        logging.error(f"Комната {room_code} не найдена при покупке инсайда")
        return

    team_name = room['teams'].get(player_id, 'Неизвестно')
    if not team_name:
        await callback.answer("Ошибка: Название вашей команды не найдено.", show_alert=True)
        logging.error(f"Название команды не найдено для игрока {player_id} в комнате {room_code}")
        return

    insider_price_mode = room.get('insider_price_mode', 'same')
    if insider_price_mode == "same":
        INSIDER_COST = room['market_price']
    elif insider_price_mode == "150%":
        INSIDER_COST = room['market_price'] * 1.5
    else:
        INSIDER_COST = 50

    INSIDER_COST = round(INSIDER_COST)

    room['balances'][player_id] -= INSIDER_COST
    logging.info(f"Игрок {player_id} купил инсайд за {INSIDER_COST} единиц в комнате {room_code}")

    room.setdefault('insiders', {}).setdefault(player_id, 0)
    room['insiders'][player_id] += 1

    await bot.send_message(
        player_id,
        f"Вы купили инсайд за {INSIDER_COST} единиц. Для получения инсайда, напишите в личные сообщения @guglenkov."
    )

    await bot.send_message(
        room['host'],
        f"Команда '{team_name}' купила инсайд."
    )
    logging.info(f"Хост {room['host']} уведомлён о покупке инсайда командой '{team_name}' в комнате {room_code}")

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("BUY (Докупить акции)", callback_data=f"buy_{player_id}_{room_code}"),
        InlineKeyboardButton("SELL ALL (Продать все акции)", callback_data=f"sell_all_{player_id}_{room_code}")
    )
    await bot.send_message(
        player_id,
        "Выберите действие с акциями:",
        reply_markup=markup
    )

    await callback.answer("Вы купили инсайд. Теперь выберите действие с акциями.", show_alert=True)
    logging.info(f"Игроку {player_id} предоставлен выбор действий с акциями после покупки инсайда")


async def not_buy_insider(callback: CallbackQuery):
    """Обработка отказа игрока от покупки инсайда и переход к выбору действий над акциями."""
    data = callback.data.split("_")

    if len(data) != 5:
        await callback.answer("Некорректный формат данных.", show_alert=True)
        logging.warning(f"Некорректный формат данных в not_buy_insider: {callback.data}")
        return

    player_id_str = data[3]
    room_code = data[4]

    try:
        player_id = int(player_id_str)
    except ValueError:
        player_id = player_id_str

    room = rooms.get(room_code)
    if not room:
        await callback.answer()
        logging.error(f"Комната {room_code} не найдена при отказе от инсайда")
        return

    team_name = room['teams'].get(player_id, 'Неизвестно')
    if not team_name:
        await callback.answer("Ошибка: Название вашей команды не найдено.", show_alert=True)
        logging.error(f"Название команды не найдено для игрока {player_id} в комнате {room_code}")
        return

    if player_id in room['out_players']:
        await callback.answer("Вы не можете выбирать действия с акциями, так как уже продали все свои акции.",
                              show_alert=True)
        logging.info(f"Игрок {player_id} попытался выбрать действия с акциями после продажи всех в комнате {room_code}")
        return

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("BUY (Докупить акции)", callback_data=f"buy_{player_id}_{room_code}"),
        InlineKeyboardButton("SELL ALL (Продать все акции)", callback_data=f"sell_all_{player_id}_{room_code}")
    )
    await bot.send_message(
        player_id,
        "Вы отказались от инсайда. Выберите действие с акциями:",
        reply_markup=markup
    )

    await callback.answer("Вы отказались от инсайда. Теперь выберите действие с акциями.", show_alert=True)
    logging.info(f"Игрок {player_id} отказался от инсайда и получил выбор действий с акциями в комнате {room_code}")


@dp.callback_query_handler(lambda callback: callback.data.startswith("buy_"))
async def buy_action(callback: CallbackQuery):
    """Игрок выбирает купить акции."""
    data = callback.data.split("_")
    if len(data) != 3:
        await callback.answer("Некорректный формат данных.", show_alert=True)
        logging.warning(f"Некорректный формат данных в buy_action: {callback.data}")
        return

    player_id_str = data[1]
    room_code = data[2]

    try:
        player_id = int(player_id_str)
    except ValueError:
        player_id = player_id_str

    room = rooms.get(room_code)
    if not room:
        await callback.answer("Комната не найдена.", show_alert=True)
        logging.error(f"Комната {room_code} не найдена при выборе 'BUY' игроком {player_id}")
        return
    if player_id in room['out_players']:
        await callback.answer("Вы не можете покупать акции, так как уже продали все свои акции.", show_alert=True)
        logging.info(f"Игрок {player_id} попытался купить акции после продажи всех в комнате {room_code}")
        return

    if player_id in room['choices']:
        await callback.answer("Вы уже сделали выбор в этом раунде.", show_alert=True)
        logging.info(f"Игрок {player_id} попытался сделать повторный выбор в комнате {room_code}")
        return

    await process_choice(room_code, player_id, "buy")

    balance = room['balances'].get(player_id, 0)
    stocks = room['purchased_stocks'].get(player_id, 0)
    insiders = room['insiders'].get(player_id, 0)
    await bot.send_message(
        player_id,
        f"**Ваш баланс:** {balance} единиц\n"
        f"**Количество акций:** {stocks}\n"
        f"**Количество инсайдов:** {insiders}",
        parse_mode='Markdown'
    )
    logging.info(
        f"Игрок {player_id} выбрал 'BUY' в комнате {room_code}: Баланс={balance}, Акции={stocks}, Инсайды={insiders}")

    await callback.answer("Вы выбрали купить акции.", show_alert=True)


@dp.callback_query_handler(lambda callback: callback.data.startswith("sell_all_"))
async def sell_all_action(callback: CallbackQuery):
    """Игрок выбирает продать все акции."""
    data = callback.data.split("_")
    if len(data) != 4:
        await callback.answer("Некорректный формат данных.", show_alert=True)
        logging.warning(f"Некорректный формат данных в sell_all_action: {callback.data}")
        return

    player_id_str = data[2]
    room_code = data[3]

    try:
        player_id = int(player_id_str)
    except ValueError:
        player_id = player_id_str

    room = rooms.get(room_code)
    if not room:
        await callback.answer("Комната не найдена.", show_alert=True)
        logging.error(f"Комната {room_code} не найдена при выборе 'SELL ALL' игроком {player_id}")
        return

    if player_id in room['choices']:
        await callback.answer("Вы уже сделали выбор в этом раунде.", show_alert=True)
        logging.info(f"Игрок {player_id} попытался сделать повторный выбор в комнате {room_code}")
        return

    await process_choice(room_code, player_id, "sell_all")

    balance = room['balances'].get(player_id, 0)
    stocks = room['purchased_stocks'].get(player_id, 0)
    insiders = room['insiders'].get(player_id, 0)
    await bot.send_message(
        player_id,
        f"**Ваш баланс:** {balance} единиц\n"
        f"**Количество акций:** {stocks}\n"
        f"**Количество инсайдов:** {insiders}",
        parse_mode='Markdown'
    )
    logging.info(
        f"Игрок {player_id} выбрал 'SELL ALL' в комнате {room_code}: Баланс={balance}, Акции={stocks}, Инсайды={insiders}")

    await callback.answer("Вы выбрали продать все акции.", show_alert=True)


async def process_choice(room_code, player_id, choice):
    """Обработка выбора игрока и обновление состояния игры."""
    room = rooms.get(room_code)
    if not room:
        logging.error(f"Комната {room_code} не найдена при обработке выбора игрока {player_id}")
        return

    room['choices'][player_id] = choice
    logging.info(f"Игрок {player_id} сделал выбор '{choice.upper()}' в комнате {room_code}")

    host_id = room['host']
    team_name = room['teams'].get(player_id, 'Неизвестно')
    await bot.send_message(
        host_id,
        f"{team_name} выбрал: {choice.upper()}"
    )
    logging.info(f"Хост {host_id} уведомлён о выборе игрока {player_id}: {choice.upper()}")

    if choice == "buy":
        room['purchased_stocks'][player_id] += 1
        room['balances'][player_id] -= room['market_price']
        logging.info(f"Игрок {player_id} купил акцию за {room['market_price']} единиц в комнате {room_code}")
    elif choice == "sell_all":
        if player_id not in room['out_players']:
            revenue = room['purchased_stocks'][player_id] * room['fundamental_price']
            room['balances'][player_id] += revenue
            room['purchased_stocks'][player_id] = 0
            room['out_players'].add(player_id)
            logging.info(f"Игрок {player_id} продал все акции за {revenue} единиц в комнате {room_code}")

            room['false_count'] += 1
            logging.info(f"Счётчик SELL ALL увеличен до {room['false_count']} в комнате {room_code}")

            team_name = room['teams'].get(player_id, 'Неизвестно')
            await bot.send_message(
                host_id,
                f"Команда '{team_name}' продала все свои акции."
            )
            logging.info(f"Хост {host_id} уведомлён о продаже всех акций команды '{team_name}' в комнате {room_code}")

            if room['false_count'] >= 3:
                await end_game_abruptly(room_code)
                logging.info(f"Игра в комнате {room_code} завершена досрочно из-за 3 SELL ALL")
                return

    required_choices = len(room['players']) - len(room['out_players'])
    current_choices = len(room['choices'])

    logging.info(f"В комнате {room_code}: {current_choices}/{required_choices} выборов сделано")

    if room['false_count'] >= 3:
        await end_game_abruptly(room_code)
        logging.info(f"Игра в комнате {room_code} завершена досрочно из-за 3 SELL ALL")
        return

    if current_choices >= required_choices:
        room['round'] += 1
        logging.info(f"Счётчик раундов увеличен до {room['round']} в комнате {room_code}")

        room['market_price'] *= 2
        logging.info(f"Рыночная цена в комнате {room_code} обновлена до {room['market_price']}")

        if random.random() < 0.5:
            room['fundamental_price'] += 1
            fundamental_update = "Фундаментальная цена увеличилась на 1."
        else:
            fundamental_update = "Фундаментальная цена осталась без изменений."

        logging.info(f"{fundamental_update} в комнате {room_code}")

        actions = "\n".join([
            f"{room['teams'].get(p, 'Неизвестно')}: {c.upper()}"
            for p, c in room['choices'].items()
        ])
        balances = "\n".join([f"{room['teams'].get(p, 'Неизвестно')}: {b}" for p, b in room['balances'].items()])
        purchased = "\n".join([
            f"{room['teams'].get(p, 'Неизвестно')}: {room['purchased_stocks'].get(p, 0)} акций"
            for p in room['players']
        ])
        insiders = "\n".join([
            f"{room['teams'].get(p, 'Неизвестно')}: {insider_count} инсайдов"
            for p, insider_count in room.get('insiders', {}).items()
        ])
        await bot.send_message(
            host_id,
            f"Результаты раунда {room['round'] - 1}:\n{actions}\n"
            f"Рыночная цена умножена на 2! Новая рыночная цена: {room['market_price']}.\n"
            f"{fundamental_update}\n"
            f"Фундаментальная цена: {room['fundamental_price']}\n"
            f"Баланс игроков:\n{balances}\n"
            f"Купленные акции:\n{purchased}\n"
            f"Купленные инсайды:\n{insiders}"
        )
        logging.info(f"Результаты раунда {room['round'] - 1} отправлены хосту {host_id} в комнате {room_code}")

        room['choices'] = {}
        await next_round(room_code)


async def end_game_abruptly(room_code):
    """Завершение игры, когда 3 или более игроков продали все акции."""
    room = rooms.get(room_code)
    if not room:
        logging.error(f"Комната {room_code} не найдена при завершении игры")
        return

    host_id = room['host']
    team_status = "\n".join([
        f"{room['teams'].get(p, 'Неизвестно')}: {'Нейросеть' if p == 'ChatGPT' else p}"
        for p in room['players']
    ])
    balances = "\n".join([f"{room['teams'].get(p, 'Неизвестно')}: {b}" for p, b in room['balances'].items()])
    purchased = "\n".join([
        f"{room['teams'].get(p, 'Неизвестно')}: {room['purchased_stocks'].get(p, 0)} акций"
        for p in room['players']
    ])
    insiders = "\n".join([
        f"{room['teams'].get(p, 'Неизвестно')}: {insider_count} инсайдов"
        for p, insider_count in room.get('insiders', {}).items()
    ])

    total_revenue = 0
    for player_id in room['players']:
        if player_id not in room['out_players'] and player_id != "ChatGPT" and player_id != room['host']:
            stocks = room['purchased_stocks'].get(player_id, 0)
            if stocks > 0:
                revenue = stocks * room['fundamental_price']
                room['balances'][player_id] += revenue
                room['purchased_stocks'][player_id] = 0
                total_revenue += revenue
                logging.info(
                    f"Акции игрока {player_id} проданы по фундаментальной цене {room['fundamental_price']} за {revenue} единиц в комнате {room_code}")
                await bot.send_message(
                    player_id,
                    f"Все ваши акции были проданы по фундаментальной цене {room['fundamental_price']} единиц. Ваш баланс увеличен на {revenue} единиц."
                )

    room['market_price'] += total_revenue
    logging.info(f"Общая выручка от продажи акций: {total_revenue}. Рыночная цена увеличена до {room['market_price']}")

    await bot.send_message(
        host_id,
        f"Игра завершена досрочно!\nПричина: 3 или более игроков продали все акции.\n"
        f"Баланс игроков:\n{balances}\n"
        f"Купленные акции:\n{purchased}\n"
        f"Купленные инсайды:\n{insiders}\n"
        f"Команды и игроки:\n{team_status}\n"
        f"Общая выручка от продажи акций: {total_revenue} единиц.\n"
        f"Новая рыночная цена: {room['market_price']} единиц."
    )
    logging.info(f"Игра в комнате {room_code} завершена досрочно. Причина: 3 или более SELL ALL.")

    for player_id in room['players']:
        if player_id != "ChatGPT" and player_id != room['host']:
            await bot.send_message(
                player_id,
                "Игра завершена досрочно из-за того, что 3 или более игроков продали все акции."
            )
            logging.info(f"Игроку {player_id} отправлено уведомление о завершении игры в комнате {room_code}")

    if "ChatGPT" in room['out_players']:
        await bot.send_message(
            "ChatGPT",
            "Игра завершена досрочно."
        )
        logging.info(f"GPT уведомлён о завершении игры в комнате {room_code}")
    if room['host'] in room['out_players']:
        await bot.send_message(
            room['host'],
            "Игра завершена досрочно."
        )
        logging.info(f"Хост {room['host']} уведомлён о завершении игры в комнате {room_code}")

    del rooms[room_code]
    logging.info(f"Комната {room_code} удалена после завершения игры")


@dp.callback_query_handler(lambda callback: callback.data.startswith("host_buy_"))
async def host_buy(callback: CallbackQuery):
    """Хост выбирает купить акции."""
    data = callback.data.split("_")
    if len(data) != 3:
        await callback.answer("Некорректный формат данных.", show_alert=True)
        logging.warning(f"Некорректный формат данных в host_buy: {callback.data}")
        return

    room_code = data[2]
    room = rooms.get(room_code)
    if not room:
        await callback.answer("Комната не найдена.", show_alert=True)
        logging.error(f"Комната {room_code} не найдена при выборе хоста купить акции")
        return

    host_id = room['host']
    if host_id in room['out_players']:
        await callback.answer("Вы не можете покупать акции, так как уже продали все свои акции.", show_alert=True)
        logging.info(f"Хост {host_id} попытался купить акции после продажи всех в комнате {room_code}")
        return

    await bot.send_message(
        host_id,
        "Выберите действие с акциями:",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("BUY (Докупить акции)", callback_data=f"buy_{host_id}_{room_code}"),
            InlineKeyboardButton("SELL ALL (Продать все акции)", callback_data=f"sell_all_{host_id}_{room_code}")
        )
    )
    logging.info(f"Хост {host_id} получил кнопки BUY и SELL ALL в комнате {room_code}")
    await callback.answer("Вы выбрали действие с акциями.", show_alert=True)


@dp.callback_query_handler(lambda callback: callback.data.startswith("host_sell_"))
async def host_sell(callback: CallbackQuery):
    """Хост выбирает продать акции."""
    data = callback.data.split("_")
    if len(data) != 3:
        await callback.answer("Некорректный формат данных.", show_alert=True)
        logging.warning(f"Некорректный формат данных в host_sell: {callback.data}")
        return

    room_code = data[2]
    room = rooms.get(room_code)
    if not room:
        await callback.answer("Комната не найдена.", show_alert=True)
        logging.error(f"Комната {room_code} не найдена при выборе хоста продать акции")
        return

    host_id = room['host']
    if host_id in room['out_players']:
        await callback.answer("Вы уже продали все акции и не можете продавать снова.", show_alert=True)
        logging.info(f"Хост {host_id} попытался продать акции после продажи всех в комнате {room_code}")
        return

    await bot.send_message(
        host_id,
        "Выберите действие с акциями:",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("BUY (Докупить акции)", callback_data=f"buy_{host_id}_{room_code}"),
            InlineKeyboardButton("SELL ALL (Продать все акции)", callback_data=f"sell_all_{host_id}_{room_code}")
        )
    )
    logging.info(f"Хост {host_id} получил кнопки BUY и SELL ALL в комнате {room_code}")
    await callback.answer("Вы выбрали действие с акциями.", show_alert=True)


@dp.callback_query_handler(lambda callback: callback.data == "game_info")
async def game_info(callback: CallbackQuery):
    """Обработчик кнопки 'Информация о игре'."""
    info_text = (
        "📘 **Информация о игре:**\n\n"
        "Ваша цель — управлять балансом и количеством акций вашей команды.\n"
        "Каждый раунд вы можете выбрать: купить инсайд или отказаться.\n"
        "• **Купить инсайд** стоит определённое количество единиц баланса и позволяет получить информацию.\n"
        "• **Не покупать инсайд** переводит вас к выбору действий над акциями:\n"
        "   - **BUY (Докупить акции):** Покупаете одну акцию.\n"
        "   - **SELL ALL (Продать все акции):** Продаёте все акции, после чего не можете покупать больше.\n\n"
        "Если 3 или более игроков выберут **SELL ALL (Продать все акции)**, игра завершится досрочно."
    )
    await bot.send_message(
        callback.from_user.id,
        info_text,
        parse_mode='Markdown'
    )
    await callback.answer()
    logging.info(f"Пользователь {callback.from_user.id} запросил информацию о игре")


@dp.callback_query_handler(lambda callback: True)
async def unknown_callback(callback: CallbackQuery):
    """Обработчик неизвестных callback данных."""
    await callback.answer("Неизвестная команда.", show_alert=True)
    logging.warning(f"Получен неизвестный callback: {callback.data}")


@dp.errors_handler()
async def handle_errors(update, exception):
    """Глобальный обработчик ошибок."""
    logging.error(f"Ошибка: {exception}")
    return True


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
