Family JARVIS — Build Specification

1. Product

Build a family AI chief-of-staff called JARVIS.

JARVIS helps a family coordinate their lives by combining calendars, important dates, family preferences, meals, trips, reminders, and plans into one conversational assistant.

The primary experience should feel like talking to a capable family chief of staff, not using a chatbot or calendar search box.

The system should eventually support:

- Family calendar aggregation
- Conflict detection
- Daily/weekly briefings
- Important-date awareness
- Birthday reminders
- Anniversary reminders
- Trip planning
- Dinner recommendations
- Family food preferences
- Date-night planning
- Family memory
- Proactive recommendations
- Voice interaction
- iPad/mobile PWA
- Desktop web access

⸻

2. Architecture

Use this architecture:

                         FAMILY JARVIS
                              |
                              v
                       MANAGER AGENT
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
          ORGANIZER         CHEF        DATE PLANNER
              |               |               |
              +---------------+---------------+
                              |
                              v
                        FAMILY BRAIN
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
         Calendars         Memory         Preferences
                              |
                              v
                         OPENROUTER

The Manager is the only agent that directly communicates with the family.

Specialist agents should not continuously converse with each other.

The Manager should delegate structured tasks to specialists and combine their results.

⸻

3. AI Provider

Use OpenRouter, not Anthropic directly.

The backend must use:

OPENROUTER_API_KEY

from an environment variable.

Never expose the key to the browser.

Never hardcode the key.

The AI provider must be abstracted behind a small server-side interface so the model can be changed without rewriting the application.

Example:

LLMProvider
├── OpenRouterProvider
└── model configuration

The model should be configurable through an environment variable:

OPENROUTER_MODEL=

Do not hardcode a single model throughout the application.

⸻

4. Hosting Architecture

Design the application to run in the cloud.

Target architecture:

iPad / iPhone / Desktop
|
| HTTPS
v
Python API
|
+-----+------+
| |
v v
OpenRouter ElevenLabs
|
v
Supabase

The application must not require a dedicated Mac, Raspberry Pi, or local server.

Development happens locally.

Production runs in the cloud.

The frontend must work as a responsive web application and PWA.

⸻

5. Recommended Stack

Frontend:

- React + TypeScript OR vanilla JS if keeping the first prototype extremely simple
- Mobile-first
- PWA
- Responsive
- Touch-friendly

Backend:

- Python
- FastAPI is acceptable if the project allows dependencies
- Keep the backend modular
- No AI provider logic in the frontend

Database:

- Supabase/PostgreSQL

AI:

- OpenRouter

Voice:

- ElevenLabs

Hosting:

- Render initially

The architecture should remain portable so it can later move to Cloud Run, Railway, AWS, or another host.

⸻

6. Family Brain

Create a normalized database representing the family.

Minimum entities:

families
family_members
calendars
calendar_events
important_dates
preferences
food_preferences
recipes
pantry_items
trips
relationships
date_history
memories
notifications
agent_tasks

Every family record must belong to a family.

Do not create a global shared memory.

Family data must be isolated by family ID.

⸻

7. Family Members

Each family member should have:

id
family_id
name
relationship
birthday
preferences
active

Do not assume the family structure.

The onboarding flow must ask the user who they are and who belongs to the family.

⸻

8. Onboarding

On first launch, JARVIS should interview the user.

Collect:

About the user

- Name
- Role in the family
- Communication preferences
- Important personal preferences

About the family

- Family members
- Names
- Relationships
- Important dates
- Traditions
- Preferences

Scheduling

- Calendars
- School schedules
- Sports schedules
- Work schedules
- Recurring commitments

Food

- Favorite meals
- Foods people dislike
- Dietary restrictions
- Cooking skill level
- Typical dinner budget
- Typical dinner preparation time

Relationships

- Anniversary
- Date-night preferences
- Favorite activities
- Favorite restaurants
- Typical budget
- Childcare constraints

Trips

- Upcoming trips
- Travel preferences
- Important travel dates

JARVIS should ask questions conversationally instead of presenting a giant form.

⸻

9. Manager Agent

The Manager is the primary reasoning agent.

Responsibilities:

1. Understand the user’s request.
2. Resolve context from conversation history.
3. Determine whether a specialist is needed.
4. Call the appropriate specialist/tool.
5. Combine results.
6. Respond naturally.
7. Never invent information.

