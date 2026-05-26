# AIuthor — Memory Schemas

This document contains the concrete JSON schemas and example records for each of the five memory structures managed by the AIuthor Memory Keeper.

---

## 1. Fact Registry Schema

### Schema
```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "claim": { "type": "string", "description": "The verified statement of fact." },
      "source_chapter": { "type": "integer", "description": "The chapter number where the fact was introduced." },
      "verified": { "type": "boolean", "description": "Flag showing whether the fact was cross-checked." },
      "citation": { "type": "string", "description": "The source file or article the fact was grounded in." }
    },
    "required": ["claim", "source_chapter", "verified"]
  }
}
```

### Example Record
```json
{
  "claim": "An emergency fund should ideally cover 3 to 6 months of essential living expenses.",
  "source_chapter": 1,
  "verified": true,
  "citation": "budgeting_and_saving.md"
}
```

---

## 2. Concept Bible Schema

### Schema
```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "name": { "type": "string", "description": "Name of the character, concept, or term." },
      "type": { "type": "string", "enum": ["character", "concept", "term", "organization"] },
      "description": { "type": "string", "description": "Detailed description and characteristics." },
      "first_introduced_chapter": { "type": "integer" },
      "details": { "type": "object", "description": "Key metadata attributes." }
    },
    "required": ["name", "type", "description", "first_introduced_chapter"]
  }
}
```

### Example Record (Fiction / Test Case B)
```json
{
  "name": "Leo",
  "type": "character",
  "description": "A retired, weather-beaten explorer with a dry sense of humor and a deep knowledge of ancient maps.",
  "first_introduced_chapter": 1,
  "details": {
    "age": 68,
    "eyes": "blue",
    "quirk": "Always carries a silver flask and wears an old canvas hat."
  }
}
```

---

## 3. Callback Index Schema

### Schema
```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "content": { "type": "string", "description": "The specific detail or event to callback." },
      "source_chapter": { "type": "integer", "description": "Chapter number where the event happened." },
      "target_chapter": { "type": "integer", "description": "The future chapter number intended for callback (0 if any)." },
      "callback_trigger": { "type": "string", "description": "The keyword or topic that should trigger referencing this detail." },
      "applied": { "type": "boolean" }
    },
    "required": ["content", "source_chapter", "callback_trigger", "applied"]
  }
}
```

### Example Record
```json
{
  "content": "Leo gave Maya his old brass pocket compass in Chapter 1, noting it has been in the family for three generations.",
  "source_chapter": 1,
  "target_chapter": 3,
  "callback_trigger": "Maya gets lost or needs direction",
  "applied": false
}
```

---

## 4. Tonality Fingerprint Schema

### Schema
```json
{
  "type": "array",
  "items": {
    "type": "string",
    "description": "A specific stylistic rule or vocabulary constraint."
  }
}
```

### Example Record
```json
[
  "Use second-person ('you') to speak directly to the reader's financial struggles.",
  "Never use the term 'delve into' or 'in today's fast-paced world'.",
  "Keep sentence lengths varied, alternating punchy statements with descriptive ones.",
  "Inject maritime and navigational metaphors when describing financial journeys."
]
```

---

## 5. Decision Log Schema

### Schema
```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "decision": { "type": "string", "description": "Creative or structural decision made." },
      "context": { "type": "string", "description": "Why the decision was necessary." },
      "rationale": { "type": "string", "description": "The engineering or creative reasoning." },
      "agent": { "type": "string", "description": "The agent that made the decision." },
      "chapter_number": { "type": "integer" },
      "timestamp": { "type": "string" }
    },
    "required": ["decision", "context", "rationale", "agent", "chapter_number"]
  }
}
```

### Example Record
```json
{
  "decision": "Introduced the 50/30/20 budgeting rule as the core framework for Chapter 2.",
  "context": "The outline requested practical budgeting methods for young professionals.",
  "rationale": "The 50/30/20 rule is mathematically straightforward and highly compatible with a conversational, accessible tonality.",
  "agent": "Writer",
  "chapter_number": 2,
  "timestamp": "2026-05-25T21:50:00Z"
}
```
