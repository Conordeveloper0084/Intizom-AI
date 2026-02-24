from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from bot.models.plan import Plan, PlanStatus
from bot.models.user import User
from datetime import date, timedelta, datetime
from bot.config import TIMEZONE


async def create_plans(session: AsyncSession, user: User, plans_data: list[dict]) -> list[Plan]:
    """GPT dan kelgan plan listni DBga saqlaydi"""
    plans = []
    today = datetime.now(TIMEZONE).date()
    
    for p in plans_data:
        # Agar ertaga uchun bo'lsa
        plan_date = today + timedelta(days=1) if p.get("for_tomorrow") else today
        
        plan = Plan(
            user_id=user.id,
            title=p["title"],
            description=p.get("description"),
            scheduled_time=p.get("scheduled_time"),
            plan_date=plan_date,
            score_value=p.get("score_value", 5),
        )
        session.add(plan)
        plans.append(plan)
    
    await session.commit()
    for plan in plans:
        await session.refresh(plan)
    return plans


async def get_today_plans(session: AsyncSession, user: User) -> list[Plan]:
    """Bugungi barcha rejalarni qaytaradi"""
    today = datetime.now(TIMEZONE).date()
    
    result = await session.execute(
        select(Plan).where(
            and_(
                Plan.user_id == user.id,
                Plan.plan_date == today
            )
        ).order_by(Plan.scheduled_time)
    )
    return result.scalars().all()


async def get_plan_by_id(session: AsyncSession, plan_id: int) -> Plan | None:
    result = await session.execute(select(Plan).where(Plan.id == plan_id))
    return result.scalar_one_or_none()


async def update_plan_status(session: AsyncSession, plan: Plan, status: PlanStatus):
    plan.status = status
    await session.commit()


async def delete_plan(session: AsyncSession, plan: Plan):
    await session.delete(plan)
    await session.commit()


async def get_pending_plans_to_notify(session: AsyncSession) -> list[Plan]:
    """Vaqti kelgan va hali notification yuborilmagan rejalarni qaytaradi"""
    now_tashkent = datetime.now(TIMEZONE)
    now_time = now_tashkent.strftime("%H:%M")
    today = now_tashkent.date()
    
    result = await session.execute(
        select(Plan).where(
            and_(
                Plan.scheduled_time == now_time,
                Plan.status == PlanStatus.pending,
                Plan.notified_at == None,
                Plan.plan_date == today
            )
        )
    )
    return result.scalars().all()


async def get_all_pending_plans_today(session: AsyncSession) -> list[Plan]:
    """Bugungi barcha pending rejalarni qaytaradi"""
    today = datetime.now(TIMEZONE).date()
    
    result = await session.execute(
        select(Plan).where(
            and_(
                Plan.status == PlanStatus.pending,
                Plan.plan_date == today
            )
        )
    )
    return result.scalars().all()


async def move_plan_to_tomorrow(session: AsyncSession, plan: Plan) -> Plan:
    """Rejani keyingi kunga ko'chiradi"""
    tomorrow = datetime.now(TIMEZONE).date() + timedelta(days=1)
    
    new_plan = Plan(
        user_id=plan.user_id,
        title=plan.title,
        description=plan.description,
        scheduled_time=plan.scheduled_time,
        plan_date=tomorrow,
        score_value=plan.score_value,
        status=PlanStatus.pending,
    )
    session.add(new_plan)
    
    plan.status = PlanStatus.failed
    await session.commit()
    await session.refresh(new_plan)
    return new_plan


async def duplicate_plan_for_tomorrow(session: AsyncSession, plan: Plan) -> Plan:
    """Rejani ertaga uchun nusxalaydi (continue feature)"""
    tomorrow = datetime.now(TIMEZONE).date() + timedelta(days=1)
    
    new_plan = Plan(
        user_id=plan.user_id,
        title=plan.title,
        description=plan.description,
        scheduled_time=plan.scheduled_time,
        plan_date=tomorrow,
        score_value=plan.score_value,
        status=PlanStatus.pending,
    )
    session.add(new_plan)
    await session.commit()
    await session.refresh(new_plan)
    return new_plan