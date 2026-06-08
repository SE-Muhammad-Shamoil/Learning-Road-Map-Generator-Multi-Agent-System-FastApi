from app.schemas.roadmap import LearningResource


async def search_youtube(*_: object, **__: object) -> list[LearningResource]:
    raise RuntimeError(
        "Use SearchTools.search_youtube through ToolExecutor so calls are traced and backed by the YouTube Data API."
    )
