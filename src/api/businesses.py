from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db import get_session
from src.models.business import Business, BusinessBase, BusinessUpdate

router = APIRouter(prefix="/businesses", tags=["Businesses"])


@router.post("/", response_model=Business)
async def create_business(
    business: BusinessBase, session: AsyncSession = Depends(get_session)
):
    db_obj = Business.model_validate(business)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[Business])
async def list_businesses(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Business))
    return result.all()


@router.get("/{id}", response_model=Business)
async def get_business(id: UUID, session: AsyncSession = Depends(get_session)):
    obj = await session.get(Business, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Business not found")
    return obj


@router.patch("/{id}", response_model=Business)
async def update_business(
    id: UUID, data: BusinessUpdate, session: AsyncSession = Depends(get_session)
):
    obj = await session.get(Business, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Business not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj
