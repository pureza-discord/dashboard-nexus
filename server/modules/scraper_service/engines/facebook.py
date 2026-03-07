"""Facebook Marketplace / Pages lead scraper engine — stub.

IMPORTANT: This is a stub. Facebook scraping requires Facebook Graph API
access (approved app with proper permissions). Do NOT scrape Facebook directly.

To enable:
1. Create a Facebook App at developers.facebook.com
2. Request pages_search_v2 and pages_info permissions
3. Set FACEBOOK_APP_ID and FACEBOOK_APP_SECRET in your .env
4. Implement the search_leads method using Graph API
"""

import logging

logger = logging.getLogger("scraper.facebook")


class FacebookEngine:
    """Facebook Marketplace / Pages lead scraper (stub — requires API access)."""

    def __init__(self, app_id: str | None = None, app_secret: str | None = None) -> None:
        self.app_id = app_id
        self.app_secret = app_secret

    async def search_leads(
        self,
        query: str,
        pais: str,
        nicho: str,
        cidade: str | None,
        limite: int,
    ) -> list[dict]:
        """Search Facebook for business leads.

        Args:
            query: Search query string.
            pais: Country.
            nicho: Business niche.
            cidade: City (optional).
            limite: Max results.

        Returns:
            List of raw lead dicts.
        """
        if not self.app_id:
            logger.warning("[SCRAPER] Facebook engine not configured — FACEBOOK_APP_ID required")
            return []

        # TODO: Implement using Facebook Graph API
        # Example fields to return per lead:
        # {
        #     "nome_empresa": "...",
        #     "telefone": "...",
        #     "email": "...",
        #     "site": "...",
        #     "facebook": "https://facebook.com/...",
        #     "cidade": "...",
        #     "pais": "...",
        #     "nicho": "...",
        #     "observacoes": "via_facebook",
        # }

        logger.info("[SCRAPER] Facebook search — API integration pending")
        return []
