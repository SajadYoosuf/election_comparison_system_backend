# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
from routers import dashboard, candidates, constituencies, parties, demographics, compare

app = FastAPI(title="Kerala Election Comparison System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://keralaelectioncomparison.vercel.app",
        "https://election-comparison-frontend.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import time
# pyrefly: ignore [missing-import]
from fastapi import Request

@app.middleware("http")
async def add_process_time_log(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    print(f"DEBUG: {request.method} {request.url.path} | Completed in {process_time:.4f}s")
    return response


app.include_router(dashboard.router)
app.include_router(candidates.router)
app.include_router(constituencies.router)
app.include_router(parties.router)
app.include_router(demographics.router)
app.include_router(compare.router)

@app.get("/")
def read_root():
    return {"message": "Kerala Election API is running", "version": "2.0.0"}
