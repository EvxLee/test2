# Atlas Backend

## Getting Started

### Prerequisites

- Docker and Docker Compose

### Setup Instructions

1. **Copy environment file and populate it with your own values**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add the required values.

2. **Start the application**

   ```bash
   docker compose up --build
   ```

   This will start both the PostgreSQL database and the backend API.
   The API will be available at http://localhost:8081

3. **Stop the application**

   ```bash
   docker compose down
   ```

### Alternative: Local Development Setup

If you want to run the backend locally (outside Docker) for development:

1. **Start only the PostgreSQL database**

   ```bash
   docker compose up postgres
   ```

2. **Create and activate Python virtual environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r product/requirements.pip.txt
   ```

4. **Run the backend locally**

   ```bash
   python product/api/app.py
   ```

   The API will be available at http://localhost:8080
