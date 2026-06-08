import json

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.config.settings import get_settings
from app.core.logging import get_request_id
from app.core.errors import RateLimitError
from app.graph.response_mapper import to_debug_response, to_public_response
from app.graph.workflow import WORKFLOW_STORE, RoadmapWorkflow
from app.schemas.request import RoadmapRequest
from app.schemas.response import DebugWorkflowResponse, ErrorResponse, MetricsResponse, RoadmapResponse

router = APIRouter(prefix="/api/v1/roadmaps", tags=["roadmaps"])


def build_workflow() -> RoadmapWorkflow:
    return RoadmapWorkflow()


@router.post("", response_model=RoadmapResponse)
async def generate_roadmap(
    request: RoadmapRequest,
    x_correlation_id: str | None = Header(default=None),
) -> RoadmapResponse:
    workflow = build_workflow()
    return await workflow.run(request, request_id=x_correlation_id or get_request_id())


compat_router = APIRouter(tags=["compatibility"])


@compat_router.post("/generate-roadmap", response_model=RoadmapResponse)
async def generate_roadmap_compat(
    request: RoadmapRequest,
    x_correlation_id: str | None = Header(default=None),
) -> RoadmapResponse:
    workflow = build_workflow()
    return await workflow.run(request, request_id=x_correlation_id or get_request_id())


@router.post("/stream")
async def stream_roadmap(
    request: RoadmapRequest,
    x_correlation_id: str | None = Header(default=None),
) -> StreamingResponse:
    workflow = build_workflow()

    async def events():
        try:
            async for event in workflow.stream(request, request_id=x_correlation_id or get_request_id()):
                yield json.dumps(event, default=str) + "\n"
        except RateLimitError as e:
            yield json.dumps({"status": "error", "error_code": "RATE_LIMIT_EXCEEDED", "message": e.message}) + "\n"
        except Exception as e:
            yield json.dumps({"status": "error", "error_code": e.__class__.__name__, "message": str(e)}) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson")


@router.get("/metrics", response_model=MetricsResponse)
async def metrics() -> MetricsResponse:
    settings = get_settings()
    return MetricsResponse(
        status="ok",
        checkpointing="memory",
        external_tools_enabled=settings.enable_external_tools,
        completed_workflows=len(WORKFLOW_STORE),
    )


@router.get("/{workflow_id}", response_model=RoadmapResponse)
async def workflow_status(workflow_id: str) -> RoadmapResponse:
    state = WORKFLOW_STORE.get(workflow_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} was not found")
    return to_public_response(state)


@router.get(
    "/{workflow_id}/debug",
    response_model=DebugWorkflowResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def workflow_debug(workflow_id: str) -> DebugWorkflowResponse:
    settings = get_settings()
    if not settings.debug_mode:
        raise HTTPException(status_code=403, detail="Debug endpoint is disabled")
    state = WORKFLOW_STORE.get(workflow_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} was not found")
    return to_debug_response(state)