Example:

User:

“What’s going on Friday?”

Manager:

Check calendar
→ identify events
→ identify conflicts
→ identify available time
→ return concise summary

User:

“What should we do Friday night?”

Manager:

Check calendar
→ determine family availability
→ ask Date Planner
→ return recommendations

User:

“What’s for dinner?”

Manager:

Check calendar
→ determine available cooking time
→ check food preferences
→ ask Chef
→ return recommendation

⸻

10. Organizer Agent

Responsibilities:

- Aggregate calendars
- Normalize events
- Detect conflicts
- Detect overlapping events
- Detect unusually busy days
- Calculate family availability
- Identify upcoming important dates
- Prepare daily briefings
- Prepare weekly briefings
- Identify preparation requirements

Example:

Conflict:
Saturday 10:00 AM
Person A: Softball
Person B: Appointment
Person C: Work

The Organizer should return structured data.

⸻

11. Chef Agent

Responsibilities:

- Recommend dinners
- Consider family preferences
- Consider available cooking time
- Consider budget
- Consider pantry
- Consider upcoming schedule
- Avoid recently repeated meals
- Explain why a recommendation fits the schedule

Example:

Available cooking time:
35 minutes
People eating:
4
Recommendation:
Chicken tacos
Reason:
Fast, family preference match, fits the available time.

⸻

12. Date Planner Agent

Responsibilities:

- Find available date-night windows
- Consider budget
- Consider preferences
- Consider previous date history
- Recommend activities
- Recommend restaurants
- Consider travel distance
- Consider weather when web research is available
- Remember previously suggested or completed dates

The Date Planner must not book anything.

It only recommends.

⸻

13. Proactive Concierge

Add a lightweight proactive layer.

JARVIS should eventually identify:

- Birthday approaching
- Anniversary approaching
- Trip approaching
- Calendar conflict
- Unusually busy week
- Free evening
- Date-night opportunity
- Dinner planning opportunity
- Important preparation deadline

Examples:

Your anniversary is in 14 days.
Friday the 21st is currently your best open evening.
You have a scheduling conflict Saturday at 10 AM.
Everyone is home tonight at 6:15 PM.
You have approximately 45 minutes for dinner.

⸻

14. Conversation Memory

Maintain recent conversational context.

Minimum:

last 10 turns

The Manager should resolve:

- “Why?”
- “What about the second one?”
- “How much?”
- “What about Saturday?”
- “Change that to Friday.”

Do not force the user to restate context unnecessarily.

⸻

15. Safety

Absolute rules:

Never send

Never send:

- Email
- Text
- Direct message
- Calendar invitation

JARVIS may draft them but must wait for explicit confirmation.

Never purchase

No purchases.

No restaurant reservations.

No tickets.

No paid services.

No financial transactions.

Calendar writes

Initially make calendar access read-only.

Do not create, modify, or delete calendar events until a later version explicitly adds confirmation-based write actions.

Memory

Never silently save memories.

If the user asks JARVIS to remember something:

1. Write the memory.
2. Tell the user exactly what was saved.

Never invent

If information is unavailable:

I don't know yet.

Never fabricate:

- Events
- Dates
- Prices
- People
- Preferences
- Restaurants
- Memories

⸻

16. Calendar Integrations

Start with:

1. Google Calendar

Do not build every calendar provider simultaneously.

Build an abstraction:

CalendarProvider
|
+-- GoogleCalendarProvider
+-- AppleCalendarProvider
+-- OutlookCalendarProvider

The first production integration should be Google Calendar.

Later add Apple/iCloud and Microsoft Outlook.

⸻

17. Voice

Use ElevenLabs.

Speech-to-text:

ElevenLabs Scribe

Text-to-speech:

ElevenLabs TTS

The API key remains server-side.

The browser must never receive the API key.

The browser communicates with:

/api/listen
/api/speak

or equivalent server routes.

⸻

18. PWA

The application must be installable on:

- iPad
- iPhone
- Desktop

The iPad should be treated as a primary client.

The app should support:

- Touch
- Voice
- Keyboard
- Responsive layouts
- Home Screen installation
- Notifications where supported

Do not require the iPad to run the AI locally.

The iPad is a client.

The cloud is the brain.

⸻

19. UI

Before building the interface:

STOP.

Ask me for a screenshot of an interface whose visual language I want.

