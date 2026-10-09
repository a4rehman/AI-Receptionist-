from typing import TypeVar

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from receptionist.db.models import Base
from receptionist.db.tenant import get_current_tenant

ModelT = TypeVar("ModelT", bound=Base)


class TenantRepository:
    def __init__(self, model: type[ModelT], session: AsyncSession):
        self.model = model
        self.session = session

    def _tenant_filter(self, tenant_id: str | None = None):
        tid = tenant_id or get_current_tenant()
        if tid is None:
            raise PermissionError("No tenant context set")
        return self.model.tenant_id == tid

    async def get_by_id(self, id: str, tenant_id: str | None = None) -> ModelT | None:
        stmt = select(self.model).where(and_(self.model.id == id, self._tenant_filter(tenant_id)))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, tenant_id: str | None = None, **filters) -> list[ModelT]:
        stmt = select(self.model).where(self._tenant_filter(tenant_id))
        for key, value in filters.items():
            if value is not None and hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, obj: ModelT, tenant_id: str | None = None) -> ModelT:
        if tenant_id:
            obj.tenant_id = tenant_id
        elif not obj.tenant_id:
            obj.tenant_id = get_current_tenant()
            if obj.tenant_id is None:
                raise PermissionError("No tenant context set")
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, id: str, tenant_id: str | None = None, **kwargs) -> ModelT | None:
        stmt = (
            update(self.model)
            .where(and_(self.model.id == id, self._tenant_filter(tenant_id)))
            .values(**kwargs)
            .execution_options(synchronize_session="fetch")
        )
        await self.session.execute(stmt)
        return await self.get_by_id(id, tenant_id)

    async def delete(self, id: str, tenant_id: str | None = None) -> bool:
        stmt = delete(self.model).where(and_(self.model.id == id, self._tenant_filter(tenant_id)))
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def exists(self, id: str, tenant_id: str | None = None) -> bool:
        stmt = select(self.model.id).where(and_(self.model.id == id, self._tenant_filter(tenant_id)))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
