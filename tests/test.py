import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, ANY
import sqlite3
from datetime import datetime

from aiogram.fsm.state import StatesGroup, State

class MockTypes:
    Message = MagicMock
    CallbackQuery = MagicMock
    PollAnswer = MagicMock
    InlineKeyboardMarkup = MagicMock
    InlineKeyboardButton = MagicMock
    ReplyKeyboardMarkup = MagicMock
    KeyboardButton = MagicMock

types = MockTypes()

class MockF:
    data = MagicMock()

F = MockF()

class MockFSMContext:
    set_state = AsyncMock
    clear = AsyncMock

FSMContext = MockFSMContext

RoleForm = type('RoleForm', (StatesGroup,), {'role': State()})
QuestionForm = type('QuestionForm', (StatesGroup,), {'question': State()})
AdminForm = type('AdminForm', (StatesGroup,), {'action': State(), 'data': State()})

from backend.bot import (
    ThrottlingMiddleware,
    db,
    init_db,
    get_role,
    set_role,
    log,
    main_menu,
    show_main,
    start,
    choose_role,
    nav,
    nav_sub,
    contacts,
    sos,
    events,
    question,
    save_question,
    tip,
    poll,
    poll_answer,
    back,
    ADMIN_IDS
)

@pytest.fixture
def mock_db():
    conn = sqlite3.connect(':memory:')
    cur = conn.cursor()
    cur.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, role TEXT)")
    cur.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, category TEXT, title TEXT, content TEXT)")
    cur.execute("CREATE TABLE contacts (id INTEGER PRIMARY KEY, category TEXT, name TEXT, phone TEXT, description TEXT)")
    cur.execute("CREATE TABLE sos_instructions (id INTEGER PRIMARY KEY, text TEXT)")
    cur.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, title TEXT, date TEXT, description TEXT, link TEXT)")
    cur.execute("CREATE TABLE questions (id INTEGER PRIMARY KEY, user_id INTEGER, question TEXT, timestamp TEXT)")
    cur.execute("CREATE TABLE tips (id INTEGER PRIMARY KEY, text TEXT)")
    cur.execute("CREATE TABLE polls (id INTEGER PRIMARY KEY, poll_id TEXT, results TEXT)")
    cur.execute("CREATE TABLE logs (id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, timestamp TEXT)")
    conn.commit()
    with patch('backend.bot.db', return_value=conn):
        yield conn

@pytest.mark.asyncio
async def test_throttling_middleware_allow():
    middleware = ThrottlingMiddleware(rate=10)
    handler = AsyncMock()
    event = MagicMock()
    event.from_user = MagicMock(id=1)
    data = {}
    with patch('asyncio.get_event_loop') as loop_mock:
        loop = MagicMock()
        loop.time.return_value = 0
        loop_mock.return_value = loop
        await middleware(handler, event, data)
    handler.assert_called_once_with(event, data)

@pytest.mark.asyncio
async def test_throttling_middleware_throttle():
    middleware = ThrottlingMiddleware(rate=1)
    handler = AsyncMock()
    event = MagicMock()
    event.from_user = MagicMock(id=1)
    data = {}
    with patch('asyncio.get_event_loop') as loop_mock:
        loop = MagicMock()
        loop.time.side_effect = [0, 0.5]
        loop_mock.return_value = loop
        await middleware(handler, event, data)
        handler.assert_called_once()
        handler.reset_mock()
        await middleware(handler, event, data)
        handler.assert_not_called()

def test_init_db(mock_db):
    cur = mock_db.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]
    assert 'users' in tables
    assert 'articles' in tables

@pytest.mark.asyncio
async def test_get_role_exists(mock_db):
    mock_db.execute("INSERT INTO users VALUES (1, 'teen')")
    mock_db.commit()
    role = await get_role(1)
    assert role == 'teen'

@pytest.mark.asyncio
async def test_get_role_not_exists(mock_db):
    role = await get_role(999)
    assert role is None

@pytest.mark.asyncio
async def test_set_role(mock_db):
    await set_role(1, 'parent')
    cur = mock_db.cursor()
    cur.execute("SELECT role FROM users WHERE user_id=1")
    assert cur.fetchone()[0] == 'parent'