Do not build the UI until I either:

1. provide a screenshot, or
2. explicitly tell you to use your own judgment.

When I provide a screenshot, analyze:

- Background
- Surfaces
- Accent colors
- Typography
- Border weight
- Radius
- Shadows
- Glow
- Spacing
- Density

Then tell me in ONE sentence what visual language you extracted before writing UI code.

Do not copy the screenshot literally.

⸻

20. Development Phases

Build in this order.

Phase 1 — Foundation

Build:

- Repository
- Backend
- Frontend shell
- Environment configuration
- Supabase connection
- OpenRouter abstraction
- Database schema
- Authentication/family isolation

Do not build the full UI yet.

Test everything.

⸻

Phase 2 — Family Brain

Build:

- Family members
- Important dates
- Preferences
- Memories
- Food preferences
- Trips
- Relationships

Create seed/demo data.

Test database operations.

⸻

Phase 3 — Calendar Intelligence

Build:

- Calendar provider abstraction
- Google Calendar integration
- Event normalization
- Conflict detection
- Availability calculations
- Important-date detection
- Daily briefing data
- Weekly briefing data

Test with fixtures before connecting real family calendars.

⸻

Phase 4 — Manager Agent

Build:

- Conversation API
- Context management
- Tool selection
- Structured agent responses
- OpenRouter integration
- No-invention guardrails

The Manager must be able to answer:

What's happening today?
What's happening Friday?
Do we have a conflict?
When is my anniversary?
What important dates are coming up?

⸻

Phase 5 — Specialist Agents

Build:

1. Organizer
2. Chef
3. Date Planner

The Manager delegates to them.

Do not allow uncontrolled agent-to-agent conversations.

Use structured tool calls.

⸻

Phase 6 — Proactive Intelligence

Add:

- Morning briefing
- Evening briefing
- Upcoming birthday alerts
- Anniversary alerts
- Trip alerts
- Conflict alerts
- Free-evening suggestions
- Dinner suggestions

Use scheduled backend jobs.

⸻

Phase 7 — Voice

Add:

- ElevenLabs Scribe
- ElevenLabs TTS
- Mic controls
- Audio state
- Voice conversation
- Interrupt handling

The system must stop listening while JARVIS speaks.

⸻

Phase 8 — PWA

Add:

- Manifest
- Service worker where appropriate
- Install experience
- iPad layout
- iPhone layout
- Desktop layout
- Push notifications where supported

⸻

Phase 9 — Production

Deploy:

Frontend + API → Render
Database → Supabase
LLM → OpenRouter
Voice → ElevenLabs

Configure:

- HTTPS
- Secrets
- Logging
- Error handling
- Rate limits
- Authentication
- Backups
- Monitoring

⸻

21. Testing

Every phase must have tests before moving to the next.

Prioritize:

- Calendar conflicts
- Date calculations
- Important dates
- Availability
- Agent routing
- Family isolation
- Memory behavior
- Guardrails
- No-send behavior
- No-purchase behavior
- No-invention behavior

Create realistic demo data.

Never test first against real family data.

⸻

22. Demo Mode

Create:

JARVIS_DEMO=true

Demo mode must use fake family information.

It must never accidentally expose real family data.

Production:

JARVIS_DEMO=false

The application must clearly show whether it is running in demo or production mode.

⸻

23. Cost Awareness

The system should minimize unnecessary LLM calls.

Do not call an LLM for:

- Simple calendar filtering
- Date comparisons
- Conflict detection
- Sorting
- Counting
- Availability calculations

Use normal application code for deterministic operations.

Use the LLM for:

- Understanding natural language
- Reasoning
- Recommendations
- Summarization
- Planning
- Conversation

This keeps the application faster and cheaper.

⸻

24. First milestone

Do NOT attempt to build everything at once.

The first working milestone should be:

Family JARVIS
|
v
User asks:
"What's happening Friday?"
|
v
Manager
|
v
Organizer
|
v
Family Calendar
|
v
Answer

Then expand from there.

⸻

25. Important development rule

After completing each phase:

1. Run tests.
2. Verify the implementation.
3. Show what was built.
4. Show what remains.
5. STOP.
6. Wait for approval before starting the next phase.

Do not silently continue through all phases.

Do not install dependencies or services I have not approved.

Do not expose API keys.

Do not connect real family calendars until the demo implementation has been tested.
