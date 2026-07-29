# Understanding This Codebase

This document is a beginner-friendly guide to the project. It explains what the app does, how the pieces fit together, and what to learn next.

---

## 1. What this project is about

This project is a web application for an industrial machine support assistant.

In simple terms, a user can chat with the system about a machine problem, and the app tries to help by:
- understanding the user message,
- looking up machine information,
- calling tools such as manuals, error codes, telemetry, or ticket creation,
- returning an answer.

This is an example of an agentic AI system because the app uses an "agent" that can decide which actions to take.

---

## 2. High-level architecture

The app is split into three big parts:

1. Frontend
   - The user interface.
   - Built with React + TypeScript + Vite.
   - Lets the user chat with the assistant.

2. Backend
   - The server logic.
   - Built with Django (Python).
   - Handles authentication, API endpoints, and agent orchestration.

3. MCP server / tools
   - A tool layer that gives the agent capabilities.
   - Tools can fetch machine info, search manuals, search error codes, create tickets, etc.

The flow is roughly:

User -> Frontend -> Backend chat endpoint -> Agent/orchestrator -> MCP tools -> Response -> Frontend

---

## 3. Main folders

### Frontend
Location: [frontend](frontend)

This contains the user-facing React app.

Important files:
- [frontend/src/App.tsx](frontend/src/App.tsx) – main app router/component entry
- [frontend/components/ChatbotPage.tsx](frontend/components/ChatbotPage.tsx) – chat UI
- [frontend/src/api/chat.ts](frontend/src/api/chat.ts) – client code that talks to the backend streaming chat endpoint
- [frontend/src/hooks/useChat.ts](frontend/src/hooks/useChat.ts) – React hook that processes streaming chat events

What to understand here:
- The frontend sends a message to the backend.
- It receives a streaming response.
- It displays tokens, tool steps, and the final answer.

### Backend
Location: [Backend](Backend)

This contains the Django server and app logic.

Important folders:
- [Backend/apps/agents](Backend/apps/agents) – agent logic and orchestration
- [Backend/apps/mcp_server](Backend/apps/mcp_server) – tool registry and tool implementations
- [Backend/apps/machines](Backend/apps/machines) – machine data models
- [Backend/config](Backend/config) – Django settings and URLs

### Documentation
Location: [documentation](documentation)

This contains deeper explanations and architecture notes.

Useful starting files:
- [documentation/ARCHITECTURE.md](documentation/ARCHITECTURE.md)
- [documentation/ORCHESTRATOR_GUIDE.md](documentation/ORCHESTRATOR_GUIDE.md)
- [documentation/ORCHESTRATOR_IMPLEMENTATION.md](documentation/ORCHESTRATOR_IMPLEMENTATION.md)

---

## 4. How the app works end-to-end

### Step 1: The user sends a message
The user types something like:
- “Alarm E042 star-wheel jam”
- “Please send a technician”

The frontend sends this message to the backend chat endpoint.

### Step 2: The backend receives the request
The endpoint is implemented in [Backend/apps/agents/views.py](Backend/apps/agents/views.py).

It:
- checks whether the user is authenticated,
- parses the request body,
- resolves the machine serial number,
- calls the agent/orchestrator.

### Step 3: The agent decides what to do
The core agent logic is in [Backend/apps/agents/troubleshooting_service_agent.py](Backend/apps/agents/troubleshooting_service_agent.py).

It does three basic things:
- classify the user intent,
- decide which tools to call,
- generate a response.

For example:
- If the user mentions an alarm/error, it may search error codes and manuals.
- If the user asks for service/help, it may create a ticket.

### Step 4: The agent calls tools
The agent does not directly query the database or search manuals itself. Instead, it uses a tool registry.

That registry is in [Backend/apps/mcp_server/registry.py](Backend/apps/mcp_server/registry.py).

The tools are implemented as functions under [Backend/apps/mcp_server/tools](Backend/apps/mcp_server/tools).

Examples of tools:
- get_machine_info
- search_error_codes
- search_manual
- query_telemetry
- create_ticket

These tools act like the agent’s available skills.

### Step 5: The backend streams the result back
The backend streams events back to the frontend using SSE (Server-Sent Events).

The stream includes events like:
- `step`: a reasoning or planning step
- `tool`: a tool call and its result
- `token`: text generated for the answer
- `done`: the interaction is finished
- `error`: anything failed

This is implemented in [Backend/apps/agents/views.py](Backend/apps/agents/views.py).

### Step 6: The frontend displays the stream
The frontend listens to the stream in [frontend/src/api/chat.ts](frontend/src/api/chat.ts) and updates the UI in [frontend/src/hooks/useChat.ts](frontend/src/hooks/useChat.ts).

So the user sees:
- the agent’s thinking steps,
- which tools were used,
- and the final answer.

---

## 5. Important concepts in this project

### Django
Django is the backend framework.

