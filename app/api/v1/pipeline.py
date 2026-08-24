"""Pipeline API 路由 /api/v1/pipeline/*"""

from fastapi import APIRouter

from app.core.response import ApiResponse
from app.models.pipeline_models import PipelineRunRequest

router = APIRouter(
    prefix="/pipeline",
    tags=["Pipeline"],
)


@router.post("/run", summary="执行 Pipeline", response_model=ApiResponse)
async def run_pipeline(request: PipelineRunRequest):
    """
    根据场景配置执行完整的流水线流程。
    传入 scenario_id 和业务参数，自动完成数据获取、处理、输出。
    """
    from app.core.scenario_loader import load_scenario
    from app.core.pipeline_engine import PipelineEngine

    # 加载场景配置
    scenario = load_scenario(request.scenario_id)

    # 执行 Pipeline
    engine = PipelineEngine()
    step_results, outputs, total_duration = await engine.run(
        scenario=scenario,
        input_params=request.params,
    )

    return ApiResponse.success(data={
        "scenario_id": request.scenario_id,
        "steps": [s.model_dump() for s in step_results],
        "outputs": [o.model_dump() for o in outputs],
        "total_duration_ms": total_duration,
    })


@router.get("/scenarios", summary="列出所有场景", response_model=ApiResponse)
async def list_scenarios():
    """列出所有可用的场景配置"""
    from app.core.scenario_loader import list_scenarios as _list

    scenarios = _list()
    return ApiResponse.success(data=scenarios)
