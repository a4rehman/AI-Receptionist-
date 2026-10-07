from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import select
from receptionist.tools.registry import tool, ToolContext, ToolResult
from receptionist.db.models import FAQ


class SearchFAQArgs(BaseModel):
    query: str = Field(..., description="Search query for FAQ")
    category: Optional[str] = Field(None, description="Filter by category")
    limit: int = Field(5, description="Maximum results")


@tool(name="search_faq", description="Search the tenant's FAQ knowledge base", input_schema=SearchFAQArgs, permission="read")
async def search_faq(args: SearchFAQArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory
    async with async_session_factory() as session:
        query = select(FAQ).where(
            FAQ.tenant_id == ctx.tenant_id,
            FAQ.is_active == True,
        )
        if args.category:
            query = query.where(FAQ.category == args.category)
        if args.query:
            query = query.where(
                (FAQ.question.ilike(f"%{args.query}%")) | (FAQ.answer.ilike(f"%{args.query}%"))
            )
        query = query.limit(args.limit)
        result = await session.execute(query)
        faqs = result.scalars().all()
        return ToolResult(success=True, data=[
            {
                "id": f.id,
                "question": f.question,
                "answer": f.answer,
                "category": f.category,
            }
            for f in faqs
        ])
