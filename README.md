# 🗳️ Kerala Election Comparison - Backend API

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![SQLModel](https://img.shields.io/badge/SQLModel-512BD4?style=for-the-badge&logo=python)](https://sqlmodel.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)

The analytical engine behind the Kerala Election Comparison System. This high-performance FastAPI backend manages historical data from 1957 to 2026, providing deep insights into alliance shifts, candidate careers, and demographic trends.

---

## 🚀 Key Features

*   **Analytical Engine:** Complex SQL aggregations for historical comparisons (Year-over-Year, Constituency-over-Constituency).
*   **Performance Monitoring:** Every high-computation endpoint returns a `computation_time_ms` metric for real-time performance auditing.
*   **Alliance Intelligence:** Custom logic to map evolving political alliances (LDF, UDF, NDA) across 7 decades.
*   **Data Integrity:** Multi-layered verification for vote counts, electorate growth, and candidate deduplication.
*   **Deduplication Algorithm:** Intelligent name normalization to track candidate careers across different spelling variations in historical records.

## 🛠️ Tech Stack

*   **Framework:** FastAPI (Python 3.14+)
*   **ORM:** SQLModel (SQLAlchemy 2.0 based)
*   **Database:** PostgreSQL (Supabase)
*   **Authentication:** OIDC Support
*   **Deployment:** Render

## 📡 Core Endpoints

| Category | Endpoint | Description |
| :--- | :--- | :--- |
| **Dashboard** | `/api/v1/dashboard/overview` | Global stats and record counts |
| **Comparison** | `/api/v1/compare/years` | Deep analysis between two election cycles |
| **Candidates** | `/api/v1/candidates/{name}/timeline` | Full career history of any candidate |
| **Demographics** | `/api/v1/demographics/gender-stats` | Historical gender distribution metrics |

## 🏗️ Getting Started

### 1. Prerequisites
*   Python 3.14+
*   PostgreSQL Database URL

### 2. Installation
```bash
# Navigate to directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Setup
Configure your environment variables in a `.env` file (not included in version control).

### 4. Running the API
```bash
fastapi dev main.py
```
The API will be available at `http://localhost:8000`. Documentation at `/docs`.

---

## 🔒 Security & Performance
*   **CORS:** Configured for strict production domain verification.
*   **Concurrency:** Async execution paths for database operations.
*   **Versioning:** API routes are versioned under `/api/v1`.

Developed with ❤️ for the Kerala Polls Archive.
