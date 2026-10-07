import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from receptionist.agent.state import ReceptionistState, Message
from receptionist.llm.classifier import RuleBasedIntentClassifier
from receptionist.db.models import Conversation, Message as MessageModel, AgentRun, AgentEvent, TenantSetting
from receptionist.db.tenant import set_current_tenant, clear_current_tenant
from receptionist.utils.pii import redact_pii
import structlog

logger = structlog.get_logger()
classifier = RuleBasedIntentClassifier()


async def load_session(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "LOAD_SESSION"
    state.execution_status = "processing"

    if db_session and state.conversation_id:
        conv_result = await db_session.execute(
            select(Conversation).where(Conversation.id == state.conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()
        if conversation:
            state.customer_id = state.customer_id or conversation.customer_id

        msg_result = await db_session.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == state.conversation_id)
            .order_by(MessageModel.created_at)
            .limit(20)
        )
        messages = msg_result.scalars().all()
        state.conversation_history = [
            Message(role=m.role, content=m.content, timestamp=m.created_at)
            for m in messages
        ]

    return state


async def load_tenant_context(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "LOAD_TENANT_CONTEXT"
    set_current_tenant(state.tenant_id)

    if db_session:
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
    result = classifier.classify(state.current_message)
    state.intent = result.intent
    state.confidence = result.confidence
    state.extracted_entities = result.entities
    logger.info(
        "intent_classified",
        intent=result.intent,
        confidence=result.confidence,
        tenant_id=state.tenant_id,
    )
    return state


async def entity_extraction(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "ENTITY_EXTRACTION"

    entities = state.extracted_entities
    if "date" in entities:
        state.requested_date = entities["date"]
    if "time" in entities:
        state.requested_time = entities["time"]
    if "staff_name" in entities:
        state.selected_staff = entities["staff_name"]
    if "service_name" in entities:
        state.selected_service = entities["service_name"]

    missing = []
    if state.intent in ("booking", "availability"):
        if not state.selected_service:
            missing.append("service")
        if not state.requested_date:
            missing.append("date")
    elif state.intent == "reschedule":
        if not state.appointment_id:
            missing.append("appointment_id")
        if not state.requested_date:
            missing.append("date")
    elif state.intent == "cancel":
        if not state.appointment_id:
            missing.append("appointment_id")

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
    if any(kw in msg_lower for kw in emergency_keywords):
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


async def human_handoff_handler(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "HUMAN_HANDOFF"
    state.human_handoff_required = True

    if db_session:
        from receptionist.tools.human_handoff_tools import CreateHandoffArgs
        from receptionist.tools.registry import ToolContext
        ctx = ToolContext(
            tenant_id=state.tenant_id,
            conversation_id=state.conversation_id,
            customer_id=state.customer_id,
            db_session=db_session,
        )
        args = CreateHandoffArgs(
            reason="Customer requested human agent",
            priority="medium",
            customer_id=state.customer_id,
        )
        from receptionist.tools.human_handoff_tools import create_handoff
        await create_handoff(args, ctx)

    state.response = "I'm connecting you to a human agent who can help you with this. Please hold on."
    return state


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
        state.response = "I'm connecting you to a human agent who can help you with this. Please hold on."
        return state

    if state.missing_information:
        questions = {
            "service": "Which service would you like?",
            "date": "What day would you prefer?",
            "time": "What time works best for you?",
            "appointment_id": "Could you provide your appointment ID or the date of your appointment?",
        }
        missing_questions = [questions.get(m, f"Could you provide {m}?") for m in state.missing_information]
        state.response = " ".join(missing_questions)
        return state

    if state.intent == "booking" and state.available_slots:
        slots_text = "\n".join(
            f"- {s.start_time}" for s in state.available_slots[:5]
        )
        state.response = f"Here are the available times:\n{slots_text}\nWhich would you prefer?"
        return state

    if state.intent == "booking" and state.tool_result:
        if isinstance(state.tool_result, dict) and state.tool_result.get("success"):
            apt = state.tool_result.get("data", {})
            state.response = (
                f"Your appointment is confirmed for {apt.get('date', 'the requested date')} "
                f"at {apt.get('time', 'the requested time')}"
            )
            return state

    if state.intent == "general_conversation" or not state.response:
        state.response = "Hello! How can I help you today? I can assist with booking appointments, checking availability, or answering questions about our services."

    return state


async def save_conversation(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "SAVE_CONVERSATION"

    if db_session and state.conversation_id:
        user_msg = MessageModel(
            conversation_id=state.conversation_id,
            role="user",
            content=redact_pii(state.current_message),
        )
        db_session.add(user_msg)

        if state.response:
            assistant_msg = MessageModel(
                conversation_id=state.conversation_id,
                role="assistant",
                content=state.response,
            )
            db_session.add(assistant_msg)

        await db_session.flush()

    return state


async def update_agent_state(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    state.current_node = "UPDATE_AGENT_STATE"
    state.execution_status = "completed"

    if db_session and state.agent_run_id:
        await db_session.execute(
            AgentRun.__table__.update()
            .where(AgentRun.id == state.agent_run_id)
            .values(
                status="completed",
                completed_at=datetime.now(timezone.utc),
            )
        )

    clear_current_tenant()
    return state


async def create_agent_run(state: ReceptionistState, db_session: Any = None) -> ReceptionistState:
    run_id = str(uuid.uuid4())
    state.agent_run_id = run_id

    if db_session:
        agent_run = AgentRun(
            id=run_id,
            conversation_id=state.conversation_id,
            tenant_id=state.tenant_id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(agent_run)
        await db_session.flush()

    return state
