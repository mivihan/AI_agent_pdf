"""
Инструменты для агента переименования PDF.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber
import pytesseract
from langchain.tools import tool
from pdf2image import convert_from_path
from pydantic import BaseModel, Field

if sys.platform == "win32":
    tesseract_exe = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if tesseract_exe.exists():
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_exe)

from src.settings import (
    CONTAINER_KEYWORDS,
    FALLBACK_PATTERN,
    LOG_FIELDS,
    MIN_CONFIDENCE_THRESHOLD,
    PDF_DPI,
    PRIORITY_PATTERN,
    TESSERACT_CONFIG,
    VALIDATION_PATTERN,
)

def _calculate_confidence(
    candidates: list[str], text: str, method: str = "regex"
) -> tuple[str, float, str]:
    '''
    Вычисляет наиболее вероятный код и уверенность.
    Приоритизирует известные префиксы контейнеров.
    '''
    from src.settings import KNOWN_CONTAINER_PREFIXES, EXCLUDED_PREFIXES, CONTAINER_KEYWORDS
    
    if not candidates:
        return "", 0.0, "кандидаты не найдены"
    
    if len(candidates) == 1:
        code = candidates[0]
        prefix = code[:4].upper()
        
        if prefix in EXCLUDED_PREFIXES:
            return "", 0.0, f"код {code} исключён (префикс {prefix} не является контейнером)"
        
        if prefix in KNOWN_CONTAINER_PREFIXES:
            return code, 0.98, f"известный префикс контейнера {prefix}"
        
        return code, 0.85, f"единственный кандидат ({method})"
    
    scored = []
    text_lower = text.lower()
    
    for code in candidates:
        prefix = code[:4].upper()
        
        if prefix in EXCLUDED_PREFIXES:
            continue
        
        score = 0.3
        
        if prefix in KNOWN_CONTAINER_PREFIXES:
            score += 0.5
        
        for keyword in CONTAINER_KEYWORDS:
            keyword_pos = text_lower.find(keyword)
            if keyword_pos != -1:
                code_pos = text_lower.find(code.lower())
                if code_pos != -1 and abs(keyword_pos - code_pos) < 100:
                    score += 0.3
                    
                    if "груз" in keyword or "cargo" in keyword or "наименование" in keyword:
                        score += 0.2
                    break
        
        score += len(code) * 0.01
        scored.append((code, score, prefix))
    
    if not scored:
        return "", 0.0, "все кандидаты исключены (не являются кодами контейнеров)"
    
    scored.sort(key=lambda x: x[1], reverse=True)
    best_code, best_score, best_prefix = scored[0]
    
    confidence = min(best_score, 0.98)
    
    if best_prefix in KNOWN_CONTAINER_PREFIXES:
        reason = f"код контейнера с префиксом {best_prefix}, выбран из {len(candidates)} кандидатов"
    else:
        reason = f"выбран лучший из {len(candidates)} кандидатов (score={best_score:.2f})"
    
    return best_code, confidence, reason

@tool
def list_pdfs(folder: str) -> list[str]:
    '''Возвращает список путей к PDF-файлам в указанной папке.'''
    try:
        folder_path = Path(folder)
        if not folder_path.exists():
            raise FileNotFoundError(f"Папка не существует: {folder}")
        
        if not folder_path.is_dir():
            raise NotADirectoryError(f"Путь не является папкой: {folder}")
        
        pdf_files = sorted(folder_path.glob("*.pdf"))
        return [str(p.absolute()) for p in pdf_files]
    
    except Exception as e:
        return [f"ERROR: {str(e)}"]


@tool
def read_pdf_text(path: str) -> str:
    '''Извлекает текст из PDF-файла (все страницы).'''
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"ERROR: Файл не найден: {path}"
        
        text_parts = []
        
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        
        full_text = "\n".join(text_parts).strip()
        return full_text if full_text else ""
    
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def regex_extract_code(text: str) -> dict[str, Any]:
    '''Извлекает код контейнера из текста с помощью регулярных выражений.'''
    try:
        if not text or text.startswith("ERROR"):
            return {
                "code": "",
                "candidates": [],
                "confidence": 0.0,
                "reason": "текст пустой или ошибка чтения"
            }
        
        candidates = []
        
        priority_matches = PRIORITY_PATTERN.findall(text)
        if priority_matches:
            for match in priority_matches:
                normalized = match.replace(" ", "").replace("-", "").replace("_", "").upper()
                if VALIDATION_PATTERN.match(normalized):
                    candidates.append(normalized)
        
        if not candidates:
            fallback_matches = FALLBACK_PATTERN.findall(text)
            for letters, digits in fallback_matches:
                normalized = f"{letters}{digits}".replace(" ", "").replace("-", "").replace("_", "").upper()
                if VALIDATION_PATTERN.match(normalized):
                    candidates.append(normalized)
        
        candidates = list(dict.fromkeys(candidates))
        
        code, confidence, reason = _calculate_confidence(candidates, text, "regex")
        
        return {
            "code": code,
            "candidates": candidates,
            "confidence": confidence,
            "reason": reason
        }
    
    except Exception as e:
        return {
            "code": "",
            "candidates": [],
            "confidence": 0.0,
            "reason": f"ошибка regex: {str(e)}"
        }


@tool
def llm_extract_code(text: str, llm_instance: Any = None) -> dict[str, Any]:
    '''
    Извлекает код контейнера с помощью GigaChat LLM.
    Агент использует свой собственный LLM для анализа.
    '''
    try:
        if not text or text.startswith("ERROR"):
            return {
                "code": "",
                "confidence": 0.0,
                "reason": "текст пустой или ошибка чтения"
            }
        
        return {
            "code": "",
            "confidence": 0.0,
            "reason": "LLM_NEEDED: требуется анализ через GigaChat"
        }
    
    except Exception as e:
        return {
            "code": "",
            "confidence": 0.0,
            "reason": f"ошибка LLM: {str(e)}"
        }


@tool
def ocr_extract_text(path: str) -> str:
    '''Извлекает текст из PDF с помощью OCR (для сканированных документов).'''
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"ERROR: Файл не найден: {path}"
        
        try:
            images = convert_from_path(str(file_path), dpi=PDF_DPI)
        except Exception as e:
            return f"ERROR: Не удалось конвертировать PDF. Установите Poppler: {str(e)}"
        
        text_parts = []
        for image in images:
            page_text = pytesseract.image_to_string(
                image, 
                lang="rus+eng",
                config=TESSERACT_CONFIG
            )
            if page_text.strip():
                text_parts.append(page_text)
        
        full_text = "\n".join(text_parts).strip()
        return full_text if full_text else ""
    
    except Exception as e:
        return f"ERROR: OCR failed - {str(e)}"


@tool
def normalize_code(raw: str) -> str:
    '''
    Нормализует код контейнера: убирает пробелы/дефисы/подчёркивания,
    приводит к верхнему регистру, валидирует формат.
    '''
    try:
        if not raw:
            return "ERROR: пустой код"
        
        normalized = raw.replace(" ", "").replace("-", "").replace("_", "").upper()
        
        if not VALIDATION_PATTERN.match(normalized):
            return f"ERROR: код '{normalized}' не соответствует формату (4 буквы + 7 цифр)"
        
        return normalized
    
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def safe_rename(path: str, new_basename: str, dry_run: bool = False) -> dict[str, str]:
    '''Безопасно переименовывает файл, избегая коллизий имён.'''
    try:
        file_path = Path(path)
        if not file_path.exists():
            return {"new_path": "", "note": f"ERROR: файл не найден: {path}"}
        
        parent_dir = file_path.parent
        new_name = f"{new_basename}.pdf"
        new_path = parent_dir / new_name
        
        if new_path.exists() and new_path != file_path:
            counter = 1
            while new_path.exists():
                new_name = f"{new_basename}_{counter}.pdf"
                new_path = parent_dir / new_name
                counter += 1
            
            note = f"коллизия имени, добавлен суффикс _{counter-1}"
        else:
            note = "переименовано успешно"
        
        if not dry_run:
            if new_path != file_path:
                file_path.rename(new_path)
        else:
            note = f"DRY RUN: {note}"
        
        return {
            "new_path": str(new_path),
            "note": note
        }
    
    except Exception as e:
        return {
            "new_path": "",
            "note": f"ERROR: {str(e)}"
        }


_LOG_FILE_PATH: Path | None = None


def set_log_file(log_path: Path) -> None:
    '''Устанавливает путь к лог-файлу.'''
    global _LOG_FILE_PATH
    _LOG_FILE_PATH = log_path
    
    if not log_path.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(",".join(LOG_FIELDS) + "\n")


@tool
def log_result(row: dict[str, Any]) -> str:
    '''Записывает строку результата в CSV-лог.'''
    try:
        if _LOG_FILE_PATH is None:
            return "ERROR: лог-файл не инициализирован"
        
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "original_path": row.get("original_path", ""),
            "new_path": row.get("new_path", ""),
            "extracted_code": row.get("extracted_code", ""),
            "method": row.get("method", ""),
            "confidence": row.get("confidence", ""),
            "note": row.get("note", ""),
            "dry_run": row.get("dry_run", "0"),
        }
        
        values = [str(log_entry.get(field, "")) for field in LOG_FIELDS]
        values = [f'"{v.replace(chr(34), chr(34)+chr(34))}"' for v in values]
        csv_line = ",".join(values)
        
        with open(_LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(csv_line + "\n")
        
        return "OK: запись добавлена в лог"
    
    except Exception as e:
        return f"ERROR: {str(e)}"


def safe_rename_direct(path: str, new_basename: str, dry_run: bool = False) -> dict[str, str]:
    '''Прямая функция переименования без LangChain wrapper.'''
    try:
        file_path = Path(path)
        if not file_path.exists():
            return {"new_path": "", "note": f"ERROR: файл не найден: {path}"}
        
        parent_dir = file_path.parent
        new_name = f"{new_basename}.pdf"
        new_path = parent_dir / new_name
        
        if new_path.exists() and new_path != file_path:
            counter = 1
            while new_path.exists():
                new_name = f"{new_basename}_{counter}.pdf"
                new_path = parent_dir / new_name
                counter += 1
            note = f"коллизия имени, добавлен суффикс _{counter-1}"
        else:
            note = "переименовано успешно"
        
        if not dry_run:
            if new_path != file_path:
                file_path.rename(new_path)
        else:
            note = f"DRY RUN: {note}"
        
        return {"new_path": str(new_path), "note": note}
    
    except Exception as e:
        return {"new_path": "", "note": f"ERROR: {str(e)}"}


def log_result_direct(row: dict[str, Any], log_path: Path) -> str:
    '''Прямая функция логирования без LangChain wrapper.'''
    try:
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "original_path": row.get("original_path", ""),
            "new_path": row.get("new_path", ""),
            "extracted_code": row.get("extracted_code", ""),
            "method": row.get("method", ""),
            "confidence": row.get("confidence", ""),
            "note": row.get("note", ""),
            "dry_run": row.get("dry_run", "0"),
        }
        
        values = [str(log_entry.get(field, "")) for field in LOG_FIELDS]
        values = [f'"{v.replace(chr(34), chr(34)+chr(34))}"' for v in values]
        csv_line = ",".join(values)
        
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(csv_line + "\n")
        
        return "OK"
    
    except Exception as e:
        return f"ERROR: {str(e)}"


def read_pdf_text_direct(path: str) -> str:
    '''Прямая функция чтения PDF без LangChain wrapper.'''
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"ERROR: Файл не найден: {path}"
        
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        
        full_text = "\n".join(text_parts).strip()
        return full_text if full_text else ""
    
    except Exception as e:
        return f"ERROR: {str(e)}"


def regex_extract_code_direct(text: str) -> dict[str, Any]:
    '''Прямая функция извлечения кода regex без LangChain wrapper.'''
    try:
        if not text or text.startswith("ERROR"):
            return {
                "code": "",
                "candidates": [],
                "confidence": 0.0,
                "reason": "текст пустой или ошибка чтения"
            }
        
        candidates = []
        
        priority_matches = PRIORITY_PATTERN.findall(text)
        if priority_matches:
            for match in priority_matches:
                normalized = match.replace(" ", "").replace("-", "").replace("_", "").upper()
                if VALIDATION_PATTERN.match(normalized):
                    candidates.append(normalized)
        
        if not candidates:
            fallback_matches = FALLBACK_PATTERN.findall(text)
            for letters, digits in fallback_matches:
                normalized = f"{letters}{digits}".replace(" ", "").replace("-", "").replace("_", "").upper()
                if VALIDATION_PATTERN.match(normalized):
                    candidates.append(normalized)
        
        candidates = list(dict.fromkeys(candidates))
        code, confidence, reason = _calculate_confidence(candidates, text, "regex")
        
        return {
            "code": code,
            "candidates": candidates,
            "confidence": confidence,
            "reason": reason
        }
    
    except Exception as e:
        return {
            "code": "",
            "candidates": [],
            "confidence": 0.0,
            "reason": f"ошибка regex: {str(e)}"
        }


def normalize_code_direct(raw: str) -> str:
    '''Прямая функция нормализации без LangChain wrapper.'''
    try:
        if not raw:
            return "ERROR: пустой код"
        
        normalized = raw.replace(" ", "").replace("-", "").replace("_", "").upper()
        
        if not VALIDATION_PATTERN.match(normalized):
            return f"ERROR: код '{normalized}' не соответствует формату (4 буквы + 7 цифр)"
        
        return normalized
    
    except Exception as e:
        return f"ERROR: {str(e)}"


def ocr_extract_text_direct(path: str) -> str:
    '''Прямая функция OCR без LangChain wrapper.'''
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"ERROR: Файл не найден: {path}"
        
        try:
            images = convert_from_path(str(file_path), dpi=PDF_DPI)
        except Exception as e:
            error_msg = str(e)
            if "poppler" in error_msg.lower() or "pdftoppm" in error_msg.lower():
                return f"ERROR: Poppler не установлен. Скачайте: https://github.com/oschwartz10612/poppler-windows/releases/ и добавьте в PATH"
            return f"ERROR: Не удалось конвертировать PDF: {error_msg}"
        
        text_parts = []
        for image in images:
            try:
                page_text = pytesseract.image_to_string(
                    image, 
                    lang="rus+eng",
                    config=TESSERACT_CONFIG
                )
                if page_text.strip():
                    text_parts.append(page_text)
            except Exception as e:
                return f"ERROR: OCR failed - {str(e)}"
        
        full_text = "\n".join(text_parts).strip()
        return full_text if full_text else ""
    
    except Exception as e:
        return f"ERROR: OCR общая ошибка - {str(e)}"


ALL_TOOLS = [
    list_pdfs,
    read_pdf_text,
    regex_extract_code,
    llm_extract_code,
    ocr_extract_text,
    normalize_code,
    safe_rename,
    log_result,
]