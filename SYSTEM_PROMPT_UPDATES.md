# System Prompt Update Summary

## Date
July 27, 2026

## Overview
The production AI System Prompt for the LinkedIn Post Agent has been enhanced with four critical operational constraints while preserving all core architecture, JSON output structure, and LangGraph workflow.

---

## CHANGES INTEGRATED

### 1. ✅ NEW SECTION: Publishing Cadence & Topic Variety
**Location:** New section after "Role & Identity" (lines 16–28)

**Content Added:**
- Automated 3x/week publishing schedule (Monday, Wednesday, Friday)
- Mandatory intra-week topic diversity requirement
- Cross-week rotation enforcement via historical database queries
- Enforcement mechanism: Must consult post history before topic selection

**Impact:** Agent now enforces distinct domain coverage within each week and maintains continuous rotation.

---

### 2. ✅ NEW SUBSECTION: Domain Scope & Whitelist (STRICT)
**Location:** Added to BEHAVIORAL GUARDRAILS section (lines 105–130)

**14 Approved Domains:**
1. Generative AI
2. DevOps
3. Cloud
4. MLOps
5. RAG (Retrieval-Augmented Generation)
6. Embeddings
7. Chunking
8. Vector Databases
9. AI / Cloud Architecture
10. Cost Optimization
11. Performance Optimization
12. Microservices
13. Software Engineering Best Practices
14. AI Application Development

**Hard Guardrail Examples (REJECTED):**
- Generic motivational posts
- Unrelated career advice or soft skills
- HR, recruitment, or workplace culture topics
- Personal development or lifestyle content
- News commentary or politics

**Validation:** Topic must map to at least one approved domain at selection time.

**Impact:** Agent cannot generate out-of-scope content; all topics are restricted to technical engineering domains.

---

### 3. ✅ NEW SUBSECTION: Practical Engineering Focus (Mandatory)
**Location:** Added to BEHAVIORAL GUARDRAILS section (lines 132–148)

**Required Content Types:**
- Architecture Patterns (service boundaries, caching, event-driven, saga patterns)
- Cost-Saving Techniques (resource consolidation, spot instances, optimization)
- Performance Tuning (query optimization, indexing, connection pooling)
- Scaling Strategies (horizontal/vertical, sharding, load distribution)
- Production Best Practices (error handling, circuit breakers, observability)
- Deployment Tactics (blue-green, canary, rollback, infrastructure-as-code)
- Real-World Lessons (incident postmortems, debugging, observability)

**Forbidden:** Vacuous, theoretical, or motivational claims without concrete implementation details.

**Audience:** Senior engineers, tech leads, CTOs, architects (assume deep technical knowledge).

**Impact:** Every post emphasizes actionable, production-grade engineering content tied to real systems.

---

### 4. ✅ NEW SUBSECTION: Historical Awareness & Anti-Repetition
**Location:** Added to TOOL & WORKFLOW EXECUTION section (lines 172–184)

**Pre-Selection Process:**
1. Query post history database for:
   - All posts published in current calendar week
   - Posts from past 4 weeks (cross-week context)
   - Topics and domain angles covered

2. Uniqueness Validation:
   - Topic NOT already covered this week
   - Topic/angle NOT a conceptual duplicate of recent posts
   - Distinctly different in BOTH topic area AND angle

3. Rejection & Regeneration:
   - If candidate topic is repetitive, REJECT it
   - Regenerate from approved domain whitelist
   - Continue until genuinely unique topic found
   - Log all rejections for audit

**Impact:** Agent maintains historical awareness and prevents topic/concept repetition within weekly and cross-week cycles.

---

## UPDATED SECTIONS

### Topic Selection Node (Enhanced)
**Lines 187–195**

Updated description now includes:
- Historical database queries
- Domain whitelist consultation
- Intra-week uniqueness enforcement
- Topic/angle deduplication logic
- Output: finalized topic + research context + domain classification + uniqueness validation status

### Output Schema (Extended)
**Lines 209–231**

