"""
CLI и агентная обработка PDF.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

from src.settings import DEFAULT_MAX_ITERATIONS, LOGS_DIR, MIN_CONFIDENCE_THRESHOLD, LOG_FIELDS

try:
    from src.agent import create_gigachat_llm, create_agent_executor, extract_code_with_llm
    AGENT_AVAILABLE = True
except ImportError as e:
    print(f"Агент недоступен: {e}")
    AGENT_AVAILABLE = False

from src.tools import (
    ALL_TOOLS,
    normalize_code_direct,
    ocr_extract_text_direct,
    read_pdf_text_direct,
    regex_extract_code_direct,
    safe_rename_direct,
    log_result_direct,
)


def process_with_agent(
    folder: str,
    ocr_enabled: bool = False,
    dry_run: bool = False,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> dict:
    '''Агентная обработка папки с PDF.'''
    log_filename = f"rename_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    log_path = LOGS_DIR / log_filename
    
    if not log_path.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(",".join(LOG_FIELDS) + "\n")
    
    from src.tools import set_log_file
    set_log_file(log_path)
    
    print(f"\n{'='*60}")
    print(f" АГЕНТНАЯ ОБРАБОТКА PDF")
    print(f"{'='*60}")
    print(f"Папка: {folder}")
    print(f"OCR: {'ВКЛ' if ocr_enabled else 'ВЫКЛ'}")
    print(f"Режим: {'DRY RUN' if dry_run else 'БОЕВОЙ'}")
    print(f"Лог: {log_path}")
    print(f"{'='*60}\n")
    
    folder_path = Path(folder)
    if not folder_path.exists():
        return {"error": f"Папка не существует: {folder}"}
    
    pdf_files = sorted([str(p) for p in folder_path.glob("*.pdf")])
    
    if not pdf_files:
        print("PDF файлы не найдены")
        return {"total": 0, "processed": 0, "renamed": 0, "skipped": 0, "errors": 0, "log_file": str(log_path)}
    
    agent_executor = create_agent_executor(tools=ALL_TOOLS, max_iterations=max_iterations * len(pdf_files), verbose=True)
    
    files_list = "\n".join(f"{i+1}. {p}" for i, p in enumerate(pdf_files))
    
    task = f"""Обработай {len(pdf_files)} PDF файлов:

{files_list}

ДЛЯ КАЖДОГО ФАЙЛА:
1. read_pdf_text - прочитай
2. regex_extract_code - найди код
3. Если confidence < 0.8 - сам найди AAAA1234567
4. normalize_code - нормализуй
5. safe_rename - переименуй
6. log_result - запиши

