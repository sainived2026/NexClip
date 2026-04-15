"""
Nexearch — Metricool API Client
Enterprise-grade async client for the Metricool REST API.
Handles auth, publishing, scheduling, performance polling, and error recovery.
"""

import asyncio
import base64
import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
import httpx
from typing import Optional, Dict, Any, List
from loguru import logger

from nexearch.config import get_nexearch_settings


class MetricoolError(Exception):
    """Custom exception for Metricool API errors."""
    def __init__(self, message: str, status_code: int = 0, response_body: str = ""):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Metricool Error ({status_code}): {message}")


class MetricoolClient:
    """
    Async Metricool API client with:
    - Retry logic (3 attempts, exponential backoff)
    - Rate limit handling (429 back-off)
    - All publish/poll/brand endpoints
    """

    def __init__(self, api_token: Optional[str] = None, base_url: Optional[str] = None):
        settings = get_nexearch_settings()
        self._token = api_token or settings.METRICOOL_API_TOKEN
        self._base_url = base_url or settings.METRICOOL_BASE_URL
        self._max_retries = 3
        self._base_delay = 1.0  # seconds

        if not self._token:
            logger.warning("MetricoolClient: No API token configured. Publishing will fail.")

    @property
    def is_configured(self) -> bool:
        return bool(self._token)

    def _headers(self) -> Dict[str, str]:
        headers = {
            "X-Mc-Auth": self._token or "",
            "Content-Type": "application/json",
        }
        return headers

    @staticmethod
    def _unwrap_data(payload: Any) -> Any:
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    @staticmethod
    def _sha256_b64(content: bytes) -> str:
        return base64.b64encode(hashlib.sha256(content).digest()).decode("ascii")

    @staticmethod
    def _normalize_publication_datetime(value: Optional[str]) -> tuple[str, str]:
        if not value:
            now_utc = datetime.now(timezone.utc)
            return now_utc.strftime("%Y-%m-%dT%H:%M:%S"), "UTC"

        raw = str(value).strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw, "UTC"

        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

        return parsed.strftime("%Y-%m-%dT%H:%M:%S"), "UTC"

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make an API request with retry and rate limit handling."""
        url = f"{self._base_url}{endpoint}"
        last_error = None

        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self._headers(),
                        json=json_data,
                        params=params,
                    )

                    # Rate limit handling
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", "60"))
                        logger.warning(f"Metricool rate limited. Waiting {retry_after}s...")
                        await asyncio.sleep(retry_after)
                        continue

                    # Success
                    if 200 <= response.status_code < 300:
                        if response.text:
                            return response.json()
                        return {"status": "ok", "status_code": response.status_code}

                    # Client/server error
                    raise MetricoolError(
                        message=response.text[:500],
                        status_code=response.status_code,
                        response_body=response.text,
                    )

            except MetricoolError:
                raise
            except Exception as e:
                last_error = e
                delay = self._base_delay * (2 ** attempt)
                logger.warning(
                    f"Metricool request failed (attempt {attempt + 1}/{self._max_retries}): {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)

        raise MetricoolError(
            message=f"All {self._max_retries} retries failed. Last error: {last_error}",
            status_code=0,
        )

    # ── Brand Management ──────────────────────────────────────

    async def list_profiles(self) -> List[Dict[str, Any]]:
        """List the Metricool profiles available to the authenticated token."""
        result = await self._request("GET", "/admin/simpleProfiles")
        result = self._unwrap_data(result)
        if isinstance(result, list):
            return result
        return result.get("data", []) if isinstance(result, dict) else []

    async def list_brands(self) -> List[Dict[str, Any]]:
        """Backward-compatible alias for the current Metricool profile listing."""
        return await self.list_profiles()

    async def get_brand(self, brand_id: str) -> Dict[str, Any]:
        """Get a specific brand/profile from the available Metricool profiles."""
        for profile in await self.list_profiles():
            if str(profile.get("id", "")) == str(brand_id):
                return profile
        raise MetricoolError(f"Metricool profile '{brand_id}' was not found for this token", status_code=404)

    @staticmethod
    def _normalize_handle(value: str) -> str:
        return (value or "").strip().lower().lstrip("@").rstrip("/")

    async def find_profile(
        self,
        brand_id: str = "",
        account_url: str = "",
        account_handle: str = "",
        platform: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve the most likely Metricool brand/profile for a client.

        Priority:
        1. Explicit brand_id
        2. Exact label match
        3. Exact platform handle match (instagram/twitter/etc)
        4. Exact account_url match
        """
        profiles = await self.list_profiles()
        if not profiles:
            return None

        if brand_id:
            for profile in profiles:
                if str(profile.get("id", "")) == str(brand_id):
                    return profile

        desired_handle = self._normalize_handle(account_handle)
        desired_url = self._normalize_handle(account_url)
        platform = self._normalize_handle(platform)

        def matches(profile: Dict[str, Any]) -> bool:
            label = self._normalize_handle(str(profile.get("label", "")))
            if desired_handle and label == desired_handle:
                return True

            if platform:
                platform_value = self._normalize_handle(str(profile.get(platform, "")))
                if desired_handle and platform_value == desired_handle:
                    return True
                if desired_url and platform_value and desired_url.endswith(platform_value):
                    return True

            profile_url = self._normalize_handle(str(profile.get("url", "")))
            return bool(desired_url and profile_url == desired_url)

        for profile in profiles:
            if matches(profile):
                return profile
        return None

    # ── Publishing ────────────────────────────────────────────

    async def add_post(
        self,
        brand_id: str,
        user_id: str,
        network: str,
        text: str,
        publish_date: str,
        video_url: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Schedule a post via Metricool.

        Args:
            brand_id: Metricool brand profile ID
            network: Platform network (instagram, tiktok, youtube, twitter, linkedin, facebook)
            text: Post caption/text
            publish_date: ISO8601 datetime for scheduling
            video_url: Public URL to the video file
            thumbnail_url: Optional thumbnail URL
            title: Optional post title (YouTube, Facebook)
        """
        publication_date, publication_timezone = self._normalize_publication_datetime(publish_date)

        payload: Dict[str, Any] = {
            "text": text,
            "publicationDate": {
                "dateTime": publication_date,
                "timezone": publication_timezone,
            },
            "providers": [{"network": network, "id": str(brand_id)}],
            "autoPublish": True,
            "saveExternalMediaFiles": True,
        }
        if str(brand_id).isdigit():
            payload["targetBrandId"] = int(brand_id)

        if video_url:
            payload["media"] = [video_url]
        if thumbnail_url:
            payload["videoThumbnailUrl"] = thumbnail_url
        if network == "instagram" and video_url:
            payload["instagramData"] = {
                "type": "REEL",
                "showReelOnFeed": True,
            }
        if title and network in {"youtube", "facebook", "linkedin"}:
            payload[f"{network}Data"] = {"title": title}

        return await self._request(
            "POST",
            "/v2/scheduler/posts",
            json_data=payload,
            params={"blogId": str(brand_id), "userId": str(user_id)},
        )

    async def upload_media_file(self, file_path: str, resource_type: str = "planner") -> str:
        """Upload a local file to Metricool-hosted media storage and return its public URL."""
        path = Path(file_path)
        if not path.exists():
            raise MetricoolError(f"Metricool media upload failed: file not found at '{file_path}'")

        file_bytes = path.read_bytes()
        if not file_bytes:
            raise MetricoolError(f"Metricool media upload failed: '{file_path}' is empty")

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        part_size = 5 * 1024 * 1024
        parts: List[Dict[str, Any]] = []
        for start in range(0, len(file_bytes), part_size):
            end = min(start + part_size, len(file_bytes))
            chunk = file_bytes[start:end]
            parts.append({
                "size": len(chunk),
                "startByte": start,
                "endByte": end,
                "hash": self._sha256_b64(chunk),
            })

        upload = self._unwrap_data(await self._request(
            "PUT",
            "/v2/media/s3/upload-transactions",
            json_data={
                "resourceType": resource_type,
                "contentType": content_type,
                "fileExtension": path.suffix.lstrip("."),
                "parts": parts,
            },
        ))

        async with httpx.AsyncClient(timeout=180.0) as client:
            if upload.get("parts"):
                completed_parts = []
                for server_part in upload["parts"]:
                    chunk = file_bytes[server_part["startByte"]:server_part["endByte"]]
                    response = await client.put(
                        server_part["presignedUrl"],
                        content=chunk,
                        headers={
                            "Content-Length": str(len(chunk)),
                            "x-amz-checksum-sha256": self._sha256_b64(chunk),
                        },
                    )
                    response.raise_for_status()
                    etag = response.headers.get("etag") or response.headers.get("ETag")
                    if not etag:
                        raise MetricoolError(
                            f"Metricool media upload failed: missing ETag for part {server_part['partNumber']}"
                        )
                    completed_parts.append({
                        "partNumber": server_part["partNumber"],
                        "etag": etag,
                    })

                completed = self._unwrap_data(await self._request(
                    "PATCH",
                    "/v2/media/s3/upload-transactions",
                    json_data={
                        "multipart": {
                            "uploadId": upload["uploadId"],
                            "key": upload["key"],
                            "parts": completed_parts,
                        }
                    },
                ))
            else:
                presigned_url = upload.get("presignedUrl")
                if not presigned_url:
                    raise MetricoolError("Metricool media upload failed: no presigned upload URL was returned")
                response = await client.put(
                    presigned_url,
                    content=file_bytes,
                    headers={
                        "Content-Length": str(len(file_bytes)),
                        "x-amz-checksum-sha256": self._sha256_b64(file_bytes),
                    },
                )
                response.raise_for_status()
                completed = self._unwrap_data(await self._request(
                    "PATCH",
                    "/v2/media/s3/upload-transactions",
                    json_data={"simple": {"fileUrl": upload.get("fileUrl", "")}},
                ))

        media_url = completed.get("convertedFileUrl") or completed.get("fileUrl") or upload.get("fileUrl")
        if not media_url:
            raise MetricoolError("Metricool media upload failed: no hosted media URL was returned")
        return str(media_url)

    async def update_post(
        self,
        brand_id: str,
        post_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a scheduled post."""
        return await self._request(
            "PUT",
            f"/v2/scheduler/posts/{post_id}",
            json_data=updates,
        )

    async def delete_post(self, brand_id: str, post_id: str) -> Dict[str, Any]:
        """Delete a scheduled post."""
        return await self._request(
            "DELETE",
            f"/v2/scheduler/posts/{post_id}",
        )

    async def list_scheduled_posts(
        self,
        brand_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all scheduled posts for a brand."""
        params = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return await self._request(
            "GET",
            "/v2/scheduler/posts",
            params=params,
        )

    # ── Performance Polling ────────────────────────────────────

    async def get_post_statistics(
        self,
        brand_id: str,
        post_id: str,
    ) -> Dict[str, Any]:
        """Get performance statistics for a specific post."""
        return await self._request(
            "GET",
            f"/v2/scheduler/posts/{post_id}",
        )

    async def get_analytics(
        self,
        brand_id: str,
        network: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """Get analytics for a network in a date range."""
        return await self._request(
            "GET",
            f"/analytics/{network}",
            params={"startDate": start_date, "endDate": end_date},
        )

    # ── Utility ────────────────────────────────────────────────

    async def test_connection(self) -> bool:
        """Test if the API token is valid."""
        try:
            await self.list_profiles()
            return True
        except Exception as e:
            logger.error(f"Metricool connection test failed: {e}")
            return False


# ── Singleton ────────────────────────────────────────────────

_metricool_instances: Dict[str, MetricoolClient] = {}


def get_metricool_client(access_token: Optional[str] = None) -> MetricoolClient:
    """
    Factory — returns a shared client for the requested token context.

    The default environment token keeps singleton behavior, while client-specific
    Metricool tokens receive isolated client instances so one customer's token
    never bleeds into another publish session.
    """
    cache_key = access_token or "__default__"
    if cache_key not in _metricool_instances:
        _metricool_instances[cache_key] = MetricoolClient(api_token=access_token)
    return _metricool_instances[cache_key]
