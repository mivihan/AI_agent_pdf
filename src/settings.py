"""
Конфигурация и промпты.
"""
import re
from pathlib import Path
from typing import Final

PROJECT_ROOT: Final[Path] = Path(__file__).parent.parent
LOGS_DIR: Final[Path] = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

GIGACHAT_MODEL: Final[str] = "GigaChat"
GIGACHAT_VERIFY_SSL: Final[bool] = False

PRIORITY_PATTERN: Final[re.Pattern] = re.compile(
    r"(?i)(?:контейнер|container|наименование\s+груза|груз|cargo|код|номер|no\.?|№)\s*(?:№|#|:)?\s*([A-Z]{4}[-\s_]?\d{7})\b",
    re.IGNORECASE | re.UNICODE
)

FALLBACK_PATTERN: Final[re.Pattern] = re.compile(
    r"\b([A-Z]{4})[-\s_]?(\d{7})\b",
    re.IGNORECASE
)

VALIDATION_PATTERN: Final[re.Pattern] = re.compile(
    r"^[A-Z]{4}\d{7}$"
)

CONTAINER_KEYWORDS: Final[list[str]] = [
    "контейнер", "container", "наименование груза", "груз", "cargo",
    "код", "номер", "no", "№", "number", "наименование"
]

KNOWN_CONTAINER_PREFIXES: Final[set[str]] = {
    "TEMU", "MSCU", "TKRU", "TGHU", "FCIU", "HLBU", "CMAU", "NYKU",
    "GESU", "TCLU", "WHLU", "PONU", "COSU", "HDMU", "KKFU", "GLDU",
    "TCNU", "SNBU", "BMOU", "DFSU", "SUDU", "APZU", "EISU", "CAXU",
    "MEDU", "OOCU", "TRLU", "INKU", "MSKU", "CRXU", "MRKU", "CXDU"
}

EXCLUDED_PREFIXES: Final[set[str]] = {
    "OKNO", "OKPO", "OGRN", "INN", "КПП"
}

MIN_CONFIDENCE_THRESHOLD: Final[float] = 0.8
MAX_AUTO_CANDIDATES: Final[int] = 1

DEFAULT_MAX_ITERATIONS: Final[int] = 15
AGENT_VERBOSE: Final[bool] = True

LOG_FIELDS: Final[list[str]] = [
    "timestamp",
    "original_path",
    "new_path",
    "extracted_code",
    "method",
    "confidence",
    "note",
    "dry_run"
]

LLM_EXTRACT_PROMPT_TEMPLATE: Final[str] = """Проанализируй текст железнодорожной накладной и извлеки ТОЧНЫЙ КОД КОНТЕЙНЕРА.

⚠️ КРИТИЧЕСКИ ВАЖНО:
- Верни ТОЛЬКО тот код, который РЕАЛЬНО ПРИСУТСТВУЕТ в тексте
- НЕ ВЫДУМЫВАЙ коды! Если не уверен - верни пустой результат
- НЕ используй примеры типа "1234567" - только реальные данные из текста

ТРЕБОВАНИЯ К КОДУ:
- Формат: 4 ЗАГЛАВНЫЕ латинские буквы + 7 цифр (всего 11 символов)
- Примеры правильных: TKRU3535802, MSCU9876543, TEMU4512367
- Примеры НЕПРАВИЛЬНЫХ: TEMU1234567 (это шаблон, не реальный код!)

ГДЕ ИСКАТЬ:
- Раздел "НАИМЕНОВАНИЕ ГРУЗА"
- Рядом со словами "контейнер", "container"
- В списках кодов/номеров

ЧТО ИГНОРИРОВАТЬ:
- ОКПО, ОГРН, ИНН, КПП (это НЕ коды контейнеров!)
- Номера накладных, счетов
- Телефоны, даты

ТЕКСТ ДОКУМЕНТА:
{text}

ИНСТРУКЦИИ:
1. Внимательно прочитай текст
2. Найди код формата AAAA1234567, который РЕАЛЬНО есть в тексте
3. Убедись, что это именно код контейнера (есть рядом ключевые слова)
4. Верни ТОЛЬКО JSON:

{{"code": "TKRU3535802", "confidence": 0.95, "reason": "найден в 'НАИМЕНОВАНИЕ ГРУЗА', строка: '...TKRU3535802...'"}}

Если НЕ НАЙДЕН или НЕ УВЕРЕН - обязательно верни:
{{"code": "", "confidence": 0.0, "reason": "код контейнера не обнаружен в тексте"}}

НЕ ВЫДУМЫВАЙ! Только реальные данные из текста!

Твой ответ (только JSON):"""

TESSERACT_CONFIG: Final[str] = "--oem 3 --psm 6"
PDF_DPI: Final[int] = 300