import json
from copy import deepcopy

from app.agents.resource.prompt import RESOURCE_PROMPT
from app.agents.resource.schema import ResourceOutput
from app.agents.resource.schema import ResourceToolDecision
from app.config.settings import Settings
from app.llm.router import LLMRouter
from app.llm.providers import LLMProvider
from app.schemas.roadmap import LearningResource, Roadmap
from app.tools.executor import ToolExecutor
from app.tools.search_tools import SearchTools


class ResourceAgent:
    name = "ResourceAgent"

    def __init__(self, router: LLMRouter, settings: Settings) -> None:
        self.router = router
        self.settings = settings
        self.tools = SearchTools(settings).build() if settings.enable_external_tools else []
        self.executor = ToolExecutor(self.tools)

    async def run(self, roadmap: Roadmap) -> tuple[ResourceOutput, object, list]:
        import asyncio
        usage = self.router.usage(self.name, LLMProvider.GEMINI, used_live_llm=False)
        revised = deepcopy(roadmap)
        resources: dict[str, list[LearningResource]] = {}
        tool_calls: list[dict] = []
        tool_results: list[dict] = []
        tool_reasoning: list[str] = []
        traces = []

        async def process_node(node):
            node_results: list[LearningResource] = []
            local_tool_calls = []
            local_tool_results = []
            local_tool_reasoning = []
            local_traces = []
            decision, decision_usage = await self._choose_tools(node)
            local_tool_reasoning.append(f"{node['id']}: {decision.thought}")
            selected_tools = [tool for tool in decision.tools if tool in self.executor.tools]
            
            async def run_tool(tool_name):
                return tool_name, await self.executor.run(tool_name, {"query": node['title'], "max_results": 2})

            tool_results_list = await asyncio.gather(*(run_tool(tool_name) for tool_name in selected_tools))

            for tool_name, (result, trace) in tool_results_list:
                local_traces.append(trace)
                call = {
                    "node_id": node['id'],
                    "tool": tool_name,
                    "input": {"query": node['title'], "max_results": 2},
                    "output": result,
                    "reasoning": decision.thought,
                }
                local_tool_calls.append(call)
                local_tool_results.append(call)
                node_results.extend(LearningResource.model_validate(item) for item in result)

            if self._quality(node_results) < decision.quality_threshold:
                retry_tools = [tool for tool in decision.retry_with if tool in self.executor.tools and tool not in selected_tools]
                
                async def run_retry_tool(tool_name):
                    return tool_name, await self.executor.run(tool_name, {"query": f"{node['title']} best learning resources", "max_results": 2})
                
                retry_results_list = await asyncio.gather(*(run_retry_tool(tool_name) for tool_name in retry_tools))

                for tool_name, (result, trace) in retry_results_list:
                    local_traces.append(trace)
                    call = {
                        "node_id": node['id'],
                        "tool": tool_name,
                        "input": {"query": f"{node['title']} best learning resources", "max_results": 2},
                        "output": result,
                        "reasoning": f"Retry because prior result quality was below {decision.quality_threshold}.",
                    }
                    local_tool_calls.append(call)
                    local_tool_results.append(call)
                    local_tool_reasoning.append(f"{node['id']}: retry with {tool_name} after quality check")
                    node_results.extend(LearningResource.model_validate(item) for item in result)

            return node['id'], node_results, decision_usage, local_tool_calls, local_tool_results, local_tool_reasoning, local_traces

        node_processing_results = await asyncio.gather(*(process_node(node.model_dump()) for node in roadmap.nodes))

        for node_id, node_results, decision_usage, local_tool_calls, local_tool_results, local_tool_reasoning, local_traces in node_processing_results:
            resources[node_id] = node_results
            usage.used_live_llm = usage.used_live_llm or decision_usage.used_live_llm
            usage.latency_ms += decision_usage.latency_ms
            tool_calls.extend(local_tool_calls)
            tool_results.extend(local_tool_results)
            tool_reasoning.extend(local_tool_reasoning)
            traces.extend(local_traces)

        # Removed population of node_copy.resources because resources field is removed from RoadmapNode
        # The resources are tracked entirely in the `resources` dictionary.
        return ResourceOutput(
            curriculum=revised,
            resources=resources,
            tool_calls=tool_calls,
            tool_results=tool_results,
            tool_reasoning=tool_reasoning,
        ), usage, traces

    async def _choose_tools(self, node: dict) -> tuple[ResourceToolDecision, object]:
        available = sorted(self.executor.tools)
        try:
            result, usage = await self.router.invoke_structured(
                agent_name=self.name,
                provider=LLMProvider.GEMINI,
                schema=ResourceToolDecision,
                prompt=RESOURCE_PROMPT.format(tools=available, node=json.dumps(node)),
            )
            if result is not None:
                result.tools = [tool for tool in result.tools if tool in available]
                result.retry_with = [tool for tool in result.retry_with if tool in available]
                return result, usage
        except Exception as e:
            from app.core.observability import log_line
            log_line("RESOURCE OUTPUT ERROR", error=str(e))
            usage = self.router.usage(self.name, LLMProvider.GEMINI, used_live_llm=False)
            
        return self._fallback_tool_decision(node.get("title", ""), available), usage

    def _fallback_tool_decision(self, node_title: str, available: list[str]) -> ResourceToolDecision:
        available = {tool.name for tool in self.tools}
        selected = []
        lower = node_title.lower()
        if "machine learning" in lower or "llm" in lower or "evaluation" in lower:
            selected.append("arxiv_search")
        selected.append("documentation_search")
        if "youtube_search" in available:
            selected.append("youtube_search")
        if "tavily_search" in available:
            selected.append("tavily_search")
        selected = [tool for tool in selected if tool in available]
        retry_with = [tool for tool in ["tavily_search", "documentation_search", "youtube_search"] if tool in available and tool not in selected]
        return ResourceToolDecision(
            thought="Select resources based on whether the node needs papers, documentation, video practice, or broader web coverage.",
            tools=selected,
            retry_with=retry_with,
            quality_threshold=0.6,
        )

    def _quality(self, resources: list[LearningResource]) -> float:
        if not resources:
            return 0.0
        return sum(item.confidence for item in resources) / len(resources)
