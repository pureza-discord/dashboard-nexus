from datetime import datetime
from pydantic import BaseModel, Field


class LeadUpdateRequest(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(novos|contatados|proposta|fechados|perdidos)$")
    ticket_estimado: float | None = Field(default=None, ge=0)
    chance_fechamento: float | None = Field(default=None, ge=0, le=100)
    proximo_follow_up: datetime | None = None
    ultimo_contato: datetime | None = None
    observacoes: str | None = Field(default=None, max_length=4000)
    score: int | None = Field(default=None, ge=0, le=100)


class BulkStatusRequest(BaseModel):
    lead_ids: list[str]
    status: str = Field(pattern=r"^(novos|contatados|proposta|fechados|perdidos)$")


class LeadInput(BaseModel):
    empresa: str = Field(min_length=1, max_length=255)
    telefone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    site: str | None = Field(default=None, max_length=512)
    cidade: str | None = Field(default=None, max_length=120)
    pais: str | None = Field(default=None, max_length=120)
    nicho: str | None = Field(default=None, max_length=180)
    origem: str | None = Field(default=None, max_length=120)
    observacoes: str | None = Field(default=None, max_length=4000)
    ticket_estimado: float | None = Field(default=None, ge=0)
    score: int | None = Field(default=None, ge=0, le=100)
    chance_fechamento: float | None = Field(default=None, ge=0, le=100)


class BulkInsertRequest(BaseModel):
    leads: list[LeadInput]