@pytest.mark.asyncio
async def test_log(mock_db):
    await log(1, 'test_action')
    cur = mock_db.cursor()
    cur.execute("SELECT action FROM logs WHERE user_id=1")
    assert cur.fetchone()[0] == 'test_action'

def test_main_menu_non_admin():
    kb = main_menu(1)
    assert len(kb.inline_keyboard) == 7
    assert kb.inline_keyboard[0][0].text == "🧭 Навигатор помощи"

def test_main_menu_admin():
    kb = main_menu(123456789)
    assert len(kb.inline_keyboard) == 8
    assert kb.inline_keyboard[7][0].text == "⚙️ Админ панель"

@pytest.mark.asyncio
async def test_show_main_edit_false_greeting_false():
    msg = MagicMock()
    msg.answer = AsyncMock()
    await show_main(msg, edit=False, greeting=False)
    msg.answer.assert_called_with("Главное меню:", reply_markup=ANY)

@pytest.mark.asyncio
async def test_show_main_edit_true():
    cb = MagicMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.from_user = MagicMock(id=1)
    await show_main(cb, edit=True)
    cb.message.edit_text.assert_called_with("Главное меню:", reply_markup=ANY)

@pytest.mark.asyncio
async def test_show_main_greeting():
    msg = MagicMock()
    msg.answer = AsyncMock()
    await show_main(msg, edit=False, greeting=True)
    msg.answer.assert_called_with("Добро пожаловать в ЦМП бот Томской области! 🌟\n\nВыберите действие:", reply_markup=ANY)

@pytest.mark.asyncio
async def test_start_no_role():
    msg = MagicMock()
    msg.from_user = MagicMock(id=1)
    msg.answer = AsyncMock()
    state = MagicMock()
    state.set_state = AsyncMock()
    with patch('backend.bot.get_role', return_value=None), patch('backend.bot.log'):
        await start(msg, state)
    msg.answer.assert_called_with("Привет 👋 Выбери роль:", reply_markup=ANY)
    state.set_state.assert_called_with(RoleForm.role)

@pytest.mark.asyncio
async def test_start_with_role():
    msg = MagicMock()
    msg.from_user = MagicMock(id=1)
    state = MagicMock()
    with patch('backend.bot.get_role', return_value='teen'), patch('backend.bot.log'), patch('backend.bot.show_main') as mock_show:
        await start(msg, state)
    mock_show.assert_called_with(msg, edit=False)

@pytest.mark.asyncio
async def test_choose_role_teen():
    msg = MagicMock()
    msg.from_user = MagicMock(id=1)
    msg.text = "Я подросток"
    state = MagicMock()
    state.clear = AsyncMock()
    with patch('backend.bot.set_role') as mock_set, patch('backend.bot.show_main') as mock_show:
        await choose_role(msg, state)
    mock_set.assert_called_with(1, "teen")
    state.clear.assert_called()
    mock_show.assert_called_with(msg, edit=False)

@pytest.mark.asyncio
async def test_choose_role_parent():
    msg = MagicMock()
    msg.from_user = MagicMock(id=1)
    msg.text = "Я родитель"
    state = MagicMock()
    state.clear = AsyncMock()
    with patch('backend.bot.set_role') as mock_set, patch('backend.bot.show_main') as mock_show:
        await choose_role(msg, state)
    mock_set.assert_called_with(1, "parent")
    state.clear.assert_called()
    mock_show.assert_called_with(msg, edit=False)

@pytest.mark.asyncio
async def test_nav():
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    with patch('backend.bot.log') as mock_log:
        await nav(cb)
    mock_log.assert_called_with(1, "navigator")
    cb.message.edit_text.assert_called_with("Навигатор помощи:", reply_markup=ANY)

@pytest.mark.asyncio
async def test_nav_sub_with_data(mock_db):
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.data = "help_me"
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    mock_db.execute("INSERT INTO articles VALUES (1, 'help_me_teen', 'Title', 'Content')")
    mock_db.commit()
    with patch('backend.bot.get_role', return_value='teen'):
        await nav_sub(cb)
    cb.message.edit_text.assert_called_with("Title: Content", reply_markup=ANY)

@pytest.mark.asyncio
async def test_nav_sub_no_data():
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.data = "help_me"
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    with patch('backend.bot.get_role', return_value='teen'):
        await nav_sub(cb)
    cb.message.edit_text.assert_called_with("Нет информации 😔", reply_markup=ANY)

