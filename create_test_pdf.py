'''Создание тестовых PDF для проверки работы агента.'''
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

test_dir = Path("test_pdfs")
test_dir.mkdir(exist_ok=True)

test_cases = [
    ("invoice_001.pdf", [
        "НАКЛАДНАЯ № 12345",
        "",
        "Контейнер № ABCD1234567",
        "Дата: 15.01.2024",
        "Отправитель: ООО Транспорт"
    ]),
    ("delivery_note.pdf", [
        "DELIVERY NOTE",
        "",
        "Container: MSCU9876543",
        "Date: 2024-01-20",
        "Shipper: Transport Ltd"
    ]),
    ("waybill_003.pdf", [
        "ТОВАРНО-ТРАНСПОРТНАЯ НАКЛАДНАЯ",
        "",
        "Код контейнера TEMU-1111111",
        "Маршрут: Москва - Владивосток",
        "Груз: 20 тонн"
    ]),
]

for filename, lines in test_cases:
    pdf_path = test_dir / filename
    
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica", 12)
    
    y = 750
    for line in lines:
        c.drawString(100, y, line)
        y -= 25
    
    c.save()
    print(f"Создан: {pdf_path.name}")

print(f"\n Папка: {test_dir.absolute()}")
print("\n Ожидаемые коды:")
print("   - ABCD1234567")
print("   - MSCU9876543")
print("   - TEMU1111111")