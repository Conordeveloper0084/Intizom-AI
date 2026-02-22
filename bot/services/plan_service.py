from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from bot.models.plan import Plan, PlanStatus
from bot.models.user import User
from datetime import date, timedelta


async def create_plans(session: AsyncSession, user: User, plans_data: list[dict]) -> list[Plan]:
    """GPT dan kelgan plan listni DBga saqlaydi"""
    plans = []
    for p in plans_data:
        plan = Plan(
            user_id=user.id,
            title=p["title"],
            description=p.get("description"),
            scheduled_time=p.get("scheduled_time"),
            plan_date=date.today(),
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
    result = await session.execute(
        select(Plan).where(
            and_(
                Plan.user_id == user.id,
                Plan.plan_date == date.today()
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
    from datetime import datetime
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
    return result.scalars().all()


async def get_all_pending_plans_today(session: AsyncSession) -> list[Plan]:
    """Bugungi barcha pending rejalarni qaytaradi (kechki tekshiruv uchun)"""
    result = await session.execute(
        select(Plan).where(
            and_(
                Plan.status == PlanStatus.pending,
                Plan.plan_date == date.today()
            )
        )
    )
    return result.scalars().all()


async def move_plan_to_tomorrow(session: AsyncSession, plan: Plan) -> Plan:
    """Rejani keyingi kunga ko'chiradi"""
    # Yangi reja yaratish
    new_plan = Plan(
        user_id=plan.user_id,
        title=plan.title,
        description=plan.description,
        scheduled_time=plan.scheduled_time,
        plan_date=date.today() + timedelta(days=1),
        score_value=plan.score_value,
        status=PlanStatus.pending,
    )
    session.add(new_plan)
    
    # Eski rejani failed qilish
    plan.status = PlanStatus.failed
    
    await session.commit()
    await session.refresh(new_plan)
    return new_plan