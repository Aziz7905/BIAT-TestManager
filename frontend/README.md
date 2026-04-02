# BIAT Test Manager Frontend

This frontend is the React application for BIAT Test Manager. It provides the authenticated workspace for project navigation, specifications, test design, and the first Layer 5 automation controls.

## Stack

- Vite
- React
- TypeScript
- Tailwind CSS
- React Router
- Zustand
- Axios

## Current Frontend Scope

Implemented areas include:

- authentication flow
- protected app shell
- project listing and project workspace
- specifications views
- manual test design views
- requirement traceability views
- minimal automation controls inside test-case detail

Layer 5 frontend is intentionally small right now. It supports:

- listing automation scripts for a selected test case
- creating and editing scripts
- validating scripts
- activating and deactivating scripts
- queueing a test execution
- viewing execution history
- pause, resume, and stop actions

## Important Product Notes

- The current workspace is functional but still needs structural UX refinement
- The UI should keep BA source artifacts, normalized requirements, test design, and execution concerns conceptually separate
- Automation currently reflects the backend v1 execution model, which is Python Playwright first

## Project Structure

```text
frontend/
├─ public/
├─ src/
│  ├─ api/
│  ├─ components/
│  ├─ pages/
│  ├─ router/
│  ├─ store/
│  ├─ types/
│  └─ assets/
├─ package.json
├─ vite.config.ts
└─ tsconfig*.json
```

## Environment Variables

Create `frontend/.env` if it does not exist:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

## Install Dependencies

From `frontend`:

```powershell
npm install
```

## Start the Frontend

From `frontend`:

```powershell
npm run dev
```

The Vite app is typically available at `http://127.0.0.1:5173/`.

## Build and Type Check

```powershell
npm run build
```

## Lint

```powershell
npm run lint
```

## Backend Dependency

The frontend expects the Django API to be running locally. In normal development, start:

1. PostgreSQL
2. Redis
3. Django API
4. Celery worker
5. Frontend Vite app

## Routing Notes

The app uses protected routes and a project-first workspace model. The main authenticated user flow centers on:

- login
- projects
- project workspace
- specifications
- team/admin pages depending on role

## Known Limitations

- The current project workspace is still heavier than intended
- Navigation and tree structure need a later UX simplification pass
- Automation is embedded into the existing test-case detail rather than having a fully dedicated execution workspace
