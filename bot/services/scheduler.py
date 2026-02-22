from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, and_
from datetime import datetime, date

from database.db import AsyncSessionLocal
from bot.models.plan import Plan, PlanStatus
from bot.models.user import User
from bot.config import SUMMARY_HOUR, SUMMARY_MINUTE

scheduler = AsyncIOScheduler()


async def send_plan_notifications(bot):
    """Har daqiqada — vaqti kelgan rejalarni eslatadi"""
    async with AsyncSessionLocal() as session:
        now = datetime.now().strftime("%H:%M")

        result = await session.execute(
            select(Plan).where(
                and_(
                    Plan.scheduled_time == now,
                    Plan.status == PlanStatus.pending,
                    Plan.notified_at == None,
                    Plan.plan_date == date.today()
                )
            )
        )
        plans = result.scalars().all()

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
                plan.notified_at = datetime.utcnow()
                await session.commit()
            except Exception:
                pass


async def send_daily_summary(bot):
    """Har kuni 21:00 da kunlik hisobot"""
    async with AsyncSessionLocal() as session:
        users_result = await session.execute(
            select(User).where(User.is_active == True)
        )
        users = users_result.scalars().all()

        for user in users:
            plans_result = await session.execute(
                select(Plan).where(
                    and_(
                        Plan.user_id == user.id,
                        Plan.plan_date == date.today()
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
    """Har kuni 23:00 da pending rejalarni tekshiradi"""
    async with AsyncSessionLocal() as session:
        # Barcha pending rejalarni topish
        result = await session.execute(
            select(Plan).where(
                and_(
                    Plan.status == PlanStatus.pending,
                    Plan.plan_date == date.today()
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
    # Har daqiqa — vaqti kelgan rejalarni eslatish
    scheduler.add_job(
        send_plan_notifications,
        trigger=CronTrigger(minute="*"),
        args=[bot],
        id="plan_notifications"
    )
    
    # Har kuni 21:00 — kunlik summary
    scheduler.add_job(
        send_daily_summary,
        trigger=CronTrigger(hour=SUMMARY_HOUR, minute=SUMMARY_MINUTE),
        args=[bot],
        id="daily_summary"
    )
    
    # Har kuni 23:00 — pending rejalarni tekshirish
    scheduler.add_job(
        check_pending_plans,
        trigger=CronTrigger(hour=23, minute=0),
        args=[bot],
        id="pending_check"
    )
    
    scheduler.start()