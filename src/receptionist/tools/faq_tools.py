import re

from pydantic import BaseModel, Field
from sqlalchemy import select

from receptionist.db.models import FAQ
from receptionist.tools.registry import ToolContext, ToolResult, tool

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be", "been",
    "being", "do", "does", "did", "can", "could", "would", "should", "will", "shall",
    "may", "might", "must", "i", "you", "we", "they", "he", "she", "it", "my", "your",
    "our", "their", "his", "her", "this", "that", "these", "those", "to", "of", "in",
    "on", "for", "with", "at", "by", "from", "as", "if", "then", "so", "not", "no",
    "yes", "what", "which", "who", "whom", "whose", "how", "when", "where", "why",
    "about", "into", "out", "up", "down", "me", "us", "them", "him", "am", "there",
    "here", "get", "got", "have", "has", "had", "tell", "please", "something", "anything",
}


def _search_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9']+", (text or "").lower())
    return [t for t in tokens if len(t) > 2 and t not in _STOPWORDS]


class SearchFAQArgs(BaseModel):
    query: str = Field(..., description="Search query for FAQ")
    category: str | None = Field(None, description="Filter by category")
    limit: int = Field(5, description="Maximum results")


@tool(name="search_faq", description="Search the tenant's FAQ knowledge base", input_schema=SearchFAQArgs, permission="read")
async def search_faq(args: SearchFAQArgs, ctx: ToolContext) -> ToolResult:
    from receptionist.db.engine import async_session_factory

    async with async_session_factory() as session:
        stmt = select(FAQ).where(
            FAQ.tenant_id == ctx.tenant_id,
            FAQ.is_active == True,
        )
        if args.category:
            stmt = stmt.where(FAQ.category == args.category)
        stmt = stmt.limit(100)
        rows = (await session.execute(stmt)).scalars().all()

        # Match on meaningful words rather than the whole raw sentence, which a
        # substring LIKE on the customer's full message could never satisfy.
        tokens = _search_tokens(args.query)
        if not tokens:
            hits = rows
        else:
            ranked: list[tuple[int, FAQ]] = []
            for row in rows:
                haystack = f"{row.question} {row.answer}".lower()
                score = sum(
                    1 for token in tokens
                    if re.search(rf"\b{re.escape(token)}", haystack)
                )
                if score:
                    ranked.append((score, row))
            ranked.sort(key=lambda pair: (-pair[0], pair[1].id))
            hits = [row for _, row in ranked]

        return ToolResult(success=True, data=[
            {
                "id": row.id,
                "question": row.question,
                "answer": row.answer,
                "category": row.category,
            }
            for row in hits[: args.limit]
        ])
