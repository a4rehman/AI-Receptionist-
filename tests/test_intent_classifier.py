from receptionist.llm.classifier import RuleBasedIntentClassifier


class TestIntentClassifier:
    def setup_method(self):
        self.classifier = RuleBasedIntentClassifier()

    def test_booking_intent(self):
        result = self.classifier.classify("I want to book an appointment")
        assert result.intent == "booking"
        assert result.confidence > 0.5

    def test_cancel_intent(self):
        result = self.classifier.classify("Cancel my appointment")
        assert result.intent == "cancel"

    def test_reschedule_intent(self):
        result = self.classifier.classify("Move my appointment to Friday")
        assert result.intent == "reschedule"

    def test_emergency_intent(self):
        result = self.classifier.classify("I am having severe chest pain")
        assert result.intent == "emergency"

    def test_human_handoff_intent(self):
        result = self.classifier.classify("I want to speak to a human")
        assert result.intent == "human_handoff"

    def test_availability_intent(self):
        result = self.classifier.classify("What times are available tomorrow?")
        assert result.intent == "availability"

    def test_appointment_lookup_intent(self):
        result = self.classifier.classify("What appointments do I have?")
        assert result.intent == "appointment_lookup"

    def test_service_lookup_intent(self):
        result = self.classifier.classify("What services do you offer?")
        assert result.intent == "service_lookup"

    def test_business_info_intent(self):
        result = self.classifier.classify("What are your hours?")
        assert result.intent == "business_info"

    def test_faq_intent(self):
        result = self.classifier.classify("Do you accept insurance?")
        assert result.intent == "faq"

    def test_general_conversation(self):
        result = self.classifier.classify("Hello")
        assert result.intent == "general_conversation"

    def test_entity_extraction_date(self):
        result = self.classifier.classify("I want to book tomorrow")
        assert "date" in result.entities

    def test_entity_extraction_time(self):
        result = self.classifier.classify("I want to book at 3pm")
        assert "time" in result.entities
