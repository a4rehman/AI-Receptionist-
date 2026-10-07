import re
from typing import Any
from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    intent: str = "unknown"
    confidence: float = 0.0
    entities: dict[str, Any] = Field(default_factory=dict)


INTENT_PATTERNS: dict[str, list[str]] = {
    "booking": [
        r"\b(book|schedule|make|set up|arrange)\b.*\b(appointment|booking|reservation|slot|visit)\b",
        r"\b(book|schedule|make)\b.*\b(dentist|doctor|stylist|haircut|cleaning|consultation|table|room)\b",
        r"\b(i want|i need|i'd like|can i get)\b.*\b(appointment|booking|reservation)\b",
        r"\b(available|availability|free|open)\b.*\b(slot|time|appointment)\b",
        r"\bi want\b.*\b(cleaning|checkup|filling|haircut|facial|massage|consultation|treatment)\b",
    ],
    "availability": [
        r"\b(what|which|any)\b.*\b(slot|time|availability)\b.*\b(available|free|open)\b",
        r"\b(when|what time)\b.*\b(available|free|open)\b",
        r"\b(check|see)\b.*\b(availability|schedule)\b",
        r"\b(available|availability|free)\b.*\b(slot|time)\b",
        r"\b(what|which|any)\b.*\b(time|slot)\b.*\b(available|free|open)\b.*\?",
        r"\bwhat times?\b.*\bavailable\b",
    ],
    "reschedule": [
        r"\b(reschedule|move|change|postpone)\b.*\b(appointment|booking|reservation)\b",
        r"\b(move|change)\b.*\b(to|for)\b.*\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today)\b",
    ],
    "cancel": [
        r"\b(cancel|delete|remove)\b.*\b(appointment|booking|reservation)\b",
        r"\b(cancel|delete)\b.*\b(it|that|my)\b",
    ],
    "appointment_lookup": [
        r"\b(what|which|my|show|list|check)\b.*\b(appointment|booking|reservation)\b",
        r"\b(do i have|i have)\b.*\b(appointment|booking|reservation)\b",
        r"\b(when|what time)\b.*\b(my|the)\b.*\b(appointment|booking)\b",
        r"\b(appointment|booking|reservation)\b.*\b(do i have|i have|what|which|my)\b",
        r"\bwhat appointments?\b.*\b(do i have|i have|my)\b",
    ],
    "customer_lookup": [
        r"\b(who am i|my info|my details|my profile|my record)\b",
        r"\b(find|look up|get)\b.*\b(customer|patient|client|me)\b",
    ],
    "service_lookup": [
        r"\b(what|which|list|show|do you have|services?)\b.*\b(service|treatment|procedure|offering)\b",
        r"\b(how much|price|cost|fee)\b.*\b(for|of)\b",
        r"\b(what|which)\b.*\b(do you offer|do you have|services)\b",
    ],
    "business_info": [
        r"\b(where|location|address|directions?)\b",
        r"\b(hours?|open|close|timing|when.*open)\b",
        r"\b(phone|contact|email|reach)\b",
        r"\b(parking|park|accessibility)\b",
    ],
    "faq": [
        r"\b(policy|policies|rule|rules|cancellation policy)\b",
        r"\b(insurance|payment|billing|cost)\b",
        r"\b(what|how|why|when|where|who|can|do|does|is|are)\b.*\?",
    ],
    "human_handoff": [
        r"\b(human|person|someone|real|agent|representative|staff|manager|supervisor)\b",
        r"\b(speak|talk|chat)\b.*\b(to|with)\b.*\b(human|person|someone|agent|representative)\b",
        r"\b(i want|i need)\b.*\b(human|person|someone|help)\b",
    ],
    "emergency": [
        r"\b(emergency|urgent|critical|severe|chest pain|heart attack|stroke|bleeding|unconscious)\b",
        r"\b(911|ambulance|er|emergency room)\b",
        r"\b(can'?t breathe|choking|overdose|suicide)\b",
    ],
    "general_conversation": [
        r"\b(hi|hello|hey|good morning|good afternoon|good evening)\b",
        r"\b(thanks|thank you|ok|okay|sure|yes|no|maybe)\b",
    ],
}

ENTITY_PATTERNS = {
    "date": r"\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|next week|next monday|next tuesday|next wednesday|next thursday|next friday)\b",
    "time": r"\b(morning|afternoon|evening|noon|midnight|\d{1,2}(:\d{2})?\s*(am|pm)?)\b",
    "staff_name": r"\b(dr\.?\s+\w+|doctor\s+\w+|sarah|ahmed|michael|jennifer|david|lisa|james|maria)\b",
    "service_name": r"\b(cleaning|checkup|filling|root canal|implant|haircut|hair color|facial|bridal|massage|consultation|table|room)\b",
    "phone": r"\b(\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b",
    "email": r"\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b",
    "party_size": r"\b(\d+|one|two|three|four|five|six|seven|eight)\b.*\b(people|person|guests?|pax)\b",
}


class RuleBasedIntentClassifier:
    def classify(self, message: str) -> ClassificationResult:
        message_lower = message.lower().strip()
        best_intent = "unknown"
        best_confidence = 0.0

        for intent, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    confidence = 0.7 + (0.1 if len(pattern) > 20 else 0)
                    if confidence > best_confidence:
                        best_confidence = min(confidence, 0.95)
                        best_intent = intent
                    break

        entities = self._extract_entities(message_lower)

        if best_intent == "unknown" and not entities:
            best_intent = "general_conversation"
            best_confidence = 0.5

        return ClassificationResult(
            intent=best_intent,
            confidence=best_confidence,
            entities=entities,
        )

    def _extract_entities(self, message: str) -> dict[str, Any]:
        entities: dict[str, Any] = {}
        for entity_type, pattern in ENTITY_PATTERNS.items():
            matches = re.findall(pattern, message, re.IGNORECASE)
            if matches:
                if isinstance(matches[0], tuple):
                    entities[entity_type] = matches[0][0]
                else:
                    entities[entity_type] = matches[0]
        return entities
