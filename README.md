# ForgeFlow production dashboard

A small production-planning website based on the assignment brief. It includes:

- SQLite-backed production orders and material inventory
- Add, edit, search, and delete production orders
- Dashboard summary cards for progress, delays, and materials
- Frontend JavaScript is included directly in `index.html`

## Run locally

From this directory, run:

```bash
python3 server.py
```

Open <http://localhost:10000>. The dashboard loads directly without a login page.

Python includes SQLite, so no packages are needed. The `production.db` SQLite file is created automatically on first startup. Render uses the included `render.yaml` and a persistent disk at `/var/data/production.db`.
