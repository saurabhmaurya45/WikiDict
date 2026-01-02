"""
Health Controller - Health check endpoints
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="", tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Liveness probe - checks if the application is running.

    Use for Kubernetes livenessProbe.
    If this fails, Kubernetes will restart the container.

    Returns:
        HealthResponse: Service health status
    """
    return HealthResponse(
        status="healthy",
        service="sm-wikidict",
        version="1.0.0"
    )


@router.get("/ready", response_model=HealthResponse)
async def readiness_check():
    """
    Readiness probe - checks if the application is ready to serve traffic.

    Use for Kubernetes readinessProbe.
    If this fails, Kubernetes will stop sending traffic to this pod.

    Add dependency checks here (database, cache, external services).

    Returns:
        HealthResponse: Service readiness status
    """
    # TODO: Add actual dependency checks here
    # Example:
    # - Check database connection
    # - Check Redis connection
    # - Check external API availability

    return HealthResponse(
        status="ready",
        service="sm-wikidict",
        version="1.0.0"
    )


@router.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to SM-WikiDict API"}
