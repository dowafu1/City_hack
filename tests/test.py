import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, ANY
import sqlite3
from datetime import datetime, timedelta

from aiogram.fsm.state import StatesGroup, State


class MockTypes:
    Message = MagicMock
    CallbackQuery = MagicMock
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
    update_data = AsyncMock
    get_data = AsyncMock


FSMContext = MockFSMContext

RoleForm = type('RoleForm', (StatesGroup,), {'role': State()})
QuestionForm = type('QuestionForm', (StatesGroup,), {'question': State()})
AdminForm = type('AdminForm', (StatesGroup,), {'section': State(), 'payload': State()})

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
    sub,
    admin,
    admin_pick,
    admin_save,
    back,
    notifier,
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
    cur.execute("CREATE TABLE subs (user_id INTEGER PRIMARY KEY, next_at TEXT)")
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
    with patch('asyncio.get_running_loop') as loop_mock:
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
    with patch('asyncio.get_running_loop') as loop_mock:
        loop = MagicMock()
        loop.time.side_effect = [0, 0.5]  # Two calls within 1 second
        loop_mock.return_value = loop
        await middleware(handler, event, data)  # First call passes
        handler.reset_mock()
        await middleware(handler, event, data)  # Second call should be throttled
        handler.assert_not_called()


def test_init_db(mock_db):
    cur = mock_db.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]
    assert 'users' in tables
    assert 'articles' in tables
    assert 'subs' in tables


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
    assert len(kb.inline_keyboard) == 8
    assert kb.inline_keyboard[0][0].text == "🧭 Навигатор помощи"


def test_main_menu_admin():
    kb = main_menu(123456789)
    assert len(kb.inline_keyboard) == 9
    assert kb.inline_keyboard[8][0].text == "⚙️ Админ панель"


@pytest.mark.asyncio
async def test_show_main_edit_false_greeting_false():
    msg = MagicMock()
    msg.answer = AsyncMock()
    await show_main(msg, edit=False, greeting=False)
    msg.answer.assert_called_once()


@pytest.mark.asyncio
async def test_show_main_edit_true():
    cb = MagicMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.from_user = MagicMock(id=1)
    await show_main(cb, edit=True)
    cb.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_show_main_greeting():
    msg = MagicMock()
    msg.answer = AsyncMock()
    await show_main(msg, edit=False, greeting=True)
    msg.answer.assert_called_once()


@pytest.mark.asyncio
async def test_start_no_role():
    msg = MagicMock()
    msg.from_user = MagicMock(id=1)
    msg.answer = AsyncMock()
    state = MagicMock()
    state.set_state = AsyncMock()
    with patch('backend.bot.get_role', return_value=None), patch('backend.bot.log'):
        await start(msg, state)
    msg.answer.assert_called_once()
    state.set_state.assert_called_with(RoleForm.role)


@pytest.mark.asyncio
async def test_start_with_role():
    msg = MagicMock()
    msg.from_user = MagicMock(id=1)
    state = MagicMock()
    with patch('backend.bot.get_role', return_value='teen'), patch('backend.bot.log'), patch(
            'backend.bot.show_main') as mock_show:
        await start(msg, state)
    mock_show.assert_called_with(msg, edit=False, greeting=True)


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
    cb.message.edit_text.assert_called_once()


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
    cb.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_nav_sub_no_data():
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.data = "help_me"
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    with patch('backend.bot.get_role', return_value='teen'):
        await nav_sub(cb)
    cb.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_contacts_with_data(mock_db):
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    mock_db.execute("INSERT INTO contacts VALUES (1, 'cat', 'name', '+7(123)456-78-90', 'desc')")
    mock_db.commit()
    with patch('backend.bot.log'):
        await contacts(cb)
    cb.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_contacts_no_data():
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    with patch('backend.bot.log'):
        await contacts(cb)
    cb.message.edit_text.assert_called_once()


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
    cb.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_sos_no_data():
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    with patch('backend.bot.log'):
        await sos(cb)
    cb.message.edit_text.assert_called_once()


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
    cb.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_events_no_data():
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    with patch('backend.bot.log'):
        await events(cb)
    cb.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_question():
    cb = MagicMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    state = MagicMock()
    state.set_state = AsyncMock()
    await question(cb, state)
    cb.message.edit_text.assert_called_once()
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
    msg.answer.assert_called_once()
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
    cb.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_tip_no_data():
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    with patch('backend.bot.log'):
        await tip(cb)
    cb.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_poll():
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    with patch('backend.bot.log'):
        await poll(cb)
    cb.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_sub_subscribe(mock_db):
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.answer = AsyncMock()
    with patch('backend.bot.show_main') as mock_show, patch('datetime.datetime') as mock_dt:
        mock_now = datetime(2023, 1, 1)
        mock_dt.now.return_value = mock_now
        await sub(cb)
    cb.answer.assert_called_with("Буду присылать советы раз в день")
    mock_show.assert_called_with(cb)
    cur = mock_db.cursor()
    cur.execute("SELECT next_at FROM subs WHERE user_id=1")
    next_at = cur.fetchone()[0]
    expected = (mock_now + timedelta(days=1)).isoformat()
    assert next_at == expected


