thonimport json
import logging
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

@dataclass
class InstagramProfile:
    id: str
    full_name: str
    is_private: bool
    fbid_v2: Optional[int]
    profile_pic_id: Optional[str]
    profile_pic_url: Optional[str]
    is_verified: bool
    username: str
    latest_reel_media: Optional[int]
    followed_by: str

    @classmethod
    def from_raw(cls, node: Dict[str, Any], followed_by: str) -> "InstagramProfile":
        """
        Build a profile object from a raw Instagram node.
        The field names and structure are loosely based on Instagram's
        public JSON responses, but this function is defensive and tolerant
        of missing keys.
        """
        # Instagram has sometimes used "pk" or "id" for the primary key
        pk = str(
            node.get("id")
            or node.get("pk")
            or node.get("pk_id")
            or node.get("strong_id__")
            or ""
        )

        profile_pic_id = node.get("profile_pic_id")
        profile_pic_url = node.get("profile_pic_url")
        fbid_v2 = None
        try:
            if "fbid_v2" in node and node["fbid_v2"] is not None:
                fbid_v2 = int(node["fbid_v2"])
        except (ValueError, TypeError):
            fbid_v2 = None

        latest_reel_media = None
        try:
            if "latest_reel_media" in node and node["latest_reel_media"] is not None:
                latest_reel_media = int(node["latest_reel_media"])
        except (ValueError, TypeError):
            latest_reel_media = None

        return cls(
            id=pk,
            full_name=node.get("full_name") or "",
            is_private=bool(node.get("is_private", False)),
            fbid_v2=fbid_v2,
            profile_pic_id=profile_pic_id,
            profile_pic_url=profile_pic_url,
            is_verified=bool(node.get("is_verified", False)),
            username=node.get("username") or "",
            latest_reel_media=latest_reel_media,
            followed_by=followed_by,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class InstagramParser:
    """
    Lightweight Instagram 'following' scraper based on publicly available
    web endpoints.

    This implementation does not use authentication by default; in practice
    you may want to provide cookies and headers via the session attribute
    for more reliable scraping.
    """

    def __init__(
        self,
        base_url: str = "https://www.instagram.com",
        timeout: int = 15,
        max_following: int = 10000,
        user_agent: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_following = max_following

        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent",
            user_agent
            or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
        )
        self.session.headers.setdefault("Accept", "text/html,application/json")

    def _fetch_profile_json(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Fetch basic profile JSON. Historically available via ?__a=1,
        though Instagram changes this periodically.

        This method is defensive: on any failure, we log an error and
        return None instead of raising.
        """
        url = f"{self.base_url}/{username}/?__a=1&__d=dis"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                logger.warning(
                    "Failed to fetch profile JSON for %s (status %s)",
                    username,
                    resp.status_code,
                )
                return None
            return resp.json()
        except requests.RequestException as exc:
            logger.error("Network error fetching profile JSON for %s: %s", username, exc)
        except json.JSONDecodeError as exc:
            logger.error("Failed to decode profile JSON for %s: %s", username, exc)
        return None

    def _extract_following_from_profile_json(
        self, profile_json: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract following nodes from a profile JSON blob.
        We support a couple of older structures to be tolerant
        of minor changes.
        """
        # Old structure: graphql.user.edge_follow.edges
        graphql = profile_json.get("graphql") or {}
        user = graphql.get("user") or {}
        edge_follow = user.get("edge_follow") or {}

        edges = edge_follow.get("edges") or []
        nodes: List[Dict[str, Any]] = []
        for edge in edges:
            node = edge.get("node") or {}
            if node:
                nodes.append(node)

        # Some responses may contain different keys; this is easily extended.
        return nodes

    def get_following(self, username: str) -> List[InstagramProfile]:
        """
        Fetch the list of profiles that `username` is following.

        This method attempts to use public JSON from the user's profile page.
        In case of failure (e.g., Instagram layout change), it returns an empty list
        instead of crashing.
        """
        profiles: List[InstagramProfile] = []
        profile_json = self._fetch_profile_json(username)
        if not profile_json:
            logger.warning(
                "No profile JSON returned for '%s'; returning empty following list",
                username,
            )
            return profiles

        nodes = self._extract_following_from_profile_json(profile_json)
        logger.info(
            "Initial JSON contained %d following entries for '%s'", len(nodes), username
        )

        for node in nodes[: self.max_following]:
            try:
                profiles.append(InstagramProfile.from_raw(node, followed_by=username))
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to parse following node for '%s': %s", username, exc)

        # NOTE: Proper pagination would require using Instagram's GraphQL or internal APIs.
        # For the sake of this example, we take only the first page of results.
        if len(profiles) >= self.max_following:
            logger.info(
                "Reached max_following (%d) for '%s'; truncating results",
                self.max_following,
                username,
            )

        # A small sleep helps avoid aggressive rate limiting if running repeatedly.
        time.sleep(0.5)
        return profiles