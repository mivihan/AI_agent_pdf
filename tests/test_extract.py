import pytest

from src.tools import normalize_code, regex_extract_code

"""
Юнит-тесты для функций извлечения и нормализации кодов
"""


class TestNormalizeCode:
    """Тесты для нормализации кодов контейнеров."""
    
    def test_simple_code(self):
        """Простой код без разделителей (4 буквы + 7 цифр)."""
        assert normalize_code("ABCD1234567") == "ABCD1234567"
        assert normalize_code("abcd1234567") == "ABCD1234567"
        assert normalize_code("MSCU9876543") == "MSCU9876543"
    
    def test_code_with_separators(self):
        """Код с разделителями."""
        assert normalize_code("ABCD-1234567") == "ABCD1234567"
        assert normalize_code("ABCD_1234567") == "ABCD1234567"
        assert normalize_code("ABCD 1234567") == "ABCD1234567"
        assert normalize_code("MSCU-9876543") == "MSCU9876543"
    
    def test_lowercase(self):
        """Приведение к верхнему регистру."""
        assert normalize_code("abcd1234567") == "ABCD1234567"
        assert normalize_code("mscu-9876543") == "MSCU9876543"
        assert normalize_code("TeMu1234567") == "TEMU1234567"
    
    def test_invalid_format(self):
        """Невалидные форматы."""
        assert normalize_code("ABC1234567").startswith("ERROR")
        assert normalize_code("ABCDE1234567").startswith("ERROR")

        assert normalize_code("ABCD123456").startswith("ERROR")
        assert normalize_code("ABCD12345678").startswith("ERROR")

        assert normalize_code("").startswith("ERROR")

        assert normalize_code("UI77").startswith("ERROR")
        assert normalize_code("MSK456").startswith("ERROR")
    
    def test_exact_format(self):
        """Проверка точного формата: 4 буквы + 7 цифр"""
        assert normalize_code("ABCD1234567") == "ABCD1234567"
        assert normalize_code("AAAA0000000") == "AAAA0000000"
        assert normalize_code("ZZZZ9999999") == "ZZZZ9999999"

        assert normalize_code("ABC1234567").startswith("ERROR")
        assert normalize_code("ABCDE1234567").startswith("ERROR")
        assert normalize_code("ABCD123456").startswith("ERROR")
        assert normalize_code("ABCD12345678").startswith("ERROR")


class TestRegexExtractCode:
    """Тесты для извлечения кодов регулярными выражениями."""
    
    def test_priority_pattern_with_keyword(self):
        """Извлечение с ключевым словом (приоритет)."""
        text = "Контейнер № ABCD1234567 был доставлен"
        result = regex_extract_code(text)
        assert result["code"] == "ABCD1234567"
        assert result["confidence"] > 0.8
        assert len(result["candidates"]) >= 1
    
    def test_multiple_keywords(self):
        """Несколько ключевых слов."""
        texts = [
            "Код контейнера: MSCU9876543",
            "Container number TEMU1234567",
            "Номер: ABCD1111111",
            "Container № ZZZZ9999999"
        ]
        
        expected_codes = ["MSCU9876543", "TEMU1234567", "ABCD1111111", "ZZZZ9999999"]
        
        for text, expected in zip(texts, expected_codes):
            result = regex_extract_code(text)
            assert result["code"] == expected, f"Ожидался {expected}, получен {result['code']}"
            assert result["confidence"] > 0.5
    
    def test_fallback_pattern(self):
        """Fallback без ключевых слов."""
        text = "Документ ABCD1234567 от 01.01.2024"
        result = regex_extract_code(text)
        assert result["code"] == "ABCD1234567"
        assert len(result["candidates"]) >= 1
    
    def test_with_separators_in_text(self):
        """Коды с разделителями в тексте."""
        texts = [
            "Контейнер ABCD-1234567",
            "Container MSCU_9876543",
            "Код TEMU 1234567"
        ]
        
        expected = ["ABCD1234567", "MSCU9876543", "TEMU1234567"]
        
        for text, exp in zip(texts, expected):
            result = regex_extract_code(text)
            assert result["code"] == exp, f"Текст: '{text}', ожидался {exp}, получен {result['code']}"
    
    def test_multiple_candidates(self):
        """Несколько кандидатов (выбор лучшего)."""
        text = "Коды: AAAA1111111, BBBB2222222, контейнер № CCCC3333333"
        result = regex_extract_code(text)
        assert result["code"] == "CCCC3333333"
        assert len(result["candidates"]) >= 3
    
    def test_no_match(self):
        """Код не найден."""
        text = "Обычный текст без кодов контейнеров"
        result = regex_extract_code(text)
        assert result["code"] == ""
        assert result["confidence"] == 0.0
        assert len(result["candidates"]) == 0
    
    def test_old_format_ignored(self):
        """Старые форматы (2-3 буквы) должны игнорироваться."""
        texts = [
            "Контейнер UI77",
            "MSK456",
            "AB123456"
        ]
        
        for text in texts:
            result = regex_extract_code(text)
            assert result["code"] == "", f"Старый формат не должен проходить: {text}"
    
    def test_empty_text(self):
        """Пустой текст."""
        result = regex_extract_code("")
        assert result["code"] == ""
        assert result["confidence"] == 0.0
    
    def test_case_insensitive(self):
        """Регистронезависимый поиск."""
        texts = [
            "КОНТЕЙНЕР № abcd1234567",
            "Container: MsCu9876543",
            "КОД tEmU1234567"
        ]
        
        expected = ["ABCD1234567", "MSCU9876543", "TEMU1234567"]
        
        for text, exp in zip(texts, expected):
            result = regex_extract_code(text)
            assert result["code"] == exp
            assert result["code"].isupper()