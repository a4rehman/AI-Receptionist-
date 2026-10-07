# Healthcare Safety Documentation

## Scope

For healthcare tenants (hospital, medical clinic, dental, dermatology, physiotherapy, med spa):

## Allowed Actions
- Schedule appointments
- Cancel appointments
- Reschedule appointments
- Provide clinic information
- Provide doctor information
- Provide appointment details
- Provide administrative information
- Escalate to human

## Prohibited Actions
- Diagnose conditions
- Prescribe medication
- Interpret medical tests
- Replace a doctor
- Make medical decisions

## Emergency Detection

Keywords that trigger immediate escalation:
- "chest pain"
- "heart attack"
- "stroke"
- "severe bleeding"
- "can't breathe"
- "choking"
- "overdose"
- "suicide"
- "unconscious"
- "emergency"
- "911"

## Emergency Response

1. Detect emergency keywords in user message
2. Set `emergency_detected = True` in agent state
3. Provide configured emergency instructions
4. Create human handoff with URGENT priority
5. Do NOT attempt diagnosis or medical advice

## Configuration

Each healthcare tenant configures:
- Emergency instructions message
- Emergency contact numbers
- Escalation policy