OCR {'включён' if ocr_enabled else 'выключен'}.
Обработай ВСЕ файлы."""

    try:
        result = agent_executor.invoke({"input": task})
        
        print(f"\n{'='*60}")
        print(f"АГЕНТ ЗАВЕРШИЛ РАБОТУ")
        print(f"{'='*60}")
        
        output = result.get("output", "Нет вывода")
        if len(output) > 500:
            output = output[:500] + "..."
        print(output)
        
        print(f"\nЛог: {log_path}")
        
        return analyze_log(log_path)
    
    except Exception as e:
        print(f"\nОшибка агента: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "log_file": str(log_path)}


def process_folder_simple(
    folder: str,
    ocr_enabled: bool = False,
    dry_run: bool = False,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> dict:
    '''Упрощённая обработка без агента.'''
    log_filename = f"rename_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    log_path = LOGS_DIR / log_filename
    
    if not log_path.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(",".join(LOG_FIELDS) + "\n")
    
    print(f"\n{'='*60}")
    print(f"УПРОЩЁННАЯ ОБРАБОТКА PDF")
    print(f"{'='*60}")
    print(f"Папка: {folder}")
    print(f"OCR: {'ВКЛ' if ocr_enabled else 'ВЫКЛ'}")
    print(f"Режим: {'DRY RUN' if dry_run else 'БОЕВОЙ'}")
    print(f"Лог: {log_path}")
    print(f"{'='*60}\n")
    
    try:
        llm = create_gigachat_llm() if AGENT_AVAILABLE else None
    except Exception as e:
        print(f"GigaChat недоступен: {e}")
        llm = None
    
    folder_path = Path(folder)
    if not folder_path.exists():
        return {"error": f"Папка не существует: {folder}"}
    
    pdf_paths = sorted([str(p) for p in folder_path.glob("*.pdf")])
    
    total_files = len(pdf_paths)
    processed = 0
    renamed = 0
    skipped = 0
    errors = 0
    
    print(f"Найдено файлов: {total_files}\n")
    
    for idx, pdf_path in enumerate(pdf_paths, 1):
        print(f"[{idx}/{total_files}] {Path(pdf_path).name}")
        
        original_path = pdf_path
        extracted_code = ""
        method = ""
        confidence = 0.0
        note = ""
        new_path = ""
        
        try:
            text = read_pdf_text_direct(pdf_path)
            
            if text.startswith("ERROR"):
                note = f"Ошибка чтения: {text}"
                errors += 1
                print(f"{note}")
                log_result_direct({
                    "original_path": original_path,
                    "new_path": "",
                    "extracted_code": "",
                    "method": "read",
                    "confidence": 0.0,
                    "note": note,
                    "dry_run": "1" if dry_run else "0"
                }, log_path)
                continue
            
            if text.strip():
                print(f"Текст извлечён ({len(text)} символов)")
                regex_result = regex_extract_code_direct(text)
                extracted_code = regex_result["code"]
                confidence = regex_result["confidence"]
                method = "regex"
                
                print(f"Regex: code='{extracted_code}', confidence={confidence:.2f}, candidates={len(regex_result['candidates'])}")
                
                if llm and (confidence < MIN_CONFIDENCE_THRESHOLD or len(regex_result["candidates"]) > 1):
                    print(f" Вызов LLM...")
                    llm_result = extract_code_with_llm(text, llm)
                    
                    if llm_result["confidence"] > confidence:
                        extracted_code = llm_result["code"]
                        confidence = llm_result["confidence"]
                        method = "llm"
                        note = llm_result["reason"]
                        print(f"LLM: code='{extracted_code}', confidence={confidence:.2f}")
            else:
                if ocr_enabled:
                    print(f"OCR...")
                    ocr_text = ocr_extract_text_direct(pdf_path)
                    
                    if not ocr_text.startswith("ERROR") and ocr_text.strip():
                        print(f"  📄 OCR текст извлечён ({len(ocr_text)} символов)")
                        regex_result = regex_extract_code_direct(ocr_text)
                        extracted_code = regex_result["code"]
                        confidence = regex_result["confidence"]
                        method = "ocr+regex"
                        
                        print(f" OCR Regex: code='{extracted_code}', confidence={confidence:.2f}")
                        
                        if llm and confidence < MIN_CONFIDENCE_THRESHOLD:
                            print(f" Вызов LLM после OCR...")
                            llm_result = extract_code_with_llm(ocr_text, llm)
                            if llm_result["confidence"] > confidence:
                                extracted_code = llm_result["code"]
                                confidence = llm_result["confidence"]
                                method = "ocr+llm"
                                print(f" LLM: code='{extracted_code}', confidence={confidence:.2f}")
                    else:
                        note = "OCR не смог извлечь текст"
                        method = "ocr"
                        print(f" {note}")
                else:
                    note = "NO_TEXT: текст пустой, OCR выключен"
                    method = "none"
                    print(f" {note}")
            
            if not extracted_code:
                note = note or "NOT_FOUND: код контейнера не найден"
                skipped += 1
                print(f"Пропущен: {note}")
                
                log_result_direct({
                    "original_path": original_path,
                    "new_path": "",
                    "extracted_code": "",
                    "method": method,
                    "confidence": confidence,
                    "note": note,
                    "dry_run": "1" if dry_run else "0"
                }, log_path)
                continue
            
            normalized = normalize_code_direct(extracted_code)
            
            if normalized.startswith("ERROR"):
                note = normalized
                skipped += 1
                print(f"{note}")
                
                log_result_direct({
                    "original_path": original_path,
                    "new_path": "",
                    "extracted_code": extracted_code,
                    "method": method,
                    "confidence": confidence,
                    "note": note,
                    "dry_run": "1" if dry_run else "0"
                }, log_path)
                continue
            
            rename_result = safe_rename_direct(pdf_path, normalized, dry_run)
            new_path = rename_result["new_path"]
            rename_note = rename_result["note"]
            
            if not new_path or rename_note.startswith("ERROR"):
                note = rename_note
                errors += 1
                print(f"{note}")
            else:
                note = rename_note
                renamed += 1
                new_filename = Path(new_path).name
                print(f"{extracted_code} → {new_filename} ({method}, {confidence:.2f})")
            
            log_result_direct({
                "original_path": original_path,
                "new_path": new_path,
                "extracted_code": normalized,
                "method": method,
                "confidence": confidence,
                "note": note,
                "dry_run": "1" if dry_run else "0"
            }, log_path)
            
            processed += 1
        
        except Exception as e:
            note = f"Критическая ошибка: {str(e)}"
            errors += 1
            print(f"{note}")
            
            import traceback
            traceback.print_exc()
            
            log_result_direct({
                "original_path": original_path,
                "new_path": "",
                "extracted_code": extracted_code,
                "method": method,
                "confidence": confidence,
                "note": note,
                "dry_run": "1" if dry_run else "0"
            }, log_path)
    
    print(f"\n{'='*60}")
    print(f"РЕЗУЛЬТАТЫ")
    print(f"{'='*60}")
    print(f"Всего: {total_files}")
    print(f"Обработано: {processed}")
    print(f"Переименовано: {renamed}")
    print(f"Пропущено: {skipped}")
    print(f"Ошибок: {errors}")
    print(f"{'='*60}")
    print(f"Лог: {log_path}\n")
    
    return {
        "total": total_files,
        "processed": processed,
        "renamed": renamed,
        "skipped": skipped,
        "errors": errors,
        "log_file": str(log_path)
    }


def analyze_log(log_path: Path) -> dict:
    '''Анализ CSV лога для получения статистики.'''
    import csv
    
    total = 0
    renamed = 0
    skipped = 0
    errors = 0
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                if row.get("new_path") and not row.get("note", "").startswith("ERROR"):
                    renamed += 1
                elif "NOT_FOUND" in row.get("note", "") or "NO_TEXT" in row.get("note", ""):
                    skipped += 1
                else:
                    errors += 1
    except Exception as e:
        print(f" Ошибка анализа лога: {e}")
    
    return {
        "total": total,
        "processed": total,
        "renamed": renamed,
        "skipped": skipped,
        "errors": errors,
        "log_file": str(log_path)
    }


def main():
    '''CLI точка входа.'''
    parser = argparse.ArgumentParser(
        description="ИИ-агент для переименования PDF по кодам контейнеров",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("--folder", type=str, required=True, help="Папка с PDF")
    parser.add_argument("--ocr", type=int, choices=[0, 1], default=0, help="OCR (0=выкл, 1=вкл)")
    parser.add_argument("--dry-run", type=int, choices=[0, 1], default=0, help="Dry-run (0=выкл, 1=вкл)")
    parser.add_argument("--max-iters", type=int, default=DEFAULT_MAX_ITERATIONS, help="Макс итераций")
    parser.add_argument("--mode", type=str, choices=["agent", "simple"], default="simple", help="Режим")
    
    args = parser.parse_args()
    
    folder_path = Path(args.folder)
    if not folder_path.exists():
        print(f"Папка не существует: {args.folder}", file=sys.stderr)
        sys.exit(1)
    
    if not folder_path.is_dir():
        print(f"Не является папкой: {args.folder}", file=sys.stderr)
        sys.exit(1)
    
    if args.mode == "agent" and AGENT_AVAILABLE:
        process_with_agent(
            folder=str(folder_path),
            ocr_enabled=bool(args.ocr),
            dry_run=bool(args.dry_run),
            max_iterations=args.max_iters
        )
    else:
        if args.mode == "agent":
            print("Агент недоступен, переключаюсь на упрощённый режим\n")
        
        process_folder_simple(
            folder=str(folder_path),
            ocr_enabled=bool(args.ocr),
            dry_run=bool(args.dry_run),
            max_iterations=args.max_iters
        )


if __name__ == "__main__":
    main()