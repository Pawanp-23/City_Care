"""Staff-controlled handbook indexing and authenticated retrieval diagnostics."""
from fastapi import APIRouter, Depends, HTTPException

from core.apis.dependencies import Principal, manager_principal, staff_principal
from core.services.clinic_rag import handbook_path, index_handbook, retrieve_handbook

router = APIRouter(prefix="/api/v1/rag", tags=["Clinic RAG"])


@router.post("/handbook/index")
async def index_default_handbook(principal: Principal = Depends(manager_principal)) -> dict:
    del principal
    try:
        return {"message": "Handbook indexed", "data": await index_handbook(handbook_path(), "CityCare-Clinic-Patient-Handbook.pdf")}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Handbook indexing failed. Check MongoDB, Gemini embedding configuration, and the server log.") from exc


@router.get("/search")
async def search(question: str, principal: Principal = Depends(staff_principal)) -> dict:
    del principal
    return {"message": "RAG retrieval completed", "data": await retrieve_handbook(question)}
