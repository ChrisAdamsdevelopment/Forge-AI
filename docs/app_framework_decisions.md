# App Framework Decisions

## Backend

Use FastAPI for the first real backend.

Reasons:

- async-friendly
- clean WebSocket support
- automatic OpenAPI docs
- strong Pydantic validation
- simple local deployment
- good fit for Python AI libraries

## Desktop

Use Electron + React + TypeScript for the desktop control plane.

Reasons:

- cross-platform
- can manage local processes
- can run system tray
- can open local files
- can display terminal output
- large ecosystem

## Web

Use Next.js only when the web dashboard becomes necessary.

The MVP does not need a separate Next.js app. The first MVP can serve a static React UI from FastAPI or use the Electron renderer.

## Mobile

Use React Native + Expo for the companion app.

Mobile should not run models. It should:

- send quick prompts
- trigger modules
- approve risky tool actions
- monitor long-running jobs
- receive status updates

## Storage

Use SQLite for sessions, settings, runs, and module registry.

Use LanceDB or Qdrant for vector search.

Use the normal filesystem for outputs, adapters, logs, and module packages.

## Why not start with a full monorepo app?

The practical first build should be smaller:

1. backend prototype
2. local chat
3. RAG
4. MCP filesystem
5. module runner
6. desktop wrapper

Avoid building desktop, web, and mobile at the same time.
