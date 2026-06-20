from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db import get_session
from src.models.customer import Customer, CustomerBase, CustomerUpdate

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post("/", response_model=Customer)
async def create_customer(
    customer: CustomerBase, session: AsyncSession = Depends(get_session)
):
    db_obj = Customer.model_validate(customer)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[Customer])
async def list_customers(
    business_id: Optional[UUID] = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(Customer)
    if business_id is not None:
        query = query.where(Customer.business_id == business_id)
    result = await session.exec(query)
    return result.all()


@router.get("/{id}", response_model=Customer)
async def get_customer(id: UUID, session: AsyncSession = Depends(get_session)):
    obj = await session.get(Customer, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Customer not found")
    return obj


@router.patch("/{id}", response_model=Customer)
async def update_customer(
    id: UUID, data: CustomerUpdate, session: AsyncSession = Depends(get_session)
):
    obj = await session.get(Customer, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Customer not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj
