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
    company_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=512)
    website: str | None = Field(default=None, max_length=512)
    rating: float | None = None
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    niche: str | None = Field(default=None, max_length=180)
    source: str | None = Field(default=None, max_length=120)

    # backward-compatible aliases accepted by current UI/integrations
    empresa: str | None = Field(default=None, max_length=255)
    telefone: str | None = Field(default=None, max_length=64)
    site: str | None = Field(default=None, max_length=512)
    cidade: str | None = Field(default=None, max_length=120)
    pais: str | None = Field(default=None, max_length=120)
    nicho: str | None = Field(default=None, max_length=180)
    origem: str | None = Field(default=None, max_length=120)


class BulkInsertRequest(BaseModel):
    leads: list[LeadInput]
