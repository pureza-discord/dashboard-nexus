import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

from server.core.settings import get_settings
from server.db.models import MarketInsight, User
from server.modules.scraper_service.service import estimate_market_company_count

settings = get_settings()

BRAZIL_CITY_POPULATION = {
    "sao paulo": 11451245,
    "rio de janeiro": 6211223,
    "brasilia": 2817381,
    "fortaleza": 2428678,
    "salvador": 2417678,
    "recife": 1488920,
    "curitiba": 1773718,
    "manaus": 2063547,
    "belo horizonte": 2315560,
    "porto alegre": 1332570,
}


@dataclass(slots=True)
class MarketRequest:
    nicho: str
    cidade: str
    pais: str


def _city_population(city: str) -> int:
    if not city:
        return 900000
    return BRAZIL_CITY_POPULATION.get(city.strip().lower(), 900000)


def _fetch_trends_volume(keyword: str, geo: str) -> float:
    if not settings.enable_external_data:
        raise RuntimeError("External market data is disabled. Set ENABLE_EXTERNAL_DATA=true.")

    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="pt-BR", tz=360)
        pytrends.build_payload([keyword], timeframe="today 12-m", geo=geo)
        interest = pytrends.interest_over_time()
        if interest.empty or keyword not in interest:
            raise RuntimeError("Google Trends returned empty data for this keyword.")
        return float(interest[keyword].mean())
    except Exception as exc:
        raise RuntimeError(f"Google Trends query failed: {exc}") from exc


def _digital_presence_ratio(company_count: int, city_population: int) -> float:
    baseline = min(0.95, max(0.08, (company_count / max(city_population, 1)) * 650))
    return round(baseline, 4)


def _saturation_index(company_count: int, city_population: int) -> float:
    saturation = (company_count / max(city_population, 1)) * 100_000
    return round(min(100.0, saturation), 2)


def _opportunity_index(search_volume: float, saturation_index: float, digital_presence_ratio: float) -> float:
    normalized_search = min(100.0, search_volume)
    competition_penalty = saturation_index * 0.55
    digital_gap_bonus = (1 - min(1.0, digital_presence_ratio)) * 35
    score = normalized_search * 0.75 + digital_gap_bonus - competition_penalty
    return round(max(0.0, min(100.0, score)), 2)


def _market_score(opportunity_index: float, saturation_index: float) -> float:
    value = (opportunity_index * 0.7) + (max(0.0, 100.0 - saturation_index) * 0.3)
    return round(max(0.0, min(100.0, value)), 2)


def _risk_level(market_score: float) -> str:
    if market_score >= 70:
        return "low"
    if market_score >= 45:
        return "medium"
    return "high"


def run_market_analysis(db: Session, user: User, request: MarketRequest) -> dict:
    keyword = f"{request.nicho} {request.cidade}".strip()
    geo = "BR" if request.pais.lower() in {"br", "brasil", "brazil"} else settings.trends_geo_default

    search_volume = _fetch_trends_volume(keyword, geo)
    company_count = estimate_market_company_count(request.nicho, request.cidade, request.pais)
    city_population = _city_population(request.cidade)

    digital_ratio = _digital_presence_ratio(company_count, city_population)
    saturation = _saturation_index(company_count, city_population)
    opportunity = _opportunity_index(search_volume, saturation, digital_ratio)
    score = _market_score(opportunity, saturation)
    risk = _risk_level(score)

    revenue_potential = round((company_count * max(0.02, opportunity / 250.0)) * 1900.0, 2)

    insight = MarketInsight(
        user_id=user.id,
        nicho=request.nicho,
        cidade=request.cidade,
        pais=request.pais,
        search_volume=search_volume,
        company_count=company_count,
        digital_presence_ratio=digital_ratio,
        saturation_index=saturation,
        opportunity_index=opportunity,
        market_score=score,
        revenue_potential=revenue_potential,
        risk_level=risk,
        raw_payload={
            "geo": geo,
            "city_population": city_population,
            "keyword": keyword,
            "inference": {
                "digital_ratio_model": "company_count / city_population",
                "opportunity_model": "search_volume + digital_gap - competition_penalty",
            },
        },
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)

    return {
        "id": str(insight.id),
        "nicho": insight.nicho,
        "cidade": insight.cidade,
        "pais": insight.pais,
        "search_volume": insight.search_volume,
        "company_count": insight.company_count,
        "digital_presence_ratio": insight.digital_presence_ratio,
        "saturation_index": insight.saturation_index,
        "opportunity_index": insight.opportunity_index,
        "market_score": insight.market_score,
        "revenue_potential": float(insight.revenue_potential),
        "risk_level": insight.risk_level,
        "recommendations": _recommendations(insight.market_score, insight.opportunity_index),
    }


def _recommendations(market_score: float, opportunity_index: float) -> list[str]:
    recommendations = []
    if market_score >= 70:
        recommendations.append("Executar campanha outbound imediata no nicho/cidade")
    if opportunity_index >= 55:
        recommendations.append("Priorizar leads com website ausente para oferta de presenca digital")
    else:
        recommendations.append("Segmentar por subnicho para reduzir competicao direta")

    recommendations.append("Rodar nova leitura de mercado em 7 dias para validar tendencia")
    return recommendations


def recent_reports(db: Session, user: User, limit: int = 20) -> list[dict]:
    rows = (
        db.query(MarketInsight)
        .filter(MarketInsight.user_id == user.id)
        .order_by(MarketInsight.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )

    return [
        {
            "id": str(row.id),
            "nicho": row.nicho,
            "cidade": row.cidade,
            "pais": row.pais,
            "market_score": row.market_score,
            "opportunity_index": row.opportunity_index,
            "saturation_index": row.saturation_index,
            "revenue_potential": float(row.revenue_potential),
            "risk_level": row.risk_level,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
