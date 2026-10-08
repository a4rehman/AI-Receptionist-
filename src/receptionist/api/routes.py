import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy import select
from receptionist.api.schemas import (
    ChatRequest, ChatResponse, AppointmentResponse, AvailabilityRequest,
    AvailabilityResponse, ServiceResponse, StaffResponse, CustomerResponse,
    HandoffRequest, HandoffResponse, AgentRunResponse, AgentEventResponse,
)
from receptionist.agent.state import ReceptionistState
from receptionist.agent.graph import receptionist_graph
from receptionist.db.engine import async_session_factory
from receptionist.db.models import (
    Appointment, Service, Staff, Customer, Conversation,
    AgentRun, AgentEvent, HumanHandoff, Tenant,
)
from receptionist.db.tenant import set_current_tenant, clear_current_tenant
from receptionist.services.availability import AvailabilityService

router = APIRouter(prefix="/api/v1")


async def get_tenant_id(x_tenant_id: str = Header(...)) -> str:
    return x_tenant_id


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"

    state = ReceptionistState(
        tenant_id=request.tenant_id,
        conversation_id=conversation_id,
        customer_id=request.customer_id,
        channel=request.channel,
        current_message=request.message,
        idempotency_key=request.idempotency_key,
    )

    set_current_tenant(request.tenant_id)
    try:
        async with async_session_factory() as session:
            tenant_result = await session.execute(
                select(Tenant).where(Tenant.id == request.tenant_id, Tenant.is_active == True)  # noqa: E712
            )
            if tenant_result.scalar_one_or_none() is None:
                raise HTTPException(status_code=404, detail="Unknown tenant")

        result = await receptionist_graph.ainvoke(
            state.model_dump(),
            config={"configurable": {"thread_id": conversation_id}},
        )
    finally:
        clear_current_tenant()

    return ChatResponse(
        conversation_id=result.get("conversation_id") or conversation_id,
        response=result.get("response", "I'm sorry, I couldn't process that request."),
        status=result.get("execution_status", "completed"),
        intent=result.get("intent"),
        available_actions=[],
    )


@router.get("/appointments", response_model=list[AppointmentResponse])
async def list_appointments(
    tenant_id: str = Depends(get_tenant_id),
    customer_id: Optional[str] = None,
    status: Optional[str] = None,
):
    set_current_tenant(tenant_id)
    try:
        async with async_session_factory() as session:
            query = select(Appointment).where(Appointment.tenant_id == tenant_id)
            if customer_id:
                query = query.where(Appointment.customer_id == customer_id)
            if status:
                query = query.where(Appointment.status == status)
            result = await session.execute(query.order_by(Appointment.start_time.desc()).limit(100))
            appointments = result.scalars().all()
            return [
                AppointmentResponse(
                    id=a.id, tenant_id=a.tenant_id, customer_id=a.customer_id,
                    staff_id=a.staff_id, service_id=a.service_id,
                    start_time=a.start_time, end_time=a.end_time,
                    status=a.status.value if a.status else "unknown",
                )
                for a in appointments
            ]
    finally:
        clear_current_tenant()


@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(appointment_id: str, tenant_id: str = Depends(get_tenant_id)):
    set_current_tenant(tenant_id)
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Appointment).where(Appointment.id == appointment_id, Appointment.tenant_id == tenant_id)
            )
            apt = result.scalar_one_or_none()
            if not apt:
                raise HTTPException(status_code=404, detail="Appointment not found")
            return AppointmentResponse(
                id=apt.id, tenant_id=apt.tenant_id, customer_id=apt.customer_id,
                staff_id=apt.staff_id, service_id=apt.service_id,
                start_time=apt.start_time, end_time=apt.end_time,
                status=apt.status.value if apt.status else "unknown",
            )
    finally:
        clear_current_tenant()


@router.get("/availability", response_model=AvailabilityResponse)
async def get_availability(
    tenant_id: str = Depends(get_tenant_id),
    service_id: str = Query(...),
    date: str = Query(...),
    staff_id: Optional[str] = None,
    timezone: str = "UTC",
):
    set_current_tenant(tenant_id)
    try:
        async with async_session_factory() as session:
            service = AvailabilityService(session)
            from datetime import date as date_type
            target_date = date_type.fromisoformat(date)
            slots = await service.get_available_slots(
                tenant_id=tenant_id, service_id=service_id,
                target_date=target_date, staff_id=staff_id, timezone=timezone,
            )
            return AvailabilityResponse(slots=slots)
    finally:
        clear_current_tenant()


