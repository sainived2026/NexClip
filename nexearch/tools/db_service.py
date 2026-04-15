"""
Nexearch — Database Service
Centralized CRUD operations for all Nexearch models.
Uses NexClip's existing database session.
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from nexearch.models import (
    NexearchClient, NexearchRawPost, NexearchAnalyzedPost, NexearchScoredPost,
    NexearchAccountDNA, NexearchAccountDNAHistory, NexearchClipDirective,
    NexearchPublishedPost, NexearchPerformanceResult, NexearchPublishedClipScore,
    NexearchEvolutionLog, NexearchPromptOverride, NexearchClientConfig,
    NexearchClientWritingProfile,
)


def _utcnow():
    return datetime.now(timezone.utc)


class NexearchDB:
    """Centralized database operations for Nexearch."""

    def __init__(self, session: Session):
        self.db = session

    # ── Client CRUD ───────────────────────────────────────────

    def create_client(self, **kwargs) -> NexearchClient:
        client = NexearchClient(**kwargs)
        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)
        return client

    def get_client(self, client_id: str) -> Optional[NexearchClient]:
        return self.db.query(NexearchClient).filter(NexearchClient.id == client_id).first()

    def get_clients_by_user(self, user_id: str) -> List[NexearchClient]:
        return self.db.query(NexearchClient).filter(
            NexearchClient.client_id == user_id, NexearchClient.is_active == True
        ).all()

    def get_active_clients(self) -> List[NexearchClient]:
        return self.db.query(NexearchClient).filter(
            NexearchClient.is_active == True, NexearchClient.is_paused == False
        ).all()

    def update_client(self, client_id: str, **kwargs) -> Optional[NexearchClient]:
        client = self.get_client(client_id)
        if not client:
            return None
        for key, value in kwargs.items():
            if hasattr(client, key) and value is not None:
                setattr(client, key, value)
        client.updated_at = _utcnow()
        self.db.commit()
        self.db.refresh(client)
        return client

    # ── Raw Post CRUD ─────────────────────────────────────────

    def upsert_raw_post(self, client_id: str, post_data: Dict[str, Any]) -> NexearchRawPost:
        """Insert or update a raw post (upsert on client_id + post_id + platform)."""
        existing = self.db.query(NexearchRawPost).filter(
            NexearchRawPost.client_id == client_id,
            NexearchRawPost.post_id == post_data.get("post_id", ""),
            NexearchRawPost.platform == post_data.get("platform", ""),
        ).first()

        if existing:
            # Update metrics only
            for field in ["likes", "comments", "shares", "saves", "views", "reach",
                          "impressions", "engagement_rate", "replies", "retweets", "quotes"]:
                metrics = post_data.get("metrics", {})
                if isinstance(metrics, dict) and field in metrics:
                    setattr(existing, field, metrics[field])
                elif field in post_data:
                    setattr(existing, field, post_data[field])
            existing.last_updated_at = _utcnow()
            self.db.commit()
            return existing

        # Create new
        metrics = post_data.pop("metrics", {})
        if isinstance(metrics, dict):
            for k, v in metrics.items():
                if k not in post_data:
                    post_data[k] = v

        # Convert lists to JSON strings
        for field in ["hashtags", "mentions", "tags", "media_urls"]:
            if field in post_data and isinstance(post_data[field], list):
                post_data[field] = json.dumps(post_data[field])
        if "reactions" in post_data and isinstance(post_data.get("reactions"), dict):
            post_data["reactions"] = json.dumps(post_data["reactions"])

        post = NexearchRawPost(client_id=client_id, **post_data)
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def get_raw_posts(self, client_id: str, limit: int = 100, offset: int = 0,
                      format_filter: Optional[str] = None) -> List[NexearchRawPost]:
        q = self.db.query(NexearchRawPost).filter(NexearchRawPost.client_id == client_id)
        if format_filter:
            q = q.filter(NexearchRawPost.format == format_filter)
        return q.order_by(desc(NexearchRawPost.posted_at)).offset(offset).limit(limit).all()

    def get_raw_post_count(self, client_id: str) -> int:
        return self.db.query(func.count(NexearchRawPost.id)).filter(
            NexearchRawPost.client_id == client_id
        ).scalar() or 0

    # ── Analyzed Post CRUD ────────────────────────────────────

    def save_analysis(self, post_id: str, client_id: str, analysis: Dict[str, Any],
                      **kwargs) -> NexearchAnalyzedPost:
        existing = self.db.query(NexearchAnalyzedPost).filter(
            NexearchAnalyzedPost.post_id == post_id, NexearchAnalyzedPost.client_id == client_id
        ).first()

        if existing:
            existing.analysis_json = json.dumps(analysis, default=str)
            for k, v in kwargs.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            existing.analyzed_at = _utcnow()
            self.db.commit()
            return existing

        ap = NexearchAnalyzedPost(
            post_id=post_id, client_id=client_id,
            analysis_json=json.dumps(analysis, default=str), **kwargs,
        )
        self.db.add(ap)
        self.db.commit()
        self.db.refresh(ap)
        return ap

    def get_analyzed_posts(self, client_id: str, limit: int = 100) -> List[NexearchAnalyzedPost]:
        return self.db.query(NexearchAnalyzedPost).filter(
            NexearchAnalyzedPost.client_id == client_id
        ).order_by(desc(NexearchAnalyzedPost.analyzed_at)).limit(limit).all()

    # ── Scored Post CRUD ──────────────────────────────────────

    def save_score(self, post_id: str, client_id: str, **kwargs) -> NexearchScoredPost:
        existing = self.db.query(NexearchScoredPost).filter(
            NexearchScoredPost.post_id == post_id, NexearchScoredPost.client_id == client_id
        ).first()

        if existing:
            for k, v in kwargs.items():
                if hasattr(existing, k): setattr(existing, k, v)
            self.db.commit()
            return existing

        sp = NexearchScoredPost(post_id=post_id, client_id=client_id, **kwargs)
        self.db.add(sp)
        self.db.commit()
        self.db.refresh(sp)
        return sp

    def get_scored_posts_by_tier(self, client_id: str, tier: str,
                                  limit: int = 50) -> List[NexearchScoredPost]:
        return self.db.query(NexearchScoredPost).filter(
            NexearchScoredPost.client_id == client_id, NexearchScoredPost.tier == tier
        ).order_by(desc(NexearchScoredPost.total_score)).limit(limit).all()

    def get_tier_distribution(self, client_id: str) -> Dict[str, int]:
        counts = {"S": 0, "A": 0, "B": 0, "C": 0}
        rows = self.db.query(
            NexearchScoredPost.tier, func.count(NexearchScoredPost.id)
        ).filter(NexearchScoredPost.client_id == client_id).group_by(NexearchScoredPost.tier).all()
        for tier, count in rows:
            counts[tier] = count
        return counts

    # ── Account DNA CRUD ──────────────────────────────────────

    def save_dna(self, client_id: str, dna_data: Dict[str, Any],
                 **kwargs) -> NexearchAccountDNA:
        existing = self.db.query(NexearchAccountDNA).filter(
            NexearchAccountDNA.client_id == client_id
        ).first()

        if existing:
            # Archive current version
            history = NexearchAccountDNAHistory(
                client_id=client_id, dna_json=existing.dna_json,
                dna_version=existing.dna_version,
            )
            self.db.add(history)

            existing.dna_json = json.dumps(dna_data, default=str)
            for k, v in kwargs.items():
                if hasattr(existing, k): setattr(existing, k, v)
            existing.updated_at = _utcnow()
            self.db.commit()
            return existing

        dna = NexearchAccountDNA(
            client_id=client_id, dna_json=json.dumps(dna_data, default=str), **kwargs,
        )
        self.db.add(dna)
        self.db.commit()
        self.db.refresh(dna)
        return dna

    def get_dna(self, client_id: str) -> Optional[NexearchAccountDNA]:
        return self.db.query(NexearchAccountDNA).filter(
            NexearchAccountDNA.client_id == client_id
        ).first()

    # ── Clip Directive CRUD ───────────────────────────────────

    def save_directive(self, client_id: str, directive_data: Dict[str, Any],
                       **kwargs) -> NexearchClipDirective:
        # Deactivate previous directives
        self.db.query(NexearchClipDirective).filter(
            NexearchClipDirective.client_id == client_id,
            NexearchClipDirective.is_active == True,
        ).update({"is_active": False, "deactivated_at": _utcnow()})

        directive = NexearchClipDirective(
            client_id=client_id,
            directive_json=json.dumps(directive_data, default=str),
            **kwargs,
        )
        self.db.add(directive)
        self.db.commit()
        self.db.refresh(directive)
        return directive

    def get_active_directive(self, client_id: str) -> Optional[NexearchClipDirective]:
        return self.db.query(NexearchClipDirective).filter(
            NexearchClipDirective.client_id == client_id,
            NexearchClipDirective.is_active == True,
        ).first()

    # ── Published Post CRUD ───────────────────────────────────

    def create_published_post(self, **kwargs) -> NexearchPublishedPost:
        pp = NexearchPublishedPost(**kwargs)
        self.db.add(pp)
        self.db.commit()
        self.db.refresh(pp)
        return pp

    def get_published_posts(self, client_id: str, status: Optional[str] = None,
                             limit: int = 50) -> List[NexearchPublishedPost]:
        q = self.db.query(NexearchPublishedPost).filter(NexearchPublishedPost.client_id == client_id)
        if status:
            q = q.filter(NexearchPublishedPost.publish_status == status)
        return q.order_by(desc(NexearchPublishedPost.created_at)).limit(limit).all()

    def get_pending_approval(self, client_id: Optional[str] = None) -> List[NexearchPublishedPost]:
        q = self.db.query(NexearchPublishedPost).filter(
            NexearchPublishedPost.publish_status == "pending",
            NexearchPublishedPost.requires_approval == True,
        )
        if client_id:
            q = q.filter(NexearchPublishedPost.client_id == client_id)
        return q.order_by(NexearchPublishedPost.created_at).all()

    # ── Performance CRUD ──────────────────────────────────────

    def save_performance(self, **kwargs) -> NexearchPerformanceResult:
        pr = NexearchPerformanceResult(**kwargs)
        self.db.add(pr)
        self.db.commit()
        self.db.refresh(pr)
        return pr

    # ── Evolution Log CRUD ────────────────────────────────────

    def log_evolution(self, **kwargs) -> NexearchEvolutionLog:
        evo = NexearchEvolutionLog(**kwargs)
        self.db.add(evo)
        self.db.commit()
        self.db.refresh(evo)
        return evo

    # ── Client Config CRUD ────────────────────────────────────

    def get_or_create_config(self, client_id: str) -> NexearchClientConfig:
        existing = self.db.query(NexearchClientConfig).filter(
            NexearchClientConfig.client_id == client_id
        ).first()
        if existing:
            return existing
        config = NexearchClientConfig(client_id=client_id)
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def get_writing_profile(self, client_id: str, platform: str) -> Optional[NexearchClientWritingProfile]:
        return self.db.query(NexearchClientWritingProfile).filter(
            NexearchClientWritingProfile.client_id == client_id,
            NexearchClientWritingProfile.platform == platform,
            NexearchClientWritingProfile.is_active == True,
        ).first()

    def save_writing_profile(self, client_id: str, platform: str,
                              **kwargs) -> NexearchClientWritingProfile:
        existing = self.get_writing_profile(client_id, platform)
        if existing:
            for k, v in kwargs.items():
                if hasattr(existing, k): setattr(existing, k, v)
            existing.updated_at = _utcnow()
            self.db.commit()
            return existing

        wp = NexearchClientWritingProfile(client_id=client_id, platform=platform, **kwargs)
        self.db.add(wp)
        self.db.commit()
        self.db.refresh(wp)
        return wp
