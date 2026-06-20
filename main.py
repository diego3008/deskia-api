import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from telegram import Update
from telegram.ext import Application
from src.api import telegram_router, businesses_router, appointments_router
from src.config import settings

logging.basicConfig(
    level="INFO",
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def build_ptb() -> Application:
    return (
        Application.builder()
        .token(settings.BOT_TOKEN)
        .updater(None)
        .build()
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    ptb = build_ptb()
    app.state.ptb = ptb

    webhook_url = f"{settings.WEBHOOK_URL}/webhook/telegram"
    await ptb.bot.set_webhook(
        url=webhook_url,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
    logger.info("Webhook registered: %s", webhook_url)

    async with ptb:
        await ptb.start()
        yield
        await ptb.stop()


app = FastAPI(
    title="Telegram Gateway",
    description="Receives Telegram updates and forwards them to the agent service.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(telegram_router)
app.include_router(businesses_router)
app.include_router(appointments_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
