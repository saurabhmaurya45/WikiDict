"""
SM-WikiDict FastAPI Server
"""

from fastapi import FastAPI
from src.controller import health_router

app = FastAPI(
    title="SM-WikiDict",
    description="Word Dictionary API",
    version="1.0.0"
)

# Register routers
app.include_router(health_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
