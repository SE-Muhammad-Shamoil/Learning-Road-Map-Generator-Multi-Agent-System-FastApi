from langchain_core.tools import BaseTool

from app.core.observability import Timer, ToolTrace, log_line


class ToolExecutionResult(dict):
    pass


class ToolExecutor:
    def __init__(self, tools: list[BaseTool]) -> None:
        self.tools = {tool.name: tool for tool in tools}

    async def run(self, tool_name: str, arguments: dict) -> tuple[list[dict], ToolTrace]:
        tool = self.tools[tool_name]
        with Timer() as timer:
            try:
                result = await tool.ainvoke(arguments)
                summary = f"{len(result) if isinstance(result, list) else 1} result(s)"
                log_line(
                    "TOOL OK   ",
                    tool=tool_name,
                    query=arguments.get("query"),
                    results=len(result) if isinstance(result, list) else 1,
                    ms=f"{timer.elapsed_ms:.1f}",
                )
                return result, ToolTrace(
                    tool_name=tool_name,
                    arguments=arguments,
                    result_summary=summary,
                    execution_time_ms=timer.elapsed_ms,
                    success=True,
                )
            except Exception as error:
                log_line(
                    "TOOL FAIL ",
                    tool=tool_name,
                    query=arguments.get("query"),
                    ms=f"{timer.elapsed_ms:.1f}",
                    error=error,
                )
                return [], ToolTrace(
                    tool_name=tool_name,
                    arguments=arguments,
                    result_summary="tool execution failed",
                    execution_time_ms=timer.elapsed_ms,
                    success=False,
                    error=str(error),
                )
