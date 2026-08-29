from fastapi import APIRouter, Depends, HTTPException

from app.deps.auth import UserContext
from app.deps.guards import assert_building_access, empty_no_building, require_module_enabled
from app.services.ai_tools import TOOL_REGISTRY, invoke_tool

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/query")
async def assistant_query(
    body: dict,
    user: UserContext = Depends(require_module_enabled("ai-chat-assistant")),
):
    building_id = body.get("building_id", "")
    tool = body.get("tool", "building_live")
    question = body.get("question", "")

    if user.is_live_account and not user.has_buildings:
        raise HTTPException(status_code=404, detail=empty_no_building())
    if building_id:
        assert_building_access(user, building_id)

    if tool not in TOOL_REGISTRY:
        return {
            "answer": "Unknown tool.",
            "evidence": [],
            "confidence": 0,
            "limitations": [f"Tool '{tool}' not registered"],
            "data_sources": [],
        }

    result = await invoke_tool(tool, building_id)
    available = result.get("available", True) if isinstance(result, dict) else bool(result)
    return {
        "answer": "Data retrieved from live building sources." if available else "No live data available for this question.",
        "question": question,
        "tool": tool,
        "evidence": result if isinstance(result, (list, dict)) else [result],
        "confidence": 0.9 if available else 0,
        "limitations": [] if available else ["Required telemetry not available"],
        "data_sources": [tool],
        "recommended_next_action": "Connect BMS and complete point mapping" if not available else None,
    }
