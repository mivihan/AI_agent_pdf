'''Тест OCR и конвертации PDF.'''
import sys
from pathlib import Path

pdf_path = sys.argv[1] if len(sys.argv) > 1 else "my_pdfs/Железнодорожная накладная _ТАМОЖНЯ_-_35227475_ _ 16.02.25.pdf"

print(f"Файл: {pdf_path}\n")

print("Проверка Tesseract...")
try:
    import pytesseract
    tesseract_exe = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if tesseract_exe.exists():
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_exe)
        print(f"Tesseract: {tesseract_exe}")
    else:
        print(f"Tesseract НЕ НАЙДЕН: {tesseract_exe}")
except Exception as e:
    print(f" Ошибка: {e}")

print("\n Проверка pdf2image...")
try:
    from pdf2image import convert_from_path
    print(" pdf2image установлен")
except ImportError as e:
    print(f" pdf2image НЕ установлен: {e}")
    sys.exit(1)

print("\n Конвертация PDF в изображения...")
try:
    images = convert_from_path(pdf_path, dpi=300)
    print(f" Конвертировано {len(images)} страниц")
except Exception as e:
    print(f" Ошибка конвертации: {e}")
    print("\n РЕШЕНИЕ: Установите Poppler:")
    print("      https://github.com/oschwartz10612/poppler-windows/releases/")
    print("      Распакуйте в C:\\Program Files\\poppler")
    print("      Добавьте в PATH: C:\\Program Files\\poppler\\Library\\bin")
    sys.exit(1)

print("\n OCR первой страницы...")
try:
    text = pytesseract.image_to_string(images[0], lang="rus+eng")
    print(f"Текст извлечён ({len(text)} символов)")
    print(f"\n   Первые 500 символов:\n{text[:500]}")
except Exception as e:
    print(f"Ошибка OCR: {e}")

print("\nТест завершён")