from aiogram.types import Message, File
from aiogram.client.bot import Bot
from aiogram import F, Router
from src.database.models import User
from src.services.s3_service import S3Service
from src.services.auth_service import AuthService 
from src.database.connection import get_db_session
from src.core.constants import UserStatus
from io import BytesIO

router = Router()

class Handler:
    def __init__(self, auth_service, s3_service):
        self.auth_service = auth_service
        self.s3_service = s3_service

    async def handle_photo(self, message: Message):
        """Handle single photo or document."""

        bot: Bot = message.bot
        chat_id: int = message.chat.id

        user: User = self.auth_service.get_authenticated_user(message.from_user.id)
        if not user:
            await bot.send_message(chat_id=chat_id, text="Вы не авторизованны")
            return

        await bot.send_message(chat_id=chat_id, text="Начинаю загрузку...")

        if message.photo:
            file_id = message.photo[-1].file_id
            filename = f"photo_{file_id}.jpg"
        elif message.document:
            file_id = message.document.file_id
            filename = message.document.file_name
        else:
            await bot.send_message(chat_id=chat_id, text="Загружать можно только картинки/видео")
            return

        media: File = await bot.get_file(file_id)
        media_io: BytesIO = BytesIO()
        await bot.download_file(media.file_path, media_io)

        success, err_text = self.s3_service.upload_file(
            media_io, user_id=user.id, filename=filename
        )
        if success:
            await bot.send_message(chat_id=chat_id, text="Успешно!")
        else:
            await bot.send_message(chat_id=chat_id, text="Что-то сломалось :(")




def register_load_message_handler(dp):
    handler = Handler(AuthService(next(get_db_session())), S3Service())

    dp.message.register(handler.handle_photo, F.photo | F.document | F.video, UserStatus.LOAD_MEDIA)