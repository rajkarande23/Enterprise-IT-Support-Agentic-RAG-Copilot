from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from pydantic import BaseModel, Field
from app.core.config import get_settings
from app.rag.workflow import ask
from app.rag.vectorstore import add_documents 
from app.services.ingestion import load_file, chunk_documents, SUPPORTED
from app.services.audit import write_audit
from app.services.tickets import (
    create_ticket,
    list_tickets,
    get_ticket,
    update_ticket_status,
)

router = APIRouter(prefix="/api")
settings = get_settings()

class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=3000)

class CreateTicketRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=2000)
    category: str = Field(default="General IT")
    priority: str = Field(default="Medium")
    requester_email: str = Field(default="employee@novacore.internal")

class UpdateTicketStatusRequest(BaseModel):
    status: str = Field(pattern="^(Open|In Progress|Resolved|Closed)$")


@router.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@router.post("/chat")
def chat(payload: ChatRequest):
    try:
        result = ask(payload.question)
        write_audit(payload.question, result["source_used"], result.get("trace", []))

        return {
            "answer": result["answer"],
            "source_used": result["source_used"],
            "trace": result.get("trace", []),
            "citations": result.get("citations", []),
            "rewritten_query": result.get("current_query", payload.question),
            "ticket": result.get("ticket"),
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ingest")
async def ingest(file: UploadFile = File(...), x_admin_key: str = Header(default="")):
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(status_code=400, detail=f"Supported: {', '.join(sorted(SUPPORTED))}")
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / Path(file.filename).name
    dest.write_bytes(await file.read())
    docs = load_file(dest)
    chunks = chunk_documents(docs)
    ids = add_documents(chunks)
    return {"message": "Document indexed", "file": dest.name, "chunks": len(chunks), "ids_created": len(ids)}


# --- IT Support Ticket Endpoints ---

@router.get("/tickets")
def get_all_tickets(status: Optional[str] = None):
    try:
        tickets = list_tickets(status=status)
        stats = {
            "total": len(tickets),
            "open": sum(1 for t in tickets if t["status"] == "Open"),
            "in_progress": sum(1 for t in tickets if t["status"] == "In Progress"),
            "resolved": sum(1 for t in tickets if t["status"] in ("Resolved", "Closed")),
        }
        return {"tickets": tickets, "stats": stats}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/tickets")
def submit_ticket(payload: CreateTicketRequest):
    try:
        ticket = create_ticket(
            title=payload.title,
            description=payload.description,
            category=payload.category,
            priority=payload.priority,
            requester_email=payload.requester_email,
            source="portal_submission",
        )
        return {"message": "Ticket created successfully", "ticket": ticket}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/tickets/{ticket_id}")
def get_ticket_by_id(ticket_id: str):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return {"ticket": ticket}


@router.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: str, payload: UpdateTicketStatusRequest):
    ticket = update_ticket_status(ticket_id, payload.status)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return {"message": f"Ticket {ticket_id} status updated to {payload.status}", "ticket": ticket}
