import re
import uuid
from datetime import UTC, datetime
from datetime import date as date_type
from functools import wraps
from typing import Any

import structlog
from sqlalchemy import select, update

from receptionist.agent.state import Message, ReceptionistState, TimeSlot
from receptionist.db.models import (
    AgentEvent,
    AgentRun,
    Appointment,
    AppointmentStatus,
    Conversation,
    Customer,
    Service,
    Staff,
    TenantSetting,
)
from receptionist.db.models import (
    Message as MessageModel,
)
from receptionist.db.tenant import clear_current_tenant, set_current_tenant
from receptionist.llm.intent import IntentClassifier
from receptionist.tools.registry import ToolContext, ToolResult, get_tool
from receptionist.utils.datetime_utils import parse_relative_date, parse_time_of_day
from receptionist.utils.pii import redact_pii

logger = structlog.get_logger()
classifier = IntentClassifier()

ACTIONABLE_INTENTS = {
    "booking", "availability", "cancel", "reschedule", "appointment_lookup",
    "customer_lookup", "service_lookup", "services", "business_info", "faq",
}

SERVICE_ENTITY_PATTERN = r"\b(cleaning|checkup|filling|root canal|implant|consultation)\b"
APPOINTMENT_ID_PATTERN = r"\b(apt_[a-z0-9]+)\b"


def _session_factory():
    from receptionist.db.engine import async_session_factory
    return async_session_factory


def with_session(func):
    """Run a node with its own DB session when LangGraph provides none."""

    @wraps(func)
    async def wrapper(state: ReceptionistState, db_session: Any = None):
        if db_session is not None:
            return await func(state, db_session)
        async with _session_factory()() as session:
            result = await func(state, session)
            await session.commit()
            return result

    wrapper.__name__ = getattr(func, "__name__", "node")
    return wrapper


