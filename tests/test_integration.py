import csv
import shutil
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from src.main import process_folder_simple

"""
Интеграционные тесты: создание тестовых PDF и проверка работы агента
"""

@pytest.fixture
def temp_pdf_folder(tmp_path):
    """Создаёт временную папку с тестовыми PDF."""
    pdf_dir = tmp_path / "test_pdfs"
    pdf_dir.mkdir()

    test_cases = [
        ("doc1.pdf", "Контейнер № ABCD1234567\nДата: 01.01.2024"),
        ("doc2.pdf", "Container: MSCU9876543\nDelivery note"),
        ("doc3.pdf", "Код контейнера TEMU-1111111\nОтправитель: ООО Тест"),
    ]
    
    for filename, text in test_cases:
        pdf_path = pdf_dir / filename

        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        c.setFont("Helvetica", 12)
        
        y = 750
        for line in text.split("\n"):
            c.drawString(50, y, line)
            y -= 20
        
        c.save()
    
    yield pdf_dir

    shutil.rmtree(pdf_dir, ignore_errors=True)


class TestIntegration:
    """Интеграционные тесты агента."""
    
    def test_process_folder_dry_run(self, temp_pdf_folder):
        """Тест обработки папки в режиме dry-run."""
        result = process_folder_simple(
            folder=str(temp_pdf_folder),
            ocr_enabled=False,
            dry_run=True,
            max_iterations=10
        )
        
        assert result["total"] == 3
        assert result["processed"] >= 2
        assert result["errors"] == 0

        original_files = sorted([f.name for f in temp_pdf_folder.glob("*.pdf")])
        assert "doc1.pdf" in original_files
        assert "doc2.pdf" in original_files
        assert "doc3.pdf" in original_files
    
    def test_log_contains_correct_codes(self, temp_pdf_folder):
        """Проверка правильности извлечённых кодов в логе."""
        result = process_folder_simple(
            folder=str(temp_pdf_folder),
            ocr_enabled=False,
            dry_run=True,
            max_iterations=10
        )
        
        log_file = Path(result["log_file"])
        assert log_file.exists()

        with open(log_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        expected_codes = {"ABCD1234567", "MSCU9876543", "TEMU1111111"}
        extracted_codes = {row["extracted_code"] for row in rows if row["extracted_code"]}

        assert expected_codes.issubset(extracted_codes), \
            f"Не все коды найдены. Ожидалось: {expected_codes}, получено: {extracted_codes}"
    
    def test_target_names_in_log(self, temp_pdf_folder):
        """Проверка целевых имён файлов в логе."""
        result = process_folder_simple(
            folder=str(temp_pdf_folder),
            ocr_enabled=False,
            dry_run=True,
            max_iterations=10
        )
        
        log_file = Path(result["log_file"])
        
        with open(log_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        target_names = [Path(row["new_path"]).name for row in rows if row["new_path"]]
        
        expected_names = {"ABCD1234567.pdf", "MSCU9876543.pdf", "TEMU1111111.pdf"}
        actual_names = set(target_names)
        
        assert expected_names.issubset(actual_names), \
            f"Целевые имена не совпадают. Ожидалось: {expected_names}, получено: {actual_names}"
    
    def test_actual_renaming(self, temp_pdf_folder):
        """Тест реального переименования (не dry-run)."""
        result = process_folder_simple(
            folder=str(temp_pdf_folder),
            ocr_enabled=False,
            dry_run=False,
            max_iterations=10
        )

        renamed_files = sorted([f.name for f in temp_pdf_folder.glob("*.pdf")])
        
        expected_names = ["ABCD1234567.pdf", "MSCU9876543.pdf", "TEMU1111111.pdf"]
        assert renamed_files == expected_names, \
            f"Файлы не переименованы корректно. Получено: {renamed_files}"
    
    def test_collision_handling(self, temp_pdf_folder):
        """Тест обработки коллизий имён."""
        c = canvas.Canvas(str(temp_pdf_folder / "duplicate.pdf"), pagesize=letter)
        c.setFont("Helvetica", 12)
        c.drawString(50, 750, "Контейнер № ABCD1234567")
        c.save()
        
        result = process_folder_simple(
            folder=str(temp_pdf_folder),
            ocr_enabled=False,
            dry_run=False,
            max_iterations=10
        )

        all_files = sorted([f.name for f in temp_pdf_folder.glob("*.pdf")])
        
        abcd_files = [f for f in all_files if f.startswith("ABCD1234567")]
        assert len(abcd_files) >= 2, f"Коллизия имён не обработана. Файлы: {abcd_files}"


class TestErrorHandling:
    """Тесты обработки ошибок."""
    
    def test_nonexistent_folder(self):
        """Тест на несуществующую папку."""
        result = process_folder_simple(
            folder="/nonexistent/folder/path",
            ocr_enabled=False,
            dry_run=True
        )
        
        assert "error" in result or result["total"] == 0
    
    def test_empty_folder(self, tmp_path):
        """Тест на пустую папку."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        result = process_folder_simple(
            folder=str(empty_dir),
            ocr_enabled=False,
            dry_run=True
        )
        
        assert result["total"] == 0
        assert result["processed"] == 0
    
    def test_invalid_format_skipped(self, tmp_path):
        """Тест: старый формат (2-3 буквы) должен пропускаться."""
        pdf_dir = tmp_path / "old_format"
        pdf_dir.mkdir()

        c = canvas.Canvas(str(pdf_dir / "old.pdf"), pagesize=letter)
        c.setFont("Helvetica", 12)
        c.drawString(50, 750, "Контейнер UI77")
        c.save()
        
        result = process_folder_simple(
            folder=str(pdf_dir),
            ocr_enabled=False,
            dry_run=True
        )

        assert result["skipped"] >= 1 or result["renamed"] == 0