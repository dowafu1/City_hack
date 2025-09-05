import os
import json
from unittest.mock import patch, mock_open
from pathlib import Path

import pytest

from backend.config import Config, PresetManager, WELCOME_TEXT, INFO_TEXT



def test_load_env_success(tmp_path):
    # Создаем временный .env файл
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("BOT_TOKEN=12345\nSBER_TOKEN=abc\nMISTRAL_TOKEN=xyz\nADMIN_IDS=123,456")

    with patch("config.Path.__truediv__", return_value=dotenv_path):
        with patch("config.load_dotenv") as mock_load_dotenv:
            Config.load_env()
            mock_load_dotenv.assert_called_once_with(dotenv_path)


def test_load_env_missing_file():
    with patch("config.Path.__truediv__", return_value=Path("/nonexistent/.env")):
        with pytest.raises(SystemExit):
            Config.load_env()


@patch.dict(os.environ, {
    "BOT_TOKEN": "12345",
    "SBER_TOKEN": "abc",
    "MISTRAL_TOKEN": "xyz",
    "ADMIN_IDS": "123,456"
})
def test_get_required_env_vars_success():
    bot_token, sber_token, mistral_token, admin_ids = Config.get_required_env_vars()
    assert bot_token == "12345"
    assert sber_token == "abc"
    assert mistral_token == "xyz"
    assert admin_ids == {123, 456}


@patch.dict(os.environ, {"BOT_TOKEN": ""})
def test_get_required_env_vars_missing_bot_token():
    with pytest.raises(ValueError, match="❌ Необходимо задать BOT_TOKEN в .env"):
        Config.get_required_env_vars()


def test_load_presets_success():
    mock_data = {
        "gigachat_prompt": "Custom prompt 1",
        "mistral_summarize_prompt": "Custom prompt 2",
        "tip_prompt": "Custom prompt 3"
    }
    with patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
        result = PresetManager.load_presets()
        assert result == mock_data


def test_load_presets_file_not_found():
    with patch("builtins.open", side_effect=FileNotFoundError()):
        result = PresetManager.load_presets()
        assert result == PresetManager.DEFAULT_PRESETS


def test_load_presets_invalid_json():
    with patch("builtins.open", mock_open(read_data="invalid json")):
        result = PresetManager.load_presets()
        assert result == PresetManager.DEFAULT_PRESETS

def test_welcome_text_exists():
    assert isinstance(WELCOME_TEXT, str)
    assert "Цифровой помощник" in WELCOME_TEXT


def test_info_text_exists():
    assert isinstance(INFO_TEXT, str)
    assert "Тревожная кнопка" in INFO_TEXT