@pytest.mark.asyncio
async def test_contacts_with_data(mock_db):
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    mock_db.execute("INSERT INTO contacts VALUES (1, 'cat', 'name', 'phone', 'desc')")
    mock_db.commit()
    with patch('backend.bot.log'):
        await contacts(cb)
    cb.message.edit_text.assert_called_with("cat: name - phone (desc)", reply_markup=ANY)

@pytest.mark.asyncio
async def test_contacts_no_data():
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    with patch('backend.bot.log'):
        await contacts(cb)
    cb.message.edit_text.assert_called_with("Нет контактов 😔", reply_markup=ANY)

@pytest.mark.asyncio
async def test_sos_with_data(mock_db):
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    mock_db.execute("INSERT INTO sos_instructions VALUES (1, 'SOS text')")
    mock_db.commit()
    with patch('backend.bot.log'):
        await sos(cb)
    cb.message.edit_text.assert_called_with("SOS text", reply_markup=ANY)

@pytest.mark.asyncio
async def test_sos_no_data():
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    with patch('backend.bot.log'):
        await sos(cb)
    cb.message.edit_text.assert_called_with("🆘 Звоните 112 или в полицию!", reply_markup=ANY)

@pytest.mark.asyncio
async def test_events_with_data(mock_db):
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    mock_db.execute("INSERT INTO events VALUES (1, 'title', 'date', 'desc', 'link')")
    mock_db.commit()
    with patch('backend.bot.log'):
        await events(cb)
    cb.message.edit_text.assert_called_with("title (date): desc - link", reply_markup=ANY)

@pytest.mark.asyncio
async def test_events_no_data():
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    with patch('backend.bot.log'):
        await events(cb)
    cb.message.edit_text.assert_called_with("Нет мероприятий 📅", reply_markup=ANY)

@pytest.mark.asyncio
async def test_question():
    cb = MagicMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    state = MagicMock()
    state.set_state = AsyncMock()
    await question(cb, state)
    cb.message.edit_text.assert_called_with("Напиши вопрос ❓")
    state.set_state.assert_called_with(QuestionForm.question)

@pytest.mark.asyncio
async def test_save_question(mock_db):
    msg = MagicMock()
    msg.from_user = MagicMock(id=1)
    msg.text = "My question"
    msg.answer = AsyncMock()
    state = MagicMock()
    state.clear = AsyncMock()
    with patch('backend.bot.show_main') as mock_show:
        await save_question(msg, state)
    state.clear.assert_called()
    msg.answer.assert_called_with("Вопрос отправлен 🚀")
    mock_show.assert_called_with(msg, edit=False)
    cur = mock_db.cursor()
    cur.execute("SELECT question FROM questions WHERE user_id=1")
    assert cur.fetchone()[0] == "My question"

@pytest.mark.asyncio
async def test_tip_with_data(mock_db):
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    mock_db.execute("INSERT INTO tips VALUES (1, 'Tip text')")
    mock_db.commit()
    with patch('backend.bot.log'):
        await tip(cb)
    cb.message.edit_text.assert_called_with("Tip text", reply_markup=ANY)

@pytest.mark.asyncio
async def test_tip_no_data():
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    with patch('backend.bot.log'):
        await tip(cb)
    cb.message.edit_text.assert_called_with("Совет дня: улыбайся 😊", reply_markup=ANY)

@pytest.mark.asyncio
async def test_poll():
    cb = MagicMock()
    cb.message = MagicMock()
    cb.message.answer_poll = AsyncMock()
    await poll(cb)
    cb.message.answer_poll.assert_called_with("Что волнует больше?", ["Стресс", "Буллинг", "Цифр. безопасность"], is_anonymous=False)

@pytest.mark.asyncio
async def test_poll_answer(mock_db):
    ans = MagicMock()
    ans.poll_id = "poll1"
    ans.option_ids = [0,1]
    await poll_answer(ans)
    cur = mock_db.cursor()
    cur.execute("SELECT poll_id, results FROM polls")
    row = cur.fetchone()
    assert row[0] == "poll1"
    assert row[1] == "[0, 1]"

@pytest.mark.asyncio
async def test_back():
    cb = MagicMock()
    with patch('backend.bot.show_main') as mock_show:
        await back(cb)
    mock_show.assert_called_with(cb)