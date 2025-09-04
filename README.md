<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ЦМП Томской области – Telegram-бот</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1, h2, h3 {
            border-bottom: 1px solid #eaecef;
            padding-bottom: 0.3em;
        }
        a {
            color: #0366d6;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        ul, ol {
            padding-left: 2em;
        }
        code {
            background-color: #f6f8fa;
            padding: 0.2em 0.4em;
            border-radius: 3px;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        }
        pre {
            background-color: #f6f8fa;
            padding: 16px;
            overflow: auto;
            border-radius: 3px;
        }
        pre code {
            background-color: transparent;
            padding: 0;
        }
        blockquote {
            margin: 0;
            padding: 0 1em;
            color: #6a737d;
            border-left: 0.25em solid #dfe2e5;
        }
        hr {
            border: 0;
            border-top: 1px solid #eaecef;
            margin: 24px 0;
        }
        table {
            border-collapse: collapse;
            border-spacing: 0;
            margin-bottom: 16px;
        }
        th, td {
            padding: 6px 13px;
            border: 1px solid #dfe2e5;
        }
        th {
            font-weight: 600;
            background-color: #f6f8fa;
        }
    </style>
</head>
<body>

<h1 id="-цмп-томской-области--telegram-бот-"><strong>ЦМП Томской области – Telegram-бот</strong> 🚀</h1>

<p>Телеграм-бот для психологической помощи, информирования и связи с Центром молодежной политики Томской области. 🌟</p>

<h2 id="-содержание">📋 Содержание</h2>

<ul>
    <li><a href="#-возможности">Возможности</a></li>
    <li><a href="#-навигация-в-боте">Навигация в боте</a></li>
    <li><a href="#-админ-панель">Админ-панель</a></li>
    <li><a href="#-ai-интеграция">AI-интеграция</a></li>
    <li><a href="#-структура-проекта">Структура проекта</a></li>
    <li><a href="#-технологии">Технологии</a></li>
    <li><a href="#-установка-и-запуск">Установка и запуск</a></li>
    <li><a href="#-переменные-окружения">Переменные окружения</a></li>
    <li><a href="#-структура-бд">Структура БД</a></li>
    <li><a href="#-логи-и-троттлинг">Логи и троттлинг</a></li>
    <li><a href="#-тестирование">Тестирование</a></li>
    <li><a href="#-команда">Команда</a></li>
</ul>

<hr>

<h2 id="-возможности">🚀 Возможности</h2>

<h3 id="1-куда-обратиться-контакты-">1. Куда обратиться (контакты) 📞</h3>
<ul>
    <li>Список контактов служб: категория, название, телефон, описание.</li>
    <li>Источник: таблица <code>contacts</code>.</li>
    <li>⚠️ Контакты выводятся текстом без интерактивных кнопок.</li>
</ul>

<h3 id="2-тревожная-кнопка-sos-️">2. Тревожная кнопка (SOS) 🆘</h3>
<ul>
    <li>Инструкция из таблицы <code>sos_instructions</code>. Если пусто: «Звоните 112 или 102…».</li>
    <li>Постоянная кнопка внизу интерфейса.</li>
</ul>

<h3 id="3-навигатор-помощи-️">3. Навигатор помощи 🧭</h3>
<ul>
    <li>Разделы для подростков и родителей:
        <ul>
            <li>Депрессивные настроения 😔</li>
            <li>Суицидальные мысли ⚠️</li>
            <li>Агрессия и раздражение 💢</li>
            <li>Проблемы с едой 🍽️</li>
            <li>Половое воспитание 🫂</li>
            <li>Сложности в общении 👥</li>
            <li>Другое — хочу поговорить 💬</li>
        </ul>
    </li>
    <li>Контент из таблицы <code>articles</code> по категориям: <code>help_me_&lt;role&gt;</code>, <code>report_&lt;role&gt;</code>, <code>other_&lt;role&gt;</code> (<code>role</code>: <code>teen</code>, <code>adult</code>).</li>