@router.get("/services", response_model=list[ServiceResponse])
async def list_services(tenant_id: str = Depends(get_tenant_id)):
    set_current_tenant(tenant_id)
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Service).where(Service.tenant_id == tenant_id, Service.is_active == True)
            )
            services = result.scalars().all()
            return [
                ServiceResponse(
                    id=s.id, name=s.name, description=s.description,
                    duration_minutes=s.duration_minutes, price=s.price, currency=s.currency,
                )
                for s in services
            ]
    finally:
        clear_current_tenant()


@router.get("/staff", response_model=list[StaffResponse])
async def list_staff(tenant_id: str = Depends(get_tenant_id)):
    set_current_tenant(tenant_id)
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Staff).where(Staff.tenant_id == tenant_id, Staff.is_active == True)
            )
            staff_list = result.scalars().all()
            return [
                StaffResponse(
                    id=s.id, name=s.name, role=s.role,
                    specialization=s.specialization, department=s.department,
                )
                for s in staff_list
            ]
    finally:
        clear_current_tenant()


@router.get("/customers", response_model=list[CustomerResponse])
async def list_customers(tenant_id: str = Depends(get_tenant_id)):
    set_current_tenant(tenant_id)
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Customer).where(Customer.tenant_id == tenant_id).limit(100)
            )
            customers = result.scalars().all()
            return [
                CustomerResponse(
                    id=c.id, first_name=c.first_name, last_name=c.last_name,
                    email=c.email, phone=c.phone,
                )
                for c in customers
            ]
    finally:
        clear_current_tenant()


@router.post("/handoff", response_model=HandoffResponse)
async def create_handoff(request: HandoffRequest):
    set_current_tenant(request.tenant_id)
    try:
        async with async_session_factory() as session:
            handoff = HumanHandoff(
                id=f"ho_{uuid.uuid4().hex[:12]}",
                tenant_id=request.tenant_id,
                conversation_id=request.conversation_id,
                customer_id=request.customer_id,
                reason=request.reason,
                priority=request.priority,
                status="open",
            )
            session.add(handoff)
            await session.commit()
            return HandoffResponse(id=handoff.id, status=handoff.status, priority=handoff.priority)
    finally:
        clear_current_tenant()


@router.get("/agent-runs", response_model=list[AgentRunResponse])
async def list_agent_runs(
    tenant_id: str = Depends(get_tenant_id),
    conversation_id: Optional[str] = None,
):
    set_current_tenant(tenant_id)
    try:
        async with async_session_factory() as session:
            query = select(AgentRun).where(AgentRun.tenant_id == tenant_id)
            if conversation_id:
                query = query.where(AgentRun.conversation_id == conversation_id)
            result = await session.execute(query.order_by(AgentRun.started_at.desc()).limit(50))
            runs = result.scalars().all()
            return [
                AgentRunResponse(
                    id=r.id, conversation_id=r.conversation_id, status=r.status,
                    started_at=r.started_at, completed_at=r.completed_at,
                )
                for r in runs
            ]
    finally:
        clear_current_tenant()


@router.get("/agent-events", response_model=list[AgentEventResponse])
async def list_agent_events(
    tenant_id: str = Depends(get_tenant_id),
    run_id: Optional[str] = None,
):
    set_current_tenant(tenant_id)
    try:
        async with async_session_factory() as session:
            query = select(AgentEvent).join(AgentRun).where(AgentRun.tenant_id == tenant_id)
            if run_id:
                query = query.where(AgentEvent.run_id == run_id)
            result = await session.execute(query.order_by(AgentEvent.created_at.desc()).limit(100))
            events = result.scalars().all()
            return [
                AgentEventResponse(
                    id=e.id, run_id=e.run_id, event_type=e.event_type,
                    node_name=e.node_name, tool_name=e.tool_name,
                    status=e.status, duration_ms=e.duration_ms, created_at=e.created_at,
                )
                for e in events
            ]
    finally:
        clear_current_tenant()
