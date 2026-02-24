from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, and_
from datetime import datetime

from database.db import AsyncSessionLocal
from bot.models.plan import Plan, PlanStatus
from bot.models.user import User
from bot.config import SUMMARY_HOUR, SUMMARY_MINUTE, PENDING_CHECK_HOUR, PENDING_CHECK_MINUTE, TIMEZONE

scheduler = AsyncIOScheduler(timezone=str(TIMEZONE))


async def send_plan_notifications(bot):
    """Har daqiqada — vaqti kelgan rejalarni eslatadi (Tashkent vaqti)"""
    async with AsyncSessionLocal() as session:
        from bot.services.plan_service import get_pending_plans_to_notify
        plans = await get_pending_plans_to_notify(session)

        for plan in plans:
            user_result = await session.execute(
                select(User).where(User.id == plan.user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                continue

            from bot.keyboards.plan_keys import done_failed_keyboard

            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=(
                        f"⏰ <b>Vaqt bo'ldi!</b>\n\n"
                        f"📌 <b>{plan.title}</b>\n"
                        f"🕐 {plan.scheduled_time}\n\n"
                        f"✅ Bajarsangiz <b>+{plan.score_value} ball</b>\n"
                        f"❌ Bajarmasangiz <b>-3 ball</b>"
                    ),
                    parse_mode="HTML",
                    reply_markup=done_failed_keyboard(plan.id)
                )
                plan.notified_at = datetime.now(TIMEZONE)
                await session.commit()
            except Exception:
                pass


async def send_daily_summary(bot):
    """Har kuni 21:00 da kunlik hisobot (Tashkent vaqti)"""
    async with AsyncSessionLocal() as session:
        today = datetime.now(TIMEZONE).date()
        
        users_result = await session.execute(
            select(User).where(User.is_active == True)
        )
        users = users_result.scalars().all()

        for user in users:
            plans_result = await session.execute(
                select(Plan).where(
                    and_(
                        Plan.user_id == user.id,
                        Plan.plan_date == today
                    )
                )
            )
            plans = plans_result.scalars().all()

            if not plans:
                continue

            done = [p for p in plans if p.status == PlanStatus.done]
            failed = [p for p in plans if p.status == PlanStatus.failed]
            pending = [p for p in plans if p.status == PlanStatus.pending]

            # Streak yangilash
            if done:
                user.streak += 1
            elif failed and not done:
                user.streak = 0
            await session.commit()

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Batafsil hisobot", callback_data="report")]
            ])

            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=(
                        f"🌙 <b>Kunlik hisobot</b>\n\n"
                        f"✅ Bajarildi: <b>{len(done)} ta</b>\n"
                        f"❌ Bajarilmadi: <b>{len(failed)} ta</b>\n"
                        f"⏳ Eslatilmadi: <b>{len(pending)} ta</b>\n\n"
                        f"🏆 Umumiy ball: <b>{user.total_score}</b>\n"
                        f"🔥 Streak: <b>{user.streak} kun</b>"
                    ),
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            except Exception:
                pass


async def check_pending_plans(bot):
    """Har kuni 23:00 da pending rejalarni tekshiradi (Tashkent vaqti)"""
    async with AsyncSessionLocal() as session:
        today = datetime.now(TIMEZONE).date()
        
        result = await session.execute(
            select(Plan).where(
                and_(
                    Plan.status == PlanStatus.pending,
                    Plan.plan_date == today
                )
            )
        )
        pending_plans = result.scalars().all()

        for plan in pending_plans:
            user_result = await session.execute(
                select(User).where(User.id == plan.user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                continue

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Bajardim", callback_data=f"done_{plan.id}"),
                    InlineKeyboardButton(text="❌ Bajarmadim", callback_data=f"failed_{plan.id}"),
                ],
                [
                    InlineKeyboardButton(text="📅 Ertaga", callback_data=f"tomorrow_{plan.id}"),
                ]
            ])

            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=(
                        f"🌙 <b>Kun tugadi</b>\n\n"
                        f"📌 <b>{plan.title}</b>\n"
                        f"{f'🕐 {plan.scheduled_time}' if plan.scheduled_time else '🕐 Vaqtsiz'}\n\n"
                        f"Bu rejani bajardingizmi?"
                    ),
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            except Exception:
                pass


def start_scheduler(bot):
    # Har daqiqa — vaqti kelgan rejalar
    scheduler.add_job(
        send_plan_notifications,
        trigger=CronTrigger(minute="*", timezone=str(TIMEZONE)),
        args=[bot],
        id="plan_notifications"
    )
    
    # 21:00 (Tashkent) — kunlik summary
    scheduler.add_job(
        send_daily_summary,
        trigger=CronTrigger(hour=SUMMARY_HOUR, minute=SUMMARY_MINUTE, timezone=str(TIMEZONE)),
        args=[bot],
        id="daily_summary"
    )
    
    # 23:00 (Tashkent) — pending check
    scheduler.add_job(
        check_pending_plans,
        trigger=CronTrigger(hour=PENDING_CHECK_HOUR, minute=PENDING_CHECK_MINUTE, timezone=str(TIMEZONE)),
        args=[bot],
        id="pending_check"
    )
    
    scheduler.start()