It handles:
- HTTP routes,
- user authentication,
- database access,
- views and APIs.

### React + TypeScript
React powers the frontend UI.

TypeScript helps make the code clearer and safer.

### Agentic AI
An agent is a component that can:
- reason about a task,
- choose actions,
- call tools,
- produce a response.

### RAG (Retrieval-Augmented Generation)
RAG means the model does not rely only on its own memory. Instead, it retrieves information from a knowledge base or documents first.

In this project, the manual and error-code search tools are part of that idea.

The RAG layer is under [Backend/apps/mcp_server/rag_engine](Backend/apps/mcp_server/rag_engine).

---

## 6. The most important files to understand first

If you are new, start with these in order:

1. [Backend/apps/agents/views.py](Backend/apps/agents/views.py)
   - Shows how chat requests are handled.

2. [Backend/apps/agents/troubleshooting_service_agent.py](Backend/apps/agents/troubleshooting_service_agent.py)
   - Shows the main agent logic and tool calling flow.

3. [Backend/apps/mcp_server/registry.py](Backend/apps/mcp_server/registry.py)
   - Shows how tools are registered and invoked.

4. [frontend/src/api/chat.ts](frontend/src/api/chat.ts)
   - Shows how the frontend reads the streaming SSE response.

5. [frontend/src/hooks/useChat.ts](frontend/src/hooks/useChat.ts)
   - Shows how the UI updates based on each event.

---

## 7. How to run the app locally

### Backend
```bash
cd Backend
python manage.py runserver
```

### Frontend
```bash
cd frontend
npm run dev
```

### Run tests
```bash
cd Backend
python manage.py test apps.agents.tests
```

---

## 8. How to inspect the agent stream

The chat endpoint returns a streaming response. You can inspect it using:

```bash
curl -N -X POST http://127.0.0.1:8000/api/agents/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message":"Alarm E042 star-wheel jam","machine_serial":"A3279"}'
```

You will see events such as:
- `step`
- `tool`
- `token`
- `done`

---

## 9. What the current progress already shows

At this stage, the project already has:
- a working frontend chat UI,
- a Django backend chat endpoint,
- an agent that routes user requests,
- a tool registry for machine-related actions,
- streaming responses for visible reasoning/tool usage,
- basic tests for the agent and chat endpoint.

That means the foundation is in place. The next step is usually to make the system more intelligent and more realistic.

---

## 10. Next steps to follow

### A. Understand the code path first
Follow one request end-to-end:
1. Type a message in the UI.
2. See it reach [Backend/apps/agents/views.py](Backend/apps/agents/views.py).
3. See the agent call tools in [Backend/apps/agents/troubleshooting_service_agent.py](Backend/apps/agents/troubleshooting_service_agent.py).
4. See the frontend render the stream in [frontend/src/api/chat.ts](frontend/src/api/chat.ts).

This is the most important learning exercise.

### B. Learn the tool layer
Open the files in [Backend/apps/mcp_server/tools](Backend/apps/mcp_server/tools) and understand what each tool does.

Focus on:
- how the tool receives parameters,
- what data it returns,
- how the agent uses the tool result.

### C. Learn the RAG part
Look at [Backend/apps/mcp_server/rag_engine](Backend/apps/mcp_server/rag_engine).

This is where manual and error-code search become more advanced and knowledge-based.

### D. Improve the agent logic
You can later improve:
- the intent classification,
- tool selection logic,
- the final answer generation,
- error handling.

### E. Add real data and real tools
The current tools are partly stubbed. A next real-world step is to connect them to:
- actual manuals,
- real telemetry data,
- real ticket systems,
- real embeddings/vector search.

### F. Learn by building one small feature
A good beginner project goal is:
- add one new tool,
- make the agent use it,
- show it in the UI.

That is much better than trying to understand everything at once.

---

## 11. Recommended learning order

If you are a beginner, I recommend this order:

1. Learn how Django views work.
2. Learn how the chat endpoint receives requests.
3. Learn how the agent chooses tools.
4. Learn how the frontend reads SSE streams.
5. Learn how MCP tools are registered and invoked.
6. Learn the RAG layer.

---

## 12. A simple mental model

Think of the app like this:

- The frontend is the face of the assistant.
- The backend is the brain and controller.
- The tools are the hands and senses.
- The RAG layer is the memory.

That is the basic idea behind this project.

---

## 13. Final advice

Do not try to understand every file immediately.

Instead, focus on one request path and follow it from start to finish.

If you do that repeatedly, the architecture will become much clearer.

You are already in a good position because the project has:
- a working UI,
- a working backend API,
- an agent flow,
- tool integration,
- and test coverage.

That means you are not starting from zero.

---

## 14. Suggested next personal goal

Your next goal should be:

“Follow one chat request from the UI to the backend, see which tool the agent calls, and understand the JSON stream that comes back.”

If you can do that, you will already understand the core architecture of this project.