@pytest.mark.asyncio
async def test_sub_unsubscribe(mock_db):
    cb = MagicMock()
    cb.from_user = MagicMock(id=1)
    cb.answer = AsyncMock()
    mock_db.execute("INSERT INTO subs VALUES (1, '2023-01-01T00:00:00')")
    mock_db.commit()
    with patch('backend.bot.show_main') as mock_show:
        await sub(cb)
    cb.answer.assert_called_with("Подписка отключена")
    mock_show.assert_called_with(cb)
    cur = mock_db.cursor()
    cur.execute("SELECT * FROM subs WHERE user_id=1")
    assert cur.fetchone() is None


@pytest.mark.asyncio
async def test_admin_non_admin():
    cb = MagicMock()
    cb.from_user = MagicMock(id=999)
    state = MagicMock()
    await admin(cb, state)
    cb.message.edit_text.assert_not_called()


@pytest.mark.asyncio
async def test_admin():
    cb = MagicMock()
    cb.from_user = MagicMock(id=123456789)
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    state = MagicMock()
    state.set_state = AsyncMock()
    await admin(cb, state)
    cb.message.edit_text.assert_called_once()
    state.set_state.assert_called_with(AdminForm.section)


@pytest.mark.asyncio
async def test_admin_pick_non_admin():
    cb = MagicMock()
    cb.from_user = MagicMock(id=999)
    state = MagicMock()
    await admin_pick(cb, state)
    cb.message.edit_text.assert_not_called()


@pytest.mark.asyncio
async def test_admin_pick_contacts():
    cb = MagicMock()
    cb.from_user = MagicMock(id=123456789)
    cb.data = "ad_contacts"
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    state = MagicMock()
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    await admin_pick(cb, state)
    cb.message.edit_text.assert_called_once()
    state.update_data.assert_called_with(section="ad_contacts")
    state.set_state.assert_called_with(AdminForm.payload)


@pytest.mark.asyncio
async def test_admin_save_non_admin():
    msg = MagicMock()
    msg.from_user = MagicMock(id=999)
    state = MagicMock()
    await admin_save(msg, state)
    msg.answer.assert_not_called()


@pytest.mark.asyncio
async def test_admin_save_contacts_valid(mock_db):
    msg = MagicMock()
    msg.from_user = MagicMock(id=123456789)
    msg.text = "cat|name|+7(123)456-78-90|desc"
    msg.answer = AsyncMock()
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"section": "ad_contacts"})
    state.clear = AsyncMock()
    with patch('backend.bot.show_main') as mock_show:
        await admin_save(msg, state)
    msg.answer.assert_called_with("Сохранено")
    state.clear.assert_called()
    mock_show.assert_called_with(msg, edit=False)
    cur = mock_db.cursor()
    cur.execute("SELECT category, name, phone, description FROM contacts")
    assert cur.fetchone() == ("cat", "name", "+7(123)456-78-90", "desc")


@pytest.mark.asyncio
async def test_admin_save_contacts_invalid(mock_db):
    msg = MagicMock()
    msg.from_user = MagicMock(id=123456789)
    msg.text = "invalid"
    msg.answer = AsyncMock()
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"section": "ad_contacts"})
    state.clear = AsyncMock()
    await admin_save(msg, state)
    msg.answer.assert_called_with("Неверный формат")
    state.clear.assert_not_called()


@pytest.mark.asyncio
async def test_admin_save_sos(mock_db):
    msg = MagicMock()
    msg.from_user = MagicMock(id=123456789)
    msg.text = "New SOS text"
    msg.answer = AsyncMock()
    state = MagicMock()
    state.get_data = AsyncMock(return_value={"section": "ad_sos"})
    state.clear = AsyncMock()
    with patch('backend.bot.show_main') as mock_show:
        await admin_save(msg, state)
    msg.answer.assert_called_with("Сохранено")
    state.clear.assert_called()
    mock_show.assert_called_with(msg, edit=False)
    cur = mock_db.cursor()
    cur.execute("SELECT text FROM sos_instructions")
    assert cur.fetchone()[0] == "New SOS text"


@pytest.mark.asyncio
async def test_back():
    cb = MagicMock()
    with patch('backend.bot.show_main') as mock_show:
        await back(cb)
    mock_show.assert_called_with(cb)


@pytest.mark.asyncio
async def test_notifier_with_sub_and_tip(mock_db):
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    with patch('backend.bot.bot', mock_bot), patch('asyncio.sleep', new_callable=AsyncMock), patch(
            'datetime.datetime') as mock_dt:
        mock_now = datetime(2023, 1, 1)
        mock_dt.now.return_value = mock_now
        mock_dt.fromisoformat.side_effect = datetime.fromisoformat

        mock_db.execute("INSERT INTO subs VALUES (1, '2023-01-01T00:00:00')")
        mock_db.execute("INSERT INTO tips VALUES (1, 'Tip text')")
        mock_db.commit()

        notifier_task = asyncio.create_task(notifier())
        await asyncio.sleep(0.1)

        mock_bot.send_message.assert_called_once()
        cur = mock_db.cursor()
        cur.execute("SELECT next_at FROM subs WHERE user_id=1")
        assert cur.fetchone()[0] == (mock_now + timedelta(days=1)).isoformat()

        notifier_task.cancel()