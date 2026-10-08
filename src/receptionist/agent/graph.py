from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from receptionist.agent.state import ReceptionistState
from receptionist.agent.nodes import (
    load_session, load_tenant_context, create_agent_run, intent_classifier,
    entity_extraction, safety_check, response_generation, save_conversation,
    update_agent_state, human_handoff_handler, emergency_handler, make_handler,
)
from receptionist.agent.router import route_by_intent


def build_graph():
    graph = StateGraph(ReceptionistState)

    graph.add_node("load_session", load_session)
    graph.add_node("load_tenant_context", load_tenant_context)
    graph.add_node("create_agent_run", create_agent_run)
    graph.add_node("intent_classifier", intent_classifier)
    graph.add_node("entity_extraction", entity_extraction)
    graph.add_node("safety_check", safety_check)
    graph.add_node("router", lambda s: s)
    graph.add_node("ask_missing_info", response_generation)
    graph.add_node("faq_handler", make_handler("faq_handler"))
    graph.add_node("service_handler", make_handler("service_handler"))
    graph.add_node("business_info_handler", make_handler("business_info_handler"))
    graph.add_node("availability_handler", make_handler("availability_handler"))
    graph.add_node("booking_handler", make_handler("booking_handler"))
    graph.add_node("reschedule_handler", make_handler("reschedule_handler"))
    graph.add_node("cancel_handler", make_handler("cancel_handler"))
    graph.add_node("appointment_lookup_handler", make_handler("appointment_lookup_handler"))
    graph.add_node("customer_lookup_handler", make_handler("customer_lookup_handler"))
    graph.add_node("human_handoff_handler", human_handoff_handler)
    graph.add_node("emergency_handler", emergency_handler)
    graph.add_node("general_handler", make_handler("general_handler", dispatch=False))
    graph.add_node("save_conversation", save_conversation)
    graph.add_node("update_agent_state", update_agent_state)

    graph.set_entry_point("load_session")
    graph.add_edge("load_session", "load_tenant_context")
    graph.add_edge("load_tenant_context", "create_agent_run")
    graph.add_edge("create_agent_run", "intent_classifier")
    graph.add_edge("intent_classifier", "entity_extraction")
    graph.add_edge("entity_extraction", "safety_check")
    graph.add_edge("safety_check", "router")
    graph.add_conditional_edges("router", route_by_intent)
    graph.add_edge("ask_missing_info", "save_conversation")
    graph.add_edge("faq_handler", "save_conversation")
    graph.add_edge("service_handler", "save_conversation")
    graph.add_edge("business_info_handler", "save_conversation")
    graph.add_edge("availability_handler", "save_conversation")
    graph.add_edge("booking_handler", "save_conversation")
    graph.add_edge("reschedule_handler", "save_conversation")
    graph.add_edge("cancel_handler", "save_conversation")
    graph.add_edge("appointment_lookup_handler", "save_conversation")
    graph.add_edge("customer_lookup_handler", "save_conversation")
    graph.add_edge("human_handoff_handler", "save_conversation")
    graph.add_edge("emergency_handler", "save_conversation")
    graph.add_edge("general_handler", "save_conversation")
    graph.add_edge("save_conversation", "update_agent_state")
    graph.add_edge("update_agent_state", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


receptionist_graph = build_graph()
