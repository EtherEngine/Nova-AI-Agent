# Nova AI Agent

Eine AI-Agent-Plattform auf Basis der **OpenAI Responses API**
mit Tool Calling, Streaming, Chat-Historie, Retrieval-Augmented
Generation (RAG), JWT-Authentifizierung und einer React-Oberfläche.

Der Agent empfängt eine Nachricht, entscheidet selbst über den Einsatz von
Tools, validiert deren Argumente mit Pydantic, führt sie aus und
erzeugt anschließend eine finale Antwort.

## Feature-Status

| Bereich                             | Status     | Kurzbeschreibung                                                                 |
| ----------------------------------- | ---------- | -------------------------------------------------------------------------------- |
| Tool Calling (Responses API)        | ✅         | Strikte Function Tools, max. Tool-Runden, isolierte Requests                     |
| Streaming (SSE)                     | ✅         | Token-/Tool-/Done-Events, Abbruch, streaming-sichere Middleware                  |
| Tool Registry                       | ✅         | Zentrale Registry (Name, Schema, Kategorie, Rechte, Handler), Auto-Registrierung |
| API-Versionierung + Security-Header | ✅         | `/api/v1`, Legacy-Aliase, ASGI-Security-Header                                   |
| PostgreSQL + SQLAlchemy 2 + Alembic | ✅         | Async-Engine, Migrationen; App startet auch ohne DB                              |
| Chat-Historie                       | ✅         | Chats/Messages/ToolCalls, CRUD, Persistenz der Turns                             |
| Authentifizierung (JWT)             | ✅         | Register/Login/Refresh/Me, argon2-Hashing, User-Scoping                          |
| RAG + pgvector + PDF-Upload         | ✅         | Extraktion→Chunking→Embeddings→Suche mit Quellen                                 |

## Architektur

```mermaid
flowchart LR
  subgraph Client
    UI[React / Vite Frontend]
  end

  subgraph API[FastAPI /api/v1]
    MW[CORS + Security-Header]
    CHAT[Chat- & Stream-Endpunkte]
    CHATS[Chat-Historie]
    DOCS[Dokumente / RAG]
    AUTH[Auth]
  end

  subgraph Core
    AG[Agent-Orchestrierung]
    REG[Tool Registry]
    RAGSVC[RAG-Service]
  end

  subgraph Data
    DB[(PostgreSQL + pgvector)]
    FS[(Upload-Verzeichnis)]
  end

  OAI[OpenAI Responses & Embeddings]

  UI -->|HTTP / SSE| MW --> CHAT --> AG
  MW --> CHATS --> DB
  MW --> DOCS --> RAGSVC
  MW --> AUTH --> DB
  AG --> REG
  AG -->|Tokens / Tool Calls| OAI
  RAGSVC --> OAI
  RAGSVC --> DB
  RAGSVC --> FS
  CHAT -->|Persistenz| DB
```

### Sequenz: Streaming-Chat mit Tool-Call

```mermaid
sequenceDiagram
  participant U as Frontend
  participant A as FastAPI (/chat/stream)
  participant G as Agent
  participant O as OpenAI Responses
  participant T as Tool Registry
  participant D as Datenbank

  U->>A: POST /api/v1/chat/stream { message, chat_id? }
  A->>G: stream_agent(message)
  G->>O: responses.create(stream=true, tools)
  O-->>G: output_text.delta …
  G-->>A: TokenEvent(delta)
  A-->>U: SSE event: token
  O-->>G: function_call (z. B. calculate)
  G->>T: execute_tool(name, args) — validiert & lokal
  T-->>G: { ok, data }
  G-->>A: ToolEvent
  A-->>U: SSE event: tool
  G->>O: responses.create(function_call_output)
  O-->>G: finaler Text (delta)
  G-->>A: TokenEvent + DoneEvent
  A->>D: persist_turn (optional, wenn chat_id + DB)
  A-->>U: SSE event: done { answer, tools }
```

### Datenbankschema

```mermaid
erDiagram
  USERS ||--o{ CHATS : besitzt
  USERS ||--o{ DOCUMENTS : besitzt
  CHATS ||--o{ MESSAGES : enthält
  MESSAGES ||--o{ TOOL_CALLS : protokolliert
  DOCUMENTS ||--o{ DOCUMENT_CHUNKS : gesplittet_in

  USERS {
    uuid id PK
    string email
    string hashed_password
    bool is_active
    datetime created_at
  }
  CHATS {
    uuid id PK
    uuid user_id FK
    string title
    bool archived
    datetime created_at
    datetime updated_at
  }
  MESSAGES {
    uuid id PK
    uuid chat_id FK
    string role
    text content
    int sequence
    datetime created_at
  }
  TOOL_CALLS {
    uuid id PK
    uuid message_id FK
    string name
    json arguments
    json result
    datetime created_at
  }
  DOCUMENTS {
    uuid id PK
    uuid user_id FK
    string filename
    string content_type
    int size_bytes
    string storage_path
    datetime created_at
  }
  DOCUMENT_CHUNKS {
    uuid id PK
    uuid document_id FK
    int chunk_index
    text content
    vector embedding
  }
```

## Projektstruktur

```
simple-ai-agent/
├── app/
│   ├── main.py            # FastAPI-App, Lifespan, Router, Security-Header, Streaming
│   ├── config.py          # Settings aus Umgebungsvariablen (Fail-fast)
│   ├── schemas.py         # Pydantic Request/Response-Modelle
│   ├── agent.py           # Responses-API-Orchestrierung (run_agent, stream_agent)
│   ├── tools/             # Tool Registry (registry.py) + Built-ins (builtin.py)
│   ├── db/                # Base, Modelle, RAG-Modelle, async Session, Vektortyp
│   ├── services/          # chats, rag, extraction, chunking, embeddings
│   ├── api/               # Router: chats, documents, deps
│   └── auth/              # JWT, Passwort-Hashing, Dependencies, Router
├── migrations/            # Alembic (env.py, versions/)
├── tests/                 # pytest (async SQLite, gemockte OpenAI)
├── frontend/              # React + TypeScript + Vite + Tailwind
├── alembic.ini
├── Dockerfile
└── pyproject.toml
```

## Voraussetzungen

- Python 3.11+
- Node.js 20+ (für das Frontend)
- Ein OpenAI API-Schlüssel
- Optional: PostgreSQL 16 mit pgvector (für Historie, Auth, RAG)

## Installation (Backend)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1        # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
```

## Lokaler Start

```powershell
uvicorn app.main:app --reload
```

Erreichbar unter `http://127.0.0.1:8000`, interaktive Doku unter `/docs`.


## Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env      # VITE_API_URL -> Backend-URL
npm run dev                      # http://localhost:5173
npm run build                    # Typecheck + Produktions-Build
npm run lint                     # ESLint
```