New JSON fields:
- `domain` — Classification into one of 14 approved domains
- `domain_validated` — Boolean flag for domain whitelist check
- `uniqueness_validated` — Boolean flag for historical uniqueness check
- `practical_focus_confirmed` — Boolean flag for practical engineering focus
- `validation_status` — Enhanced enum (added FAIL_DOMAIN, FAIL_UNIQUENESS, FAIL_PRACTICAL_FOCUS)
- `published_at` — ISO 8601 timestamp (optional)
- `status` — Enhanced enum (added REJECTED for out-of-scope content)

### Validation Rules (Enhanced)
**Lines 268–299**

Three NEW HARD GATES (must pass before publication):
1. Domain Whitelist Compliance
2. Historical Uniqueness
3. Practical Engineering Focus

Existing soft constraints remain (Length, Format, Character Safety, Whitespace, Thought Compliance).

### Success Criteria (Expanded)
**Lines 348–363**

10-point quality rubric now includes:
- Domain Whitelist Compliance (#2)
- Intra-Week Uniqueness (#3)
- Historical Non-Repetition (#4)
- Practical Engineering Focus (#5)

**Rejection Triggers:** Criteria #2–5 are hard gates; #1, #6–10 warrant revision, not rejection.

---

## CORE ARCHITECTURE PRESERVED

✅ **Unchanged Elements:**
- Role & Identity (Expert LinkedIn Branding Strategist)
- 5-Phase Cognitive Pipeline (Input Analysis → Insight Derivation → Drafting → Validation → Image Thought)
- Minimalist post format (Hook → Checklist → Evolution → Mini-headers → Question → Hashtags)
- Formatting rules (150–230 words, 800–1,200 characters, no forbidden characters)
- LangGraph node workflow
- Human-in-the-loop review nodes
- Database checkpoints & state management
- Output JSON structure (backward compatible)

---

## DEPLOYMENT CHECKLIST

- [x] Update `.prompts/SYSTEM_PROMPT.md` in repository
- [ ] Update database schema to store domain, uniqueness_validated, practical_focus_confirmed fields
- [ ] Implement historical uniqueness check in Topic Selection Node
- [ ] Add domain whitelist validation in Validation Node
- [ ] Create database query function for post history retrieval (current week + past 4 weeks)
- [ ] Add audit logging for topic rejections
- [ ] Update LangGraph edge logic to reject non-compliant topics (return to Topic Selection with rejection reason)
- [ ] Test with 3 sample posts across different weeks to verify intra-week diversity
- [ ] Test domain whitelist enforcement (reject out-of-scope topics)
- [ ] Test historical uniqueness (verify no duplicate topics generated)

---

## TESTING RECOMMENDATIONS

**Scenario 1: Intra-Week Diversity**
- Generate 3 posts on Mon/Wed/Fri
- Verify each post covers a different approved domain
- Example: Monday (DevOps), Wednesday (RAG), Friday (Cloud)

**Scenario 2: Domain Whitelist Rejection**
- Attempt to generate post on "Career Development Tips" (out of scope)
- Verify agent REJECTS with domain validation error
- Verify agent auto-regenerates within approved domains

**Scenario 3: Historical Uniqueness**
- Generate post about "Vector Database Selection" on Monday
- Attempt to generate similar post on Wednesday
- Verify agent REJECTS due to historical duplicate and selects different domain

**Scenario 4: Practical Focus Enforcement**
- Attempt to generate motivational post ("You got this, engineers!")
- Verify agent REJECTS for lack of practical engineering content
- Verify agent regenerates with actionable architectural insights

---

## BACKWARD COMPATIBILITY

- Existing system prompt sections remain unchanged
- JSON output schema is backward compatible (new fields are optional or additive)
- Existing validation rules (length, format, character safety) are preserved
- LangGraph workflow architecture remains intact
- Human-in-the-loop review nodes unchanged

---

## Questions or Issues?

Refer to the updated SYSTEM_PROMPT.md file for detailed operational rules and integration guidance.

---

**Generated:** 2026-07-27  
**Agent:** Claude Code (System Prompt Architect)  
**Status:** Ready for deployment
