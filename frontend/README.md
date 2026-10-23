# StudyVault frontend

The frontend is the React, TypeScript and Tailwind client for StudyVault. Run it from this directory with:

```powershell
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

During local development, Vite proxies `/api` requests to the FastAPI server at `http://127.0.0.1:8000`. See the repository [README](../README.md) for backend setup, environment variables, migrations, the reminder worker and all verification commands.

Quality checks:

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
npm.cmd run test:e2e
```
