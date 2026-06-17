import logging
from http import HTTPStatus

from fastapi import APIRouter, Request, Response
from telegram import Update

from .agent_client import forward_to_agent
from src.schemas import IncomingMessage

logger = logging.getLogger(__name__)

telegram_router = APIRouter(prefix="/webhook", tags=["Webhook"])


@telegram_router.post("/telegram")
async def telegram_webhook(request: Request):
    """
    Receives raw Telegram updates, normalizes them, forwards to the agent
    service, and sends the reply back to the user via the bot.

    Always returns 200 — Telegram retries on any other status code.
    """
    try:
        payload = await request.json()
        ptb = request.app.state.ptb
        update = Update.de_json(data=payload, bot=ptb.bot)

        if not (update.message and update.message.text):
            return Response(status_code=HTTPStatus.OK)

        msg = IncomingMessage(
            platform="telegram",
            chat_id=str(update.effective_chat.id),
            user_id=str(update.effective_user.id),
            username=update.effective_user.username,
            metadata={
                "message_id": update.message.message_id,
                "update_id": update.update_id,
            },
            role="user",
            content=update.message.text
        )

        agent_response = await forward_to_agent(msg)

        if agent_response:
            await ptb.bot.send_message(
                chat_id=msg.chat_id,
                text=agent_response.text,
            )

    except Exception:
        logger.exception("Error processing Telegram update")

    return Response(status_code=HTTPStatus.OK)