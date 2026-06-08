from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.roadmap import compat_router, router as roadmap_router
from app.config.settings import get_settings
from app.core.logging import configure_logging, set_request_id
from app.graph.response_mapper import to_debug_response, to_public_response
from app.graph.workflow import WORKFLOW_STORE
from app.schemas.response import DebugWorkflowResponse, ErrorResponse, HealthResponse, MetricsResponse, RoadmapResponse

configure_logging()
settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(roadmap_router)
app.include_router(compat_router)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-correlation-id") or f"req_{uuid4().hex}"
    set_request_id(request_id)
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    return HealthResponse(status="ready")


@app.get("/metrics", response_model=MetricsResponse)
async def root_metrics() -> MetricsResponse:
    return MetricsResponse(
        status="ok",
        checkpointing="memory",
        external_tools_enabled=settings.enable_external_tools,
        completed_workflows=len(WORKFLOW_STORE),
    )


@app.get("/workflow/{workflow_id}", response_model=RoadmapResponse)
async def root_workflow(workflow_id: str):
    state = WORKFLOW_STORE.get(workflow_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} was not found")
    return to_public_response(state)


@app.get(
    "/workflow/{workflow_id}/debug",
    response_model=DebugWorkflowResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def root_workflow_debug(workflow_id: str) -> DebugWorkflowResponse:
    if not settings.debug_mode:
        raise HTTPException(status_code=403, detail="Debug endpoint is disabled")
    state = WORKFLOW_STORE.get(workflow_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} was not found")
    return to_debug_response(state)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", request.headers.get("x-correlation-id", "unhandled"))
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
            request_id=request_id,
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", request.headers.get("x-correlation-id", "unhandled"))
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error_code="REQUEST_VALIDATION_ERROR",
            message="Request validation failed",
            request_id=request_id,
        ).model_dump(),
    )


from app.core.errors import RateLimitError

@app.exception_handler(RateLimitError)
async def rate_limit_exception_handler(request: Request, exc: RateLimitError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", request.headers.get("x-correlation-id", "unhandled"))
    return JSONResponse(
        status_code=429,
        content=ErrorResponse(
            error_code="RATE_LIMIT_EXCEEDED",
            message=exc.message,
            request_id=request_id,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", request.headers.get("x-correlation-id", "unhandled"))
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code=exc.__class__.__name__,
            message=str(exc),
            request_id=request_id,
        ).model_dump(),
    )
