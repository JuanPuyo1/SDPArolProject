# Frontend — Arol Customer Platform SPA

A modern, responsive React Single Page Application (SPA) built for the **Arol SpA Customer Platform**.

It provides packaging machinery operators and maintenance engineers with interactive machine data inspection, digital manual viewing, and a real-time streaming AI chatbot interface powered by Server-Sent Events (SSE).

---

## 🛠 Technology Stack

- **Framework**: [React 19](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/)
- **Build Tool / Dev Server**: [Vite 8](https://vitejs.dev/) with React plugin & Fast Refresh
- **Routing**: [React Router](https://reactrouter.com/)
- **Styling**: Vanilla CSS with curated color schemes and responsive layouts
- **Networking**: Custom SSE streaming client (`fetchEventSource` pattern) & Session-authenticated REST calls

---

## 📁 Directory Layout

```tree
frontend/
├── components/                 # Page components & navigation UI
│   ├── WelcomePage.tsx         # Welcome page & feature overview
│   ├── LoginPage.tsx           # Customer authentication form
│   ├── MachinePage.tsx         # Machine technical specifications & main units
│   ├── ManualPage.tsx          # Digital manual viewer (PDF integration)
│   ├── ChatbotPage.tsx         # Streaming AI chat assistant interface
│   ├── ProfilePage.tsx         # User profile & account details
│   └── NavBar.tsx              # Top navigation bar
├── src/
│   ├── api/
│   │   ├── auth.ts             # Auth REST client (login, logout, session check)
│   │   ├── machines.ts         # Machine REST client (machine metadata & fleet list)
│   │   └── chat.ts             # SSE chat client for POST /api/agents/chat/
│   ├── hooks/
│   │   ├── useAuth.ts          # Authentication state hook
│   │   └── useChat.ts          # Custom hook for parsing and holding chat stream events
│   ├── App.tsx                 # Main Application router
│   ├── main.tsx                # React app entrypoint
│   └── index.css               # Global styles & design system tokens
├── public/                     # Static assets (manual PDFs, logos, icons)
├── vite.config.ts              # Vite configuration & /api proxy to Django (8000)
└── package.json
```

---

## 🚀 Getting Started

### Prerequisites

- **Node.js**: `≥ 22.12` (required by Vite 8)
- **npm** or **yarn**

### Installation

From the `frontend/` directory:

```bash
npm install
```

### Development Server

Start the local development server:

```bash
npm run dev
```

The application will be accessible at `http://localhost:5173`.

Vite is configured with a development proxy (`vite.config.ts`) that automatically forwards all `/api/*` HTTP requests and Server-Sent Event (SSE) connections to the Django backend at `http://127.0.0.1:8000`.

---

## 🔑 Authentication & API Scoping

- **Session Authentication**: The SPA relies on Django session cookies (`credentials: 'include'`).
- **Tenant Protection**: `customer_id` is managed entirely server-side from `request.user.username`. The client sends `machine_serial` in requests to scope chat and machine operations.
- **CSRF Token Handling**: All `POST` requests include the `X-CSRFToken` header extracted from Django's CSRF cookie.

---

## 💬 Real-Time Streaming Chat (`useChat`)

The AI Chatbot uses Server-Sent Events (SSE) to deliver real-time feedback:

1. **Step Events (`step`)**: Displays agent reasoning and execution progress (e.g. "Searching manual...", "Loading machine context...").
2. **Tool Events (`tool`)**: Exposes MCP tool invocation results for debugging or UI tool activity indicators.
3. **Token Events (`token`)**: Incremental assistant answer tokens rendered immediately as they stream.
4. **Done Events (`done`)**: Marks completion of the chat turn.

---

## 📜 Available Scripts

- `npm run dev` — Starts Vite dev server on port 5173 with HMR
- `npm run build` — Compiles TypeScript and creates production bundle in `dist/`
- `npm run preview` — Locally previews the built production bundle
- `npm run lint` — Runs ESLint across TypeScript and React code