</ul>

<h3 id="4-анонсы-мероприятий-">4. Анонсы мероприятий 📅</h3>
<ul>
    <li>Список событий из <code>events</code>: название, дата, описание, ссылка.</li>
    <li>Уведомления не реализованы.</li>
</ul>

<h3 id="5-совет-дня--подписка-️">5. Совет дня / Подписка 💡</h3>
<ul>
    <li>Кнопка «Подписаться на поддержку» добавляет в <code>subs</code>, отправка совета раз в день.</li>
    <li>Фоновый таск <code>notifier()</code> управляет рассылкой.</li>
    <li>Повторное нажатие отключает подписку.</li>
    <li>Советы из <code>tips</code>. Если пусто — дефолтный текст.</li>
    <li>Возможна генерация советов через AI.</li>
</ul>

<h3 id="6-обратная-связь-вопрос-️">6. Обратная связь (вопрос) ❓</h3>
<ul>
    <li>Пользователь вводит вопрос, сохраняется в <code>questions</code> с <code>user_id</code> и timestamp.</li>
    <li>Пересылка экспертам не реализована, но чат логируется для AI.</li>
</ul>

<h3 id="7-опросы-️">7. Опросы 📊</h3>
<ul>
    <li>Раздел есть, но показывает «Пока опросов нет».</li>
</ul>

<h3 id="8-роли-пользователей-️">8. Роли пользователей 👥</h3>
<ul>
    <li>При <code>/start</code> выбор: «Я подросток» или «Я взрослый». Роль влияет на контент.</li>
</ul>

<h3 id="9-хранение-истории-чата-️">9. Хранение истории чата 📝</h3>
<ul>
    <li>Сообщения логируются в <code>chat_history</code> для анализа и AI-обработки.</li>
</ul>

<hr>

<h2 id="-навигация-в-боте">🧭 Навигация в боте</h2>

<ul>
    <li><code>/start</code>: приветствие и выбор роли. Главное меню:
        <ul>
            <li>🆘 Тревожная кнопка</li>
            <li>🧭 Мне нужна помощь</li>
            <li>🤖 Поддержка (с использованием ИИ)</li>
            <li>📞 Куда обратиться?</li>
            <li>❓ Задать вопрос</li>
            <li>📅 Мероприятия</li>
            <li>💡 Получить совет</li>
            <li>🔔 Подписаться на поддержку</li>
            <li>🔄 Изменить роль</li>
            <li>🛠️ Админ-панель (для <code>ADMIN_IDS</code>)</li>
        </ul>
    </li>
</ul>

<hr>

<h2 id="-админ-панель">🛡️ Админ-панель</h2>

<p>Доступ для пользователей из <code>ADMIN_IDS</code>. Форматы ввода:</p>

<ul>
    <li><strong>Контакты (<code>ad_contacts</code>)</strong>: <code>category|name|+7(XXX)XXX-XX-XX|description</code></li>
    <li><strong>SOS (<code>ad_sos</code>)</strong>: любой текст, перезаписывает инструкцию.</li>
    <li><strong>Событие (<code>ad_event</code>)</strong>: <code>title|YYYY-MM-DD|description|link</code></li>
    <li><strong>Статья (<code>ad_article</code>)</strong>: <code>category|title|content</code></li>
    <li><strong>Совет (<code>ad_tip</code>)</strong>: любой текст.</li>
</ul>

<p>Операции подтверждаются: «✅ Сохранено» или «❌ Неверный формат».</p>

<hr>

<h2 id="-ai-интеграция">🤖 AI-интеграция</h2>

