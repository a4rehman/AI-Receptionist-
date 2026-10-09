from receptionist.agent.state import ReceptionistState

INTENT_TO_NODE = {
    "faq": "faq_handler",
    "services": "service_handler",
    "service_lookup": "service_handler",
    "business_info": "business_info_handler",
    "availability": "availability_handler",
    "booking": "booking_handler",
    "reschedule": "reschedule_handler",
    "cancel": "cancel_handler",
    "appointment_lookup": "appointment_lookup_handler",
    "customer_lookup": "customer_lookup_handler",
    "human_handoff": "human_handoff_handler",
    "emergency": "emergency_handler",
    "general_conversation": "general_handler",
    "unknown": "general_handler",
}


def route_by_intent(state: ReceptionistState) -> str:
    if state.emergency_detected:
        return "emergency_handler"
    if state.human_handoff_required:
        return "human_handoff_handler"
    if state.missing_information:
        return "ask_missing_info"
    return INTENT_TO_NODE.get(state.intent, "general_handler")
