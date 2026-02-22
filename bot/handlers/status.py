from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import date

from bot.services.user_service import get_user_by_telegram_id
from bot.services.admin_service import get_user_status
from bot.models.plan import Plan, PlanStatus
from bot.models.score_log import ScoreLog

router = Router()


@router.message(F.text == "📊 Mening statusim")
async def my_status_handler(message: Message, session: AsyncSession):
    user = await get_user_by_telegram_id(session, message.from_user.id)

    if not user:
        await message.answer("Iltimos /start bosing.")
        return

    status = get_user_status(user.total_score, user.streak)

    # Bugungi rejalar statistikasi
    plans_result = await session.execute(
        select(Plan).where(
            and_(
                Plan.user_id == user.id,
                Plan.plan_date == date.today()
            )
        )
    )
    plans = plans_result.scalars().all()

    done_today = len([p for p in plans if p.status == PlanStatus.done])
    total_today = len(plans)

    # Bugungi ball
    score_result = await session.execute(
        select(func.sum(ScoreLog.score_change)).where(
            and_(
                ScoreLog.user_id == user.id,
                func.date(ScoreLog.created_at) == date.today()
            )
        )
    )
    today_score = score_result.scalar() or 0

    # Jami bajarilgan rejalar
    all_done_result = await session.execute(
        select(func.count(Plan.id)).where(
            and_(
                Plan.user_id == user.id,
                Plan.status == PlanStatus.done
            )
        )
    )
    all_done = all_done_result.scalar() or 0

    text = (
        f"👤 <b>{user.full_name}</b>\n"
        f"📊 Status: <b>{status}</b>\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⭐ Umumiy ball: <b>{user.total_score}</b>\n"
        f"🔥 Streak: <b>{user.streak} kun</b>\n"
        f"✅ Jami bajarilgan: <b>{all_done} ta</b>\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📅 <b>Bugun:</b>\n"
        f"📋 Rejalar: <b>{total_today} ta</b>\n"
        f"✅ Bajarildi: <b>{done_today} ta</b>\n"
        f"⭐ Bugungi ball: <b>{today_score:+d}</b>"
    )

    await message.answer(text, parse_mode="HTML")