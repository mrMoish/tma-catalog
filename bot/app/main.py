import io
import logging

import httpx
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from pydantic_settings import BaseSettings

log = logging.getLogger("bot")

CREATE_BUTTON_TEXT = "Создать товар"
WEBHOOK_PATH = "/tg/webhook"


class Settings(BaseSettings):
    bot_token: str
    admin_ids: str = ""
    public_url: str
    webhook_secret: str = "secret"
    backend_url: str = "http://backend:8000"
    internal_token: str

    @property
    def admins(self):
        return {int(x) for x in self.admin_ids.split(",") if x.strip()}


settings = Settings()
router = Router()


def is_admin(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id in settings.admins


def catalog_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть каталог",
                    web_app=WebAppInfo(url=settings.public_url),
                )
            ]
        ]
    )


def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CREATE_BUTTON_TEXT)]],
        resize_keyboard=True,
    )


async def send_welcome(message: Message):
    await message.answer("У меня есть товар", reply_markup=catalog_keyboard())
    if is_admin(message):
        await message.answer(
            "Вы администратор: нажмите «Создать товар», чтобы добавить новый.",
            reply_markup=admin_keyboard(),
        )


@router.message(CommandStart())
async def on_start(message: Message):
    await send_welcome(message)


@router.message(Command("create"))
@router.message(F.text == CREATE_BUTTON_TEXT)
async def on_create(message: Message):
    if not is_admin(message):
        await message.answer("Эта команда доступна только администратору.")
        return
    await message.answer(
        "Отправьте одно сообщение: фотография товара и подпись (название товара)."
    )


@router.message(F.photo)
async def on_photo(message: Message, bot: Bot):
    if not is_admin(message):
        await send_welcome(message)
        return

    title = (message.caption or "").strip()
    if not title:
        await message.answer(
            "Нужна подпись к фото, это название товара. "
            "Отправьте фото и название в одном сообщении."
        )
        return

    photo = message.photo[-1]
    buf = io.BytesIO()
    await bot.download(photo, destination=buf)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.backend_url}/api/products",
            headers={"X-Internal-Token": settings.internal_token},
            data={"title": title[:255]},
            files={"image": ("photo.jpg", buf.getvalue(), "image/jpeg")},
        )
    if resp.status_code != 201:
        log.error("backend error %s: %s", resp.status_code, resp.text)
        await message.answer("Не удалось создать товар, попробуйте ещё раз.")
        return

    await message.answer(f"Товар «{title}» создан.", reply_markup=catalog_keyboard())


@router.message()
async def on_any(message: Message):
    await send_welcome(message)


def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    async def on_startup(bot: Bot):
        await bot.set_webhook(
            settings.public_url.rstrip("/") + WEBHOOK_PATH,
            secret_token=settings.webhook_secret,
        )
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Каталог", web_app=WebAppInfo(url=settings.public_url)
            )
        )

    dp.startup.register(on_startup)

    app = web.Application()
    app.router.add_get("/health", lambda request: web.json_response({"status": "ok"}))
    SimpleRequestHandler(
        dispatcher=dp, bot=bot, secret_token=settings.webhook_secret
    ).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
