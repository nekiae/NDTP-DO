from __future__ import annotations

from src.database.connection import get_db_session
from src.repositories import UserRepository, AuthCodeRepository

from PIL import Image, ImageDraw, ImageFont
from bs4 import BeautifulSoup
from datetime import datetime
import requests
import fitz  # PyMuPDF
import re
import tempfile
import os
import qrcode
import secrets
from typing import Optional, List


def create_user(username: str) -> str:
    """Create a user (if missing) and issue a one-time authentication code.

    Returns the auth code string.
    """
    db = next(get_db_session())
    try:
        user_repo = UserRepository(db)
        code_repo = AuthCodeRepository(db)

        # Ensure user exists
        user = user_repo.get_by_username(username)
        if not user:
            user = user_repo.create_user(username=username)

        # Generate a unique code
        code = _generate_unique_code(code_repo)
        code_repo.create_auth_code(user_id=user.id, code=code)

        print(f"User created: {user.username}")
        return code
    finally:
        db.close()


def _generate_unique_code(code_repo: AuthCodeRepository, attempts: int = 10) -> str:
    """Generate a unique code by checking repository; raise if cannot after attempts."""
    for _ in range(attempts):
        code = secrets.token_urlsafe(8)
        if code_repo.get_by_code(code) is None:
            return code
    raise RuntimeError("Failed to generate a unique auth code after multiple attempts")


def parse_latest_enrollment_document(html_content: str) -> Optional[str]:
    # Парсим HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # Ищем все секции смен
    panels = soup.find_all('div', class_='fusion-panel')
    latest_date: Optional[datetime] = None
    latest_link: Optional[str] = None

    for panel in panels:
        # Извлекаем даты смены
        date_span = panel.find('span', style=lambda value: value and 'font-size: 16px; text-align: center;' in value)
        if date_span:
            date_text = date_span.text.strip()
            # Предполагаем формат "DD.MM.YYYY – DD.MM.YYYY"
            try:
                end_date_str = date_text.split('–')[1].strip()
                end_date = datetime.strptime(end_date_str, '%d.%m.%Y')

                # Ищем ссылку на документ о зачисленных
                links = panel.find_all('a', href=True)
                for link in links:
                    if 'Списочный состав групп учащихся, зачисленных' in link.text:
                        # Сохраняем ссылку и дату, если это самая поздняя дата
                        if latest_date is None or end_date > latest_date:
                            latest_date = end_date
                            latest_link = link['href']
            except (IndexError, ValueError):
                continue

    return latest_link


def is_cyrillic_word(word: str) -> bool:
    return re.fullmatch(r'[А-ЯЁа-яё\-]+', word) is not None


def extract_fio_from_text(lines: List[str]) -> List[str]:
    fio_list: List[str] = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        words = line.split()

        # Вариант 1: ФИО на одной строке
        if len(words) == 3 and all(is_cyrillic_word(w) for w in words):
            fio_list.append(" ".join(words))
            i += 1
            continue

        # Вариант 2: Фамилия Имя на одной, Отчество на следующей
        if len(words) == 2 and all(is_cyrillic_word(w) for w in words):
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                next_words = next_line.split()
                if len(next_words) == 1 and is_cyrillic_word(next_words[0]):
                    fio_list.append(f"{words[0]} {words[1]} {next_words[0]}")
                    i += 2
                    continue

        i += 1

    return fio_list


def parse_pdf_fio_from_file(pdf_path: str) -> List[str]:
    all_fio: List[str] = []

    with fitz.open(pdf_path) as pdf:
        for page in pdf:
            blocks = page.get_text("blocks")
            for block in blocks:
                x0, y0, x1, y1, text, *_ = block
                text = text.strip().replace("\n", "")
                if text:
                    if "«" not in text and len(text) > 3:
                        split_text = text.split()
                        # осторожно: предполагаем, что первый токен — номер
                        if len(split_text) >= 4:
                            all_fio.append(" ".join(split_text[1:4]))

    return all_fio


def download_pdf_from_url(url: str) -> str:
    response = requests.get(url)
    response.raise_for_status()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(response.content)
        return tmp_file.name


def generate_qr_with_text(data: str, text: str, name: str) -> None:
    # Создание QR-кода
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=4
    )
    qr.add_data(data)
    qr.make(fit=True)

    # Создание изображения QR
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    # Настройка шрифта — используем файл из репозитория
    try:
        font = ImageFont.truetype("data/Manrope/Manrope-VariableFont_wght.ttf", 24)
    except IOError:
        font = ImageFont.load_default()
        print("⚠️ Не удалось загрузить шрифт Manrope. Используется шрифт по умолчанию.")

    # Получение размеров текста
    left, top, right, bottom = font.getbbox(text)
    text_width = abs(right - left)
    text_height = abs(top - bottom)

    # Создание нового изображения (QR + текст)
    qr_width, qr_height = qr_img.size
    total_height = qr_height + text_height + 50  # отступ

    new_img = Image.new('RGB', (qr_width, total_height), "white")
    new_img.paste(qr_img, (0, 0))

    # Добавление текста
    draw = ImageDraw.Draw(new_img)
    text_position = ((qr_width - text_width) // 2, qr_height + 10)
    draw.text(text_position, text, font=font, fill="black")

    # Убедимся, что папка существует
    os.makedirs("qrcodes", exist_ok=True)

    # Сохранение результата
    out_path = os.path.join("qrcodes", f"{name}.png")
    new_img.save(out_path)
    print(f"QR saved: {out_path}")


if __name__ == '__main__':
    html_content = requests.get("http://ndtp.by/schedule/").text
    result: Optional[str] = parse_latest_enrollment_document(html_content)
    print(f"Ссылка на документ за последний месяц: {result}")

    if not result:
        raise SystemExit("Не удалось найти ссылку на документ о зачисленных.")

    url = result.replace("https", "http")

    try:
        local_pdf_path = download_pdf_from_url(url)
        fio_list = parse_pdf_fio_from_file(local_pdf_path)

        # Ограничим первые 5 для теста
        for fio in fio_list[:5]:
            code = create_user(fio)
            generate_qr_with_text(f"https://t.me/techonoprodbot?start={code}", text=fio, name=fio)
    finally:
        if 'local_pdf_path' in locals() and os.path.exists(local_pdf_path):
            os.remove(local_pdf_path)
