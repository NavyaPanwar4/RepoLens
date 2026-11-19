from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.vector_store import query_chunks
from app.services.llm import ask_llm, summarise_bugs
from app.services.repository_store import get_analysis

router = APIRouter()

class AskPayload(BaseModel):
    repo_id: str
    question: str
    summary: dict = None
    context: dict = None

class BugSummaryPayload(BaseModel):
    findings: list

@router.post("/ask")
async def ask_question(payload: AskPayload):
    try:
        hits = query_chunks(payload.repo_id, payload.question, n_results=40)
        analysis = get_analysis(payload.repo_id) or {}
        repository_context = payload.context or {}
        if analysis:
            repository_context = {
                **repository_context,
                "summary": analysis.get("summary", {}),
                "overview": analysis.get("overview", {}),
                "graph": analysis.get("graph", {}),
            }
        answer = ask_llm(
            payload.question,
            hits,
            summary=payload.summary,
            repository_context=repository_context,
        )
        return {
            "question": payload.question,
            "answer": answer,
            "context_chunks": hits,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/bugs/explain")
async def explain_bugs(payload: BugSummaryPayload):
    try:
        explanation = summarise_bugs(payload.findings)
        return {"explanation": explanation}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))