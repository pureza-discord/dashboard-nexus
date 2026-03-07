"""LinkedIn lead scraper engine — stub.

IMPORTANT: This is a stub. LinkedIn scraping requires LinkedIn Sales Navigator
API access or a LinkedIn-approved integration. Do NOT scrape LinkedIn directly
without proper authorization.

To enable:
1. Obtain a LinkedIn Sales Navigator API key
2. Set LINKEDIN_API_KEY in your .env
3. Implement the search_leads method using the official API
"""

import logging

logger = logging.getLogger("scraper.linkedin")


class LinkedInEngine:
    """LinkedIn lead scraper (stub — requires API key to activate)."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    async def search_leads(
        self,
        query: str,
        pais: str,
        nicho: str,
        cidade: str | None,
        limite: int,
    ) -> list[dict]:
        """Search LinkedIn for business leads.

        Args:
            query: Search query string.
            pais: Country.
            nicho: Business niche.
            cidade: City (optional).
            limite: Max results.

        Returns:
            List of raw lead dicts.
        """
        if not self.api_key:
            logger.warning("[SCRAPER] LinkedIn engine not configured — LINKEDIN_API_KEY required")
            return []

        # TODO: Implement using LinkedIn Sales Navigator API
        # Example fields to return per lead:
        # {
        #     "nome_empresa": "...",
        #     "telefone": "...",
        #     "email": "...",
        #     "site": "...",
        #     "linkedin": "https://linkedin.com/company/...",
        #     "cidade": "...",
        #     "pais": "...",
        #     "nicho": "...",
        #     "observacoes": "via_linkedin",
        # }

        logger.info("[SCRAPER] LinkedIn search — API integration pending")
        return []