@with_session
async def load_session(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "LOAD_SESSION"
    state.execution_status = "processing"

    if not state.conversation_id:
        state.conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

    conversation = (await db_session.execute(
        select(Conversation).where(
            Conversation.id == state.conversation_id,
            Conversation.tenant_id == state.tenant_id,
        )
    )).scalar_one_or_none()

    if conversation is None:
        taken = (await db_session.execute(
            select(Conversation.id).where(Conversation.id == state.conversation_id)
        )).scalar_one_or_none()
        if taken:
            state.conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        conversation = Conversation(
            id=state.conversation_id,
            tenant_id=state.tenant_id,
            customer_id=state.customer_id,
            channel=state.channel,
        )
        db_session.add(conversation)
        await db_session.flush()
    else:
        state.customer_id = state.customer_id or conversation.customer_id

    msg_rows = (await db_session.execute(
        select(MessageModel)
        .where(MessageModel.conversation_id == state.conversation_id)
        .order_by(MessageModel.created_at.desc())
        .limit(20)
    )).scalars().all()
    state.conversation_history = [
        Message(role=m.role, content=m.content, timestamp=m.created_at)
        for m in reversed(msg_rows)
    ]

    return state


@with_session
async def load_tenant_context(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "LOAD_TENANT_CONTEXT"
    set_current_tenant(state.tenant_id)

    settings_result = await db_session.execute(
        select(TenantSetting).where(TenantSetting.tenant_id == state.tenant_id)
    )
    settings = settings_result.scalars().all()
    config = {s.key: s.value for s in settings}
    state.tenant_config = config
    state.timezone = config.get("timezone", "UTC")
    state.enabled_tools = config.get("enabled_tools", "").split(",") if config.get("enabled_tools") else []
    state.business_rules = {
        "min_cancellation_hours": int(config.get("min_cancellation_hours", "24")),
        "max_booking_horizon_days": int(config.get("max_booking_horizon_days", "90")),
        "buffer_minutes": int(config.get("buffer_minutes", "0")),
    }

    return state


async def intent_classifier(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "INTENT_CLASSIFIER"
    result = await classifier.aclassify(state.current_message, state.conversation_history)
    intent = result.intent
    confidence = result.confidence
    entities = dict(result.entities)

    # Multi-turn continuation: a short reply ("3 pm", "tomorrow") that does not
    # classify on its own inherits the intent of the last real user request.
    if intent == "unknown" and entities:
        for msg in reversed(state.conversation_history):
            if msg.role != "user":
                continue
            prev = classifier.classify(msg.content)
            if prev.intent in ACTIONABLE_INTENTS:
                intent = prev.intent
                confidence = 0.6
                break

    state.intent = intent
    state.confidence = confidence
    state.extracted_entities = entities
    logger.info(
        "intent_classified",
        intent=intent,
        confidence=confidence,
        tenant_id=state.tenant_id,
    )
    return state


def _normalize_date(raw: str, tz: str) -> str | None:
    if not raw:
        return None
    try:
        return date_type.fromisoformat(raw).isoformat()
    except ValueError:
        pass
    parsed = parse_relative_date(raw, tz)
    return parsed.isoformat() if parsed else None


def _normalize_time(raw: str) -> str | None:
    if not raw:
        return None
    if re.search(r"\b\d{1,2}:\d{2}\b", raw) or re.search(r"\b(am|pm)\b", raw.lower()):
        return parse_time_of_day(raw)
    if re.search(r"\b(morning|afternoon|evening|noon|midday|midnight)\b", raw.lower()):
        return parse_time_of_day(raw)
    return None


@with_session
async def entity_extraction(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "ENTITY_EXTRACTION"
    entities = dict(state.extracted_entities or {})
    user_messages = [m.content for m in state.conversation_history if m.role == "user"]
    user_messages.reverse()

    # --- date resolution -------------------------------------------------
    raw_date = entities.get("date")
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", state.current_message)
    if iso_match:
        raw_date = iso_match.group(1)
    resolved_date = _normalize_date(raw_date, state.timezone) if raw_date else None
    if not resolved_date:
        resolved_date = _normalize_date(state.current_message, state.timezone)
    if not resolved_date:
        for prev in user_messages:
            resolved_date = _normalize_date(prev, state.timezone)
            if resolved_date:
                break
    if resolved_date:
        state.requested_date = resolved_date

    # --- time resolution -------------------------------------------------
    resolved_time = _normalize_time(state.current_message)
    if not resolved_time and entities.get("time"):
        resolved_time = _normalize_time(entities["time"])
    if not resolved_time:
        for prev in user_messages:
            resolved_time = _normalize_time(prev)
            if resolved_time:
                break
    if resolved_time:
        state.requested_time = resolved_time

    # --- service name -> service ID -------------------------------------
    raw_service = state.selected_service or entities.get("service_name")
    if not raw_service:
        for prev in user_messages:
            m = re.search(SERVICE_ENTITY_PATTERN, prev, re.IGNORECASE)
            if m:
                raw_service = m.group(1)
                break
    if raw_service:
        svc = (await db_session.execute(
            select(Service).where(Service.tenant_id == state.tenant_id, Service.id == raw_service)
        )).scalar_one_or_none()
        if not svc:
            rows = (await db_session.execute(
                select(Service).where(
                    Service.tenant_id == state.tenant_id,
                    Service.is_active == True,
                )
            )).scalars().all()
            lowered = raw_service.lower().strip()
            svc = next((s for s in rows if s.name.lower() == lowered), None)
            if svc is None:
                svc = next(
                    (s for s in rows if lowered in s.name.lower() or s.name.lower() in lowered),
                    None,
                )
        if svc:
            state.selected_service = svc.id
            entities["service_name"] = svc.name
        else:
            state.selected_service = None
            entities.pop("service_name", None)

    # --- staff name -> staff ID -----------------------------------------
    raw_staff = state.selected_staff or entities.get("staff_name")
    if not raw_staff:
        for prev in user_messages:
            m = re.search(r"\b(dr\.?\s+\w+|sarah|ahmed|michael)\b", prev, re.IGNORECASE)
            if m:
                raw_staff = m.group(1)
                break
    if raw_staff:
        staff_rows = (await db_session.execute(
            select(Staff).where(Staff.tenant_id == state.tenant_id, Staff.is_active == True)
        )).scalars().all()
        lowered = raw_staff.lower().replace(".", "").strip()
        match = next(
            (
                s for s in staff_rows
                if lowered in s.name.lower().replace(".", "")
                or s.name.lower().replace(".", "") in lowered
            ),
            None,
        )
        if match:
            state.selected_staff = match.id
            entities["staff_name"] = match.name
        else:
            state.selected_staff = None
            entities.pop("staff_name", None)

    # --- customer resolution (request -> conversation -> phone/email) ----
    if not state.customer_id:
        candidates = [state.current_message] + user_messages
        email_entity = entities.get("email")
        phone_entity = entities.get("phone")
        for text in candidates:
            if not email_entity:
                m = re.search(r"\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b", text)
                if m:
                    email_entity = m.group(1)
            if not phone_entity:
                m = re.search(r"\b(\+?\d[\d\s().-]{7,}\d)\b", text)
                if m:
                    phone_entity = m.group(1)
        customer = None
        if email_entity:
            customer = (await db_session.execute(
                select(Customer).where(
                    Customer.tenant_id == state.tenant_id,
                    Customer.email.ilike(email_entity),
                )
            )).scalar_one_or_none()
        if not customer and phone_entity:
            digits = re.sub(r"\D", "", phone_entity)
            rows = (await db_session.execute(
                select(Customer).where(Customer.tenant_id == state.tenant_id)
            )).scalars().all()
            customer = next(
                (c for c in rows if c.phone and re.sub(r"\D", "", c.phone).endswith(digits[-7:])),
                None,
            )
        if customer:
            state.customer_id = customer.id
            entities["customer_name"] = f"{customer.first_name} {customer.last_name}".strip()

    # --- appointment resolution for cancel / reschedule ------------------
    if state.intent in ("cancel", "reschedule") and not state.appointment_id:
        m = re.search(APPOINTMENT_ID_PATTERN, state.current_message, re.IGNORECASE)
        if m:
            apt = (await db_session.execute(
                select(Appointment).where(
                    Appointment.id == m.group(1),
                    Appointment.tenant_id == state.tenant_id,
                )
            )).scalar_one_or_none()
            if apt and (not state.customer_id or apt.customer_id == state.customer_id):
                state.appointment_id = apt.id
                entities["resolved_appointment"] = {
                    "id": apt.id,
                    "start": apt.start_time.isoformat(),
                    "date": apt.start_time.date().isoformat(),
                    "time": apt.start_time.strftime("%H:%M"),
                }

        if not state.appointment_id and state.customer_id:
            now = datetime.now(UTC)
            upcoming = (await db_session.execute(
                select(Appointment).where(
                    Appointment.tenant_id == state.tenant_id,
                    Appointment.customer_id == state.customer_id,
                    Appointment.status.notin_([
                        AppointmentStatus.CANCELLED,
                        AppointmentStatus.NO_SHOW,
                        AppointmentStatus.COMPLETED,
                    ]),
                    Appointment.start_time >= now,
                ).order_by(Appointment.start_time.asc())
            )).scalars().all()

            if len(upcoming) == 1:
                apt = upcoming[0]
                state.appointment_id = apt.id
                entities["resolved_appointment"] = {
                    "id": apt.id,
                    "start": apt.start_time.isoformat(),
                    "date": apt.start_time.date().isoformat(),
                    "time": apt.start_time.strftime("%H:%M"),
                }
                if state.intent == "reschedule" and not state.requested_time:
                    state.requested_time = apt.start_time.strftime("%H:%M")
            elif len(upcoming) > 1:
                entities["upcoming_appointments"] = [
                    {
                        "id": a.id,
                        "start": a.start_time.strftime("%A, %B %d at %I:%M %p"),
                    }
                    for a in upcoming[:5]
                ]

    state.extracted_entities = entities

    # --- what is still missing before we can act ------------------------
    missing: list[str] = []
    if state.intent in ("booking", "availability"):
        if not state.selected_service:
            missing.append("service")
        if not state.requested_date:
            missing.append("date")
        if (
            state.intent == "booking"
            and state.selected_service
            and state.requested_date
            and state.requested_time
            and not state.customer_id
        ):
            missing.append("customer")
    elif state.intent == "reschedule":
        if not state.customer_id:
            missing.append("customer")
        elif not state.appointment_id:
            if entities.get("upcoming_appointments"):
                missing.append("appointment_choice")
            else:
                missing.append("appointment")
        if not state.requested_date:
            missing.append("date")
    elif state.intent == "cancel":
        if not state.customer_id:
            missing.append("customer")
        elif not state.appointment_id:
            if entities.get("upcoming_appointments"):
                missing.append("appointment_choice")
            else:
                missing.append("appointment")
    elif state.intent in ("appointment_lookup", "customer_lookup") and not state.customer_id:
        missing.append("customer")

    state.missing_information = missing
    return state


async def safety_check(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "SAFETY_CHECK"

    emergency_keywords = [
        "chest pain", "heart attack", "stroke", "severe bleeding",
        "can't breathe", "choking", "overdose", "suicide", "unconscious",
        "emergency", "911",
    ]
    msg_lower = state.current_message.lower()
    if state.intent == "emergency" or any(kw in msg_lower for kw in emergency_keywords):
        state.emergency_detected = True
        state.human_handoff_required = True
        logger.warning("emergency_detected", tenant_id=state.tenant_id)
        return state

    injection_patterns = [
        "ignore previous instructions",
        "ignore all previous",
        "you are now",
        "system prompt",
        "reveal your instructions",
        "delete all",
        "drop table",
    ]
    if any(p in msg_lower for p in injection_patterns):
        logger.warning("prompt_injection_attempt", tenant_id=state.tenant_id)
        state.human_handoff_required = True

    return state


async def dispatch_tool(state: ReceptionistState, db_session: Any) -> ReceptionistState:
    """Resolve the intent to a real tool call and store the result on state."""
    intent = state.intent
    ctx = ToolContext(
        tenant_id=state.tenant_id,
        conversation_id=state.conversation_id,
        customer_id=state.customer_id,
        db_session=db_session,
        enabled_tools=state.enabled_tools,
        run_id=state.agent_run_id,
    )

    tool_name: str | None = None
    args: Any = None

    if intent == "booking":
        from receptionist.tools.availability_tools import GetAvailabilityArgs
        from receptionist.tools.booking_tools import CreateBookingArgs

        if (
            state.selected_service and state.requested_date
            and state.requested_time and state.customer_id
        ):
            tool_name = "create_booking"
            args = CreateBookingArgs(
                customer_id=state.customer_id,
                service_id=state.selected_service,
                date=state.requested_date,
                time=state.requested_time,
                staff_id=state.selected_staff,
                timezone=state.timezone,
                idempotency_key=state.idempotency_key,
            )
        elif state.selected_service and state.requested_date:
            tool_name = "get_availability"
            args = GetAvailabilityArgs(
                service_id=state.selected_service,
                date=state.requested_date,
                staff_id=state.selected_staff,
                timezone=state.timezone,
            )
    elif intent == "availability":
        from receptionist.tools.availability_tools import GetAvailabilityArgs

        if state.selected_service and state.requested_date:
            tool_name = "get_availability"
            args = GetAvailabilityArgs(
                service_id=state.selected_service,
                date=state.requested_date,
                staff_id=state.selected_staff,
                timezone=state.timezone,
            )
    elif intent == "cancel":
        from receptionist.tools.cancellation_tools import CancelBookingArgs

        if state.appointment_id and state.customer_id:
            tool_name = "cancel_booking"
            args = CancelBookingArgs(
                appointment_id=state.appointment_id,
                customer_id=state.customer_id,
                idempotency_key=state.idempotency_key,
            )
    elif intent == "reschedule":
        from receptionist.tools.reschedule_tools import RescheduleBookingArgs

        if state.appointment_id and state.customer_id and state.requested_date:
            tool_name = "reschedule_booking"
            args = RescheduleBookingArgs(
                appointment_id=state.appointment_id,
                customer_id=state.customer_id,
                new_date=state.requested_date,
                new_time=state.requested_time or "10:00",
                timezone=state.timezone,
                idempotency_key=state.idempotency_key,
            )
    elif intent == "appointment_lookup":
        from receptionist.tools.customer_tools import GetCustomerAppointmentsArgs

        if state.customer_id:
            tool_name = "get_customer_appointments"
            args = GetCustomerAppointmentsArgs(customer_id=state.customer_id)
    elif intent == "customer_lookup":
        from receptionist.tools.customer_tools import GetCustomerArgs

        if state.customer_id:
            tool_name = "get_customer"
            args = GetCustomerArgs(customer_id=state.customer_id)
    elif intent in ("service_lookup", "services"):
        from receptionist.tools.service_tools import ListServicesArgs

        tool_name = "list_services"
        args = ListServicesArgs()
    elif intent == "business_info":
        from receptionist.tools.business_tools import GetBusinessInfoArgs

        tool_name = "get_business_info"
        args = GetBusinessInfoArgs()
    elif intent == "faq":
        from receptionist.tools.faq_tools import SearchFAQArgs

        tool_name = "search_faq"
        args = SearchFAQArgs(query=state.current_message)

    if not tool_name or args is None:
        return state

    tool_def = get_tool(tool_name)
    if not tool_def:
        state.error = f"Tool '{tool_name}' not found"
        logger.error("tool_not_found", tool_name=tool_name)
        return state

    try:
        result = await tool_def.func(args, ctx)
    except Exception as e:  # noqa: BLE001 - tool boundary converts any error to a ToolResult
        logger.error("tool_execution_failed", tool_name=tool_name, error=str(e), tenant_id=state.tenant_id)
        result = ToolResult(
            success=False,
            error="The request could not be completed due to an unexpected error.",
        )

    state.tool_name = tool_name
    state.tool_arguments = args.model_dump()
    state.tool_result = result.to_dict()

    if tool_name == "get_availability" and result.success and result.data:
        state.available_slots = [TimeSlot(**s) for s in result.data]

    logger.info(
        "tool_executed",
        tool_name=tool_name,
        success=result.success,
        tenant_id=state.tenant_id,
    )
    return state


@with_session
async def human_handoff_handler(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "HUMAN_HANDOFF"
    state.human_handoff_required = True

    from receptionist.tools.human_handoff_tools import CreateHandoffArgs, create_handoff
    ctx = ToolContext(
        tenant_id=state.tenant_id,
        conversation_id=state.conversation_id,
        customer_id=state.customer_id,
        db_session=db_session,
        run_id=state.agent_run_id,
    )
    args = CreateHandoffArgs(
        reason="Customer requested human agent",
        priority="medium",
        customer_id=state.customer_id,
    )
    await create_handoff(args, ctx)

    state.response = "I'm connecting you to a human agent who can help you with this. Please hold on."
    return state


@with_session
async def emergency_handler(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "EMERGENCY"
    state.emergency_detected = True
    state.human_handoff_required = True

    from receptionist.tools.human_handoff_tools import CreateHandoffArgs, create_handoff
    ctx = ToolContext(
        tenant_id=state.tenant_id,
        conversation_id=state.conversation_id,
        customer_id=state.customer_id,
        db_session=db_session,
        run_id=state.agent_run_id,
    )
    args = CreateHandoffArgs(
        reason="Emergency detected in conversation",
        priority="high",
        customer_id=state.customer_id,
    )
    await create_handoff(args, ctx)

    return await response_generation(state, db_session)


def _friendly_date(iso: str | None) -> str:
    if not iso:
        return "the requested date"
    try:
        return date_type.fromisoformat(iso[:10]).strftime("%A, %B %d")
    except ValueError:
        return iso


def _friendly_time(hhmm: str | None) -> str:
    if not hhmm:
        return "the requested time"
    try:
        h, m = map(int, hhmm.split(":"))
        return f"{((h + 11) % 12) + 1:02d}:{m:02d} {'AM' if h < 12 else 'PM'}"
    except ValueError:
        return hhmm


def _format_tool_success(state: ReceptionistState, tr: dict) -> str:
    data = tr.get("data") or {}
    entities = state.extracted_entities or {}
    tool = state.tool_name

    if tool == "create_booking":
        when = (
            f"{_friendly_date(data.get('date'))} at {_friendly_time(data.get('time'))}"
        )
        parts = [(f"Your {data.get('service') or entities.get('service_name') or 'appointment'} "
                  f"appointment is confirmed for {when}")]
        if data.get("staff"):
            parts.append(f" with {data['staff']}")
        parts.append(f". Appointment ID: {data.get('appointment_id')}.")
        return "".join(parts)

    if tool == "get_availability":
        slots = state.available_slots
        if slots:
            lines = [
                f"- {_friendly_time(s.start_time)}"
                + (f" with {s.staff_name}" if s.staff_name else "")
                for s in slots[:5]
            ]
            return (
                f"Here are the open times on {_friendly_date(state.requested_date)}:\n"
                + "\n".join(lines)
                + "\nWhich time would you prefer?"
            )
        return (
            f"There are no open times on {_friendly_date(state.requested_date)}. "
            "Would you like to try a different day?"
        )

    if tool == "cancel_booking":
        apt = entities.get("resolved_appointment") or {}
        if apt.get("start"):
            when = _friendly_date(apt.get("date")) + " at " + _friendly_time(apt.get("time"))
            return f"Your appointment on {when} has been cancelled. Appointment ID: {apt.get('id')}."
        return f"Your appointment {data.get('appointment_id', '')} has been cancelled."

    if tool == "reschedule_booking":
        return (
            f"Your appointment has been rescheduled to {_friendly_date(data.get('new_date'))} "
            f"at {_friendly_time(data.get('new_time'))}."
        )

    if tool == "get_customer_appointments":
        if not data:
            return "You don't have any appointments on file."
        lines = []
        for apt in data[:5]:
            try:
                start = datetime.fromisoformat(apt["start_time"])
                when = start.strftime("%A, %B %d at %I:%M %p")
            except (KeyError, ValueError):
                when = apt.get("start_time", "unknown time")
            label = apt.get("service") or "appointment"
            lines.append(f"- {when}: {label} ({apt.get('status', 'unknown')}) [ID: {apt.get('id')}]")
        return "Here are your appointments:\n" + "\n".join(lines)

    if tool == "list_services":
        lines = [
            f"- {s.get('name')} ({s.get('duration_minutes')} min, ${s.get('price')})"
            for s in data[:10]
        ]
        return "These are the services we offer:\n" + "\n".join(lines)

    if tool == "get_business_info":
        lines = [f"{data.get('business_name')}"]
        if data.get("phone"):
            lines.append(f"Phone: {data['phone']}")
        if data.get("email"):
            lines.append(f"Email: {data['email']}")
        if data.get("address"):
            lines.append(f"Address: {data['address']}")
        return "\n".join(lines)

    if tool == "search_faq":
        if data:
            return data[0].get("answer", "I don't have an answer for that.")
        return (
            "I don't have that information on hand. "
            "Would you like me to connect you with our team?"
        )

    if tool == "get_customer":
        return (
            f"I found your record: {data.get('first_name', '')} {data.get('last_name', '')}. "
            f"Email: {data.get('email')}, phone: {data.get('phone')}."
        )

    if data:
        return "Done — I've completed your request."
    return "I've completed your request."


async def response_generation(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "RESPONSE_GENERATION"

    if state.emergency_detected:
        emergency_msg = state.tenant_config.get(
            "emergency_instructions",
            "If this is a medical emergency, please call your local emergency services (911) immediately. "
            "I'm connecting you to a human agent who can assist you further."
        )
        state.response = emergency_msg
        return state

    if state.human_handoff_required:
        state.response = state.response or (
            "I'm connecting you to a human agent who can help you with this. Please hold on."
        )
        return state

    if state.missing_information:
        missing = state.missing_information
        if "appointment_choice" in missing:
            apts = (state.extracted_entities or {}).get("upcoming_appointments", [])
            verb = "cancel" if state.intent == "cancel" else "reschedule"
            lines = [f"- {a.get('id')} ({a.get('start')})" for a in apts]
            state.response = (
                f"I found {len(apts)} upcoming appointments:\n"
                + "\n".join(lines)
                + f"\nWhich one would you like to {verb}? "
                "You can reply with the appointment ID."
            )
            return state
        questions = {
            "service": "Which service would you like?",
            "date": "What day would you prefer?",
            "time": "What time works best for you?",
            "customer": (
                "Could you share the phone number or email address on your account "
                "so I can find your record?"
            ),
            "appointment": (
                "I couldn't find an upcoming appointment on your account. "
                "Could you provide your appointment ID?"
            ),
        }
        missing_questions = [questions.get(m, f"Could you provide {m}?") for m in missing]
        state.response = " ".join(missing_questions)
        return state

    if state.tool_result is not None:
        tr = state.tool_result if isinstance(state.tool_result, dict) else {"success": False}
        if tr.get("success"):
            state.response = _format_tool_success(state, tr)
        else:
            error = tr.get("error") or "unexpected error"
            state.response = (
                "Sorry, I wasn't able to complete that request: " + redact_pii(str(error))
            )
        return state

    if state.intent in ACTIONABLE_INTENTS:
        state.response = (
            "I wasn't able to complete that just now. "
            "Could you give me a few more details?"
        )
        return state

    state.response = (
        "Hello! How can I help you today? I can assist with booking appointments, "
        "checking availability, or answering questions about our services."
    )
    return state


@with_session
async def save_conversation(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "SAVE_CONVERSATION"

    if not state.conversation_id:
        return state

    conversation = (await db_session.execute(
        select(Conversation).where(
            Conversation.id == state.conversation_id,
            Conversation.tenant_id == state.tenant_id,
        )
    )).scalar_one_or_none()
    if conversation is None:
        conversation = Conversation(
            id=state.conversation_id,
            tenant_id=state.tenant_id,
            customer_id=state.customer_id,
            channel=state.channel,
        )
        db_session.add(conversation)
    elif state.customer_id and not conversation.customer_id:
        conversation.customer_id = state.customer_id

    db_session.add(MessageModel(
        conversation_id=state.conversation_id,
        role="user",
        content=redact_pii(state.current_message),
    ))
    if state.response:
        db_session.add(MessageModel(
            conversation_id=state.conversation_id,
            role="assistant",
            content=state.response,
        ))

    await db_session.flush()
    return state


@with_session
async def update_agent_state(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "UPDATE_AGENT_STATE"
    state.execution_status = "completed"

    if state.agent_run_id:
        status = "failed" if state.error else "completed"
        await db_session.execute(
            update(AgentRun)
            .where(AgentRun.id == state.agent_run_id)
            .values(status=status, completed_at=datetime.now(UTC))
        )
        db_session.add(AgentEvent(
            run_id=state.agent_run_id,
            event_type="run_completed",
            node_name="update_agent_state",
            status=status,
        ))

    clear_current_tenant()
    return state


@with_session
async def create_agent_run(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "CREATE_AGENT_RUN"
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    state.agent_run_id = run_id

    db_session.add(AgentRun(
        id=run_id,
        conversation_id=state.conversation_id,
        tenant_id=state.tenant_id,
        status="running",
        started_at=datetime.now(UTC),
    ))
    await db_session.flush()
    db_session.add(AgentEvent(
        run_id=run_id,
        event_type="run_started",
        node_name="create_agent_run",
        status="running",
    ))
    await db_session.flush()
    return state


async def _run_handler(
    state: ReceptionistState, session: Any, node_name: str, dispatch: bool
) -> ReceptionistState:
    state.current_node = node_name.upper()
    if dispatch:
        state = await dispatch_tool(state, session)
    state = await response_generation(state, session)
    return state


def make_handler(node_name: str, dispatch: bool = True):
    """Build a graph node that runs the intent's tool (optional) then renders a response."""

    async def handler(state: ReceptionistState, db_session: Any = None):
        if db_session is not None:
            return await _run_handler(state, db_session, node_name, dispatch)
        async with _session_factory()() as session:
            result = await _run_handler(state, session, node_name, dispatch)
            await session.commit()
            return result

    handler.__name__ = node_name
    return handler
