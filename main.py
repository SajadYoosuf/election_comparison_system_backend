# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
from routers import dashboard, candidates, constituencies, parties, demographics, compare

app = FastAPI(title="Kerala Election Comparison System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(dashboard.router)
app.include_router(candidates.router)
app.include_router(constituencies.router)
app.include_router(parties.router)
app.include_router(demographics.router)
app.include_router(compare.router)

@app.get("/")
def read_root():
    return {"message": "Kerala Election API is running", "version": "2.0.0"}