<ul>
    <li><strong>Цепочка AI (<code>ai_chain.py</code>)</strong>:
        <ul>
            <li><code>chainize()</code>: генерирует ответ через Sber AI, улучшает через Mistral AI.</li>
            <li><code>get_tip()</code>: создаёт советы на основе предыдущих (Sber AI).</li>
        </ul>
    </li>
    <li><strong>Использование</strong>: тестируется, не интегрировано в бот. Для генерации контента админами.</li>
    <li><strong>Библиотеки</strong>: langchain-gigachat, mistralai.</li>
    <li><strong>Переменные</strong>: <code>SBER_TOKEN</code>, <code>MISTRAL_TOKEN</code>.</li>
    <li><strong>Дополнительно</strong>: папка <code>ai/context/</code> для контекстных файлов (например, промпты). Поддержка других нейросетей возможна через API.</li>
</ul>

<hr>

<h2 id="-структура-проекта">🏗️ Структура проекта</h2>

<p>Модульная структура для удобства разработки и тестирования:</p>

<ul>
    <li><strong>ai/</strong> 📁 — AI-интеграции и цепочки обработки.
        <ul>
            <li><code>__init__.py</code></li>
            <li><code>ai_chain.py</code> — функции <code>chainize</code> и <code>get_tip</code>.</li>
            <li><code>mistral_ai.py</code> — интеграция с Mistral AI.</li>
            <li><code>sber_ai.py</code> — интеграция с Sber AI (GigaChat).</li>
            <li><strong>context/</strong> 📁 — файлы для AI-контекста (например, промпты, данные для анализа).</li>
        </ul>
    </li>
    <li><strong>backend/</strong> 📁 — backend бота и базы данных.
        <ul>
            <li><code>__init__.py</code></li>
            <li><code>bot.py</code> — логика бота (aiogram, FSM, обработчики).</li>
            <li><code>db.py</code> — работа с PostgreSQL (asyncpg, CRUD).</li>
        </ul>
    </li>
    <li><strong>tests/</strong> 📁 — unit-тесты.
        <ul>
            <li><code>test.py</code> — тесты бота и AI.</li>
            <li><code>test_DB.py</code> — тесты базы данных.</li>
        </ul>
    </li>
    <li><strong>Корневые файлы</strong>:
        <ul>
            <li><code>README.md</code> — документация.</li>
            <li><code>requirements.txt</code> — зависимости.</li>
            <li><code>.env</code> — переменные окружения (не коммитится).</li>
        </ul>
    </li>
</ul>

<p>Эта структура разделяет логику AI, бота и тестов, упрощая масштабирование и отладку.</p>

<hr>

<h2 id="-тестирование">🧪 Тестирование</h2>

<h3 id="тесты">Тесты</h3>
<p>Unit-тесты (pytest) для:</p>
<ul>
    <li><strong>Middleware</strong>: троттлинг, ограничение запросов.</li>
    <li><strong>БД</strong>: создание таблиц, CRUD, роли, логи.</li>
    <li><strong>Обработчики</strong>: <code>/start</code>, выбор роли, навигатор, админ-панель, подписка, вопросы, AI.</li>
    <li><strong>Валидация</strong>: формат телефона, даты, обработка ошибок.</li>
    <li><strong>FSM</strong>: состояния админ-панели.</li>
</ul>

<h3 id="результаты">Результаты</h3>
<ul>
    <li>Все тесты успешны (100% pass rate).</li>
    <li>Покрытие кода: 87% (coverage.py).</li>
</ul>

<hr>

<h2 id="-технологии">🛠️ Технологии</h2>

<ul>
    <li><strong>Язык</strong>: Python 3.11+</li>
    <li><strong>Фреймворк</strong>: aiogram 3.x</li>
    <li><strong>Хранилище</strong>: PostgreSQL (asyncpg)</li>
    <li><strong>FSM</strong>: aiogram.fsm + MemoryStorage</li>
    <li><strong>AI</strong>: langchain-gigachat, mistralai</li>
    <li><strong>Другое</strong>: python-dotenv, asyncpg, pytest</li>
</ul>

<hr>

