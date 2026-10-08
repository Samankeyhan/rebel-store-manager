# Rebel Store Manager

Personal accounting and inventory manager for Rebel Store — tracks products, materials, production batches, orders, and expenses. FastAPI backend (`api/`, over `db/`) and a Next.js frontend (`frontend/`).

## Setup

1. Create a virtual environment:

   ```powershell
   python -m venv .venv
   ```

2. Activate it:

   ```powershell
   .venv\Scripts\activate
   ```

3. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. Run the API against a scratch copy of the database (startup applies migrations, so never point it at `data/shop.db`):

   ```powershell
   $env:REBEL_DB = "<path to a copy of data/shop.db>"
   .venv/Scripts/uvicorn api.main:app --port 8000
   ```

   The frontend lives in `frontend/` (`npm run dev`).