<h2 id="-установка-и-запуск">📦 Установка и запуск</h2>

<h3 id="требования">Требования</h3>
<ul>
    <li>Python 3.11+</li>
    <li>Git</li>
    <li>PostgreSQL</li>
</ul>

<h3 id="клонирование">Клонирование</h3>
<pre><code class="language-bash">git clone https://github.com/dowafu1/City_hack.git
cd City_hack
</code></pre>

<h3 id="виртуальное-окружение">Виртуальное окружение</h3>
<pre><code class="language-bash">python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
</code></pre>

<h3 id="переменные-окружения">Переменные окружения</h3>
<p>Создайте <code>.env</code> в корне:</p>
<pre><code class="language-env">BOT_TOKEN=123456789:AA...
ADMIN_IDS=123456789,987654321
SBER_TOKEN=your_sber_token
MISTRAL_TOKEN=your_mistral_token
DB_HOST=localhost
DB_PORT=5432
DB_USER=your_db_user
DB_PASS=your_db_pass
DB_NAME=cmp_bot
</code></pre>

<h3 id="запуск">Запуск</h3>
<pre><code class="language-bash">python bot.py
</code></pre>
<blockquote>
<p>Таблицы создаются автоматически. База данных должна быть создана заранее.</p>
</blockquote>

<hr>

<h2 id="-переменные-окружения">🔧 Переменные окружения</h2>

<ul>
    <li><code>BOT_TOKEN</code> — обязательна</li>
    <li><code>ADMIN_IDS</code> — необязательна</li>
    <li><code>SBER_TOKEN</code> — для Sber AI</li>
    <li><code>MISTRAL_TOKEN</code> — для Mistral AI</li>
    <li><code>DB_HOST</code>, <code>DB_PORT</code>, <code>DB_USER</code>, <code>DB_PASS</code>, <code>DB_NAME</code> — для PostgreSQL (дефолты: localhost:5432, user=текущий логин, pass=&quot;&quot;, db=cmp_bot)</li>
</ul>

<hr>

<h2 id="-структура-бд">🗄️ Структура БД</h2>

<p>Таблицы создаются в <code>init_db()</code>:</p>
<ul>
    <li><code>users(user_id PK, role)</code></li>
    <li><code>articles(id PK, category, title, content)</code></li>
    <li><code>contacts(id PK, category, name, phone, description)</code></li>
    <li><code>sos_instructions(id PK, text)</code></li>
    <li><code>events(id PK, title, date, description, link)</code></li>
    <li><code>questions(id PK, user_id, question, timestamp)</code></li>
    <li><code>tips(id PK, text)</code></li>
    <li><code>polls(id PK, poll_id, results)</code></li>
    <li><code>logs(id PK, user_id, action, timestamp)</code></li>
    <li><code>subs(user_id PK, next_at)</code></li>
    <li><code>chat_history(id PK, chat_id, role, content, timestamp)</code></li>
</ul>

<hr>

<h2 id="-логи-и-троттлинг">📈 Логи и троттлинг</h2>

<ul>
    <li><strong>Логи</strong>: действия (<code>start</code>, переходы, советы) в <code>logs</code>.</li>
    <li><strong>История чата</strong>: сообщения в <code>chat_history</code> (роли: <code>user</code>, <code>ai</code>).</li>
    <li><strong>Троттлинг</strong>: ~10 запросов/сек на пользователя через <code>ThrottlingMiddleware</code>.</li>
</ul>

<hr>

<h2 id="-команда">👥 Команда</h2>

<ul>
    <li>Даниил Татарников — Тимлид, Backend-разработчик</li>
    <li>Шевченко Егор — ML-инженер, Backend-разработчик, Тестировщик</li>
    <li>Щилко Максим — ML-инженер, Backend-разработчик</li>
    <li>Дарья Климова — Frontend-разработчик, Аналитик, Дизайнер</li>
</ul>

</body>
</html>