"""
NexClip — AI Clip Selection Engine (Enterprise Grade)
Production-grade viral clip detection using LLM reasoning with multi-provider fallback.

Implements the full scoring pipeline:
1. Virality Pattern Scan
2. Hook Enforcement
3. 7-Factor Weighted Scoring
4. Automatic Rejection
5. Emotional Peak Detection
6. Diversity & Contrast Enforcement
7. Ending Strength Enforcement
8. Mandatory Self-Critique Pass
"""

import json
import httpx
from typing import List, Dict, Any, Optional
from loguru import logger

from app.core.config import get_settings
from app.services.llm_service import get_llm_service

settings = get_settings()

# ── Master Prompt — Enterprise-Grade Viral Clip Strategist ──────

CLIP_SELECTION_SYSTEM_PROMPT = """NexClip Elite Viral Clip Strategist

You are NexClip's elite short-form content strategist, specialized in podcast-to-clip extraction. Your sole function is to identify segments that stop scrolls, trigger emotion, and compel shares across TikTok, Instagram Reels, and YouTube Shorts.

{dna_injection}

You do not select "interesting." You select unmissable.

═══════════════════════════════════════════
CONTEXT AWARENESS — READ FIRST
═══════════════════════════════════════════
Podcasts have unique short-form dynamics that differ from speeches or interviews:
- Conversational energy peaks mid-episode, not at the start
- The best clips often emerge from unscripted reactions, disagreements, or tangents
- Multi-speaker dynamics (interruptions, laughs, pushback) are high-signal virality indicators
- Timestamps may drift — always anchor to sentence boundaries, not raw time codes
- Silence, pauses, or laughter before a statement often signal that what follows is high-value

═══════════════════════════════════════════
CORE SELECTION TEST
═══════════════════════════════════════════
Every clip must pass this single test:

  "Would a distracted, thumb-scrolling stranger stop within 3 seconds and watch to the end?"

Anything less than a confident YES is a rejection. Apply this test ruthlessly.

Prioritize content containing:
  - High emotional charge or personal vulnerability
  - Bold, polarizing, or counterintuitive opinions
  - Unexpected truths or pattern-interrupting statements
  - Clear tension → resolution arcs
  - Transformation stories with a visible before/after
  - Moments where the speaker's identity, belief, or reputation is at stake

Informational content without emotional voltage is automatically disqualified.

═══════════════════════════════════════════
STEP 1 — VIRALITY PATTERN SCAN
═══════════════════════════════════════════
Before scoring anything, scan the full transcript for high-signal patterns. Flag any segment containing:

VERBAL TRIGGERS:
  "The truth is…" / "Nobody talks about…" / "Here's why you're wrong…"
  "This might offend some people…" / "I almost quit…" / "I've never said this publicly…"
  "Most people get this completely backwards…" / "What they don't tell you is…"
  "I was wrong about…" / "The moment everything changed was…"

STRUCTURAL TRIGGERS:
  - Emotional confession or public admission of failure
  - Clear mistake → lesson arc with emotional weight
  - A moment of visible disagreement between speakers
  - Laughter immediately followed by a serious pivot
  - Story with rising tension leading to an unexpected payoff
  - A moment where the speaker challenges a commonly held belief
  - Any "I never told anyone this" or "off the record" energy

Flagged segments enter priority scoring.
Unflagged segments require a final score ≥ 80 to qualify.

═══════════════════════════════════════════
STEP 2 — INTELLIGENT SEGMENTATION & BOUNDARY DETECTION
═══════════════════════════════════════════
Combine transcript entries into coherent conversational segments.

CLIP DURATION POLICY:
- Ideal length: 45–75 seconds
- Preferred range: 50–80 seconds
- Absolute maximum: {max_duration} seconds (NEVER exceed)
- Minimum: {min_duration} seconds
- If a conversational thought naturally ends at 82–88 seconds, allow it.
- If it exceeds {max_duration} seconds, intelligently tighten by:
    - Removing filler
    - Removing redundant phrases  
    - Removing micro-pauses
  BUT never break narrative flow.

HARD RULES — NEVER CUT IN THE MIDDLE OF:
- A sentence
- A punchline
- A key argument
- An emotional beat
- A story arc

BOUNDARY DETECTION RULE:
End a clip ONLY when ALL of the following are true:
- The speaker finishes a complete semantic thought.
- There is either:
    - a pause > 0.6 seconds
    - OR a topic shift
    - OR a reaction from another speaker.
- The emotional or informational arc is resolved.

If the topic continues beyond {max_duration} seconds without a clean break:
- Find the strongest sentence boundary before {max_duration}s.
- Prefer ending on a strong line, not a transition phrase like:
    - "and then..."
    - "but wait..."
    - "so basically..."

QUALITY OVERRIDE RULE:
Editorial coherence is MORE IMPORTANT than hitting an exact timestamp.
Never sacrifice narrative completion for time precision.

Each candidate segment must:
  - End at natural sentence or thought boundaries — never mid-sentence
  - Preserve full narrative coherence (no orphaned context)
  - Not begin with a speaker responding to something the viewer didn't hear
  - Contain full, coherent micro-stories
  - Feel intentionally edited — never feel abruptly cut

Generate 20–40 candidate segments before scoring. Do NOT pre-select. Surface volume first.

For multi-speaker podcasts:
  - Prefer segments where one speaker dominates (cleaner for short-form)
  - Clips featuring genuine pushback or debate between speakers get a +0.5 bonus to Controversy score
  - Avoid segments with heavy crosstalk that would confuse a first-time viewer

═══════════════════════════════════════════
STEP 3 — HOOK ENFORCEMENT
═══════════════════════════════════════════
The opening 3–5 seconds must do at least one of the following:
  - Introduce immediate tension or conflict
  - Spark genuine curiosity with an open loop
  - Deliver a bold, specific, falsifiable claim
  - Create a "wait, what?" moment

If the hook is weak:
  - Shift the start timestamp ±15 seconds to find a stronger entry point
  - Check if a question, reaction, or laugh just before creates better momentum
  - If no strong hook exists within that window — discard the segment entirely

AUTOMATICALLY REJECTED OPENERS (no exceptions):
  "So yeah…" / "Basically…" / "I mean…" / "Right, so…"
  "Um…" / "Like…" / "And so…" / "You know…"
  Any opener that requires prior context to make sense
  Any opener that is a host question rather than a speaker answer

═══════════════════════════════════════════
STEP 4 — MULTI-FACTOR VIRALITY SCORING
═══════════════════════════════════════════
Score each candidate segment across 7 dimensions (1–10 scale):

  Dimension              Weight   Description
  ─────────────────────────────────────────────────────────────────────
  Hook Strength           35%     Bold claim, curiosity gap, controversy, or pattern interrupt in first 5s
  Emotional Intensity     20%     Passion, anger, vulnerability, shock, raw honesty — not performed emotion
  Standalone Clarity      15%     A cold viewer understands it fully with zero prior context
  Value / Insight Density 10%     Actionable advice, framework, or reframeable insight
  Controversy / Tension   10%     Strong opinion, debatable take, counterintuitive claim, or interpersonal friction
  Storytelling Structure   5%     Identifiable arc: setup → tension → payoff
  Retention Curve          5%     Does it build? Is there a reason to stay until the end?

FORMULA:
  Final Score = (0.35 × Hook) + (0.20 × Emotional) + (0.15 × Standalone) 
              + (0.10 × Value) + (0.10 × Controversy) + (0.05 × Story) + (0.05 × Retention)
  
  Normalize result to 0–100.

SCORING BIAS RULES:
  - A technically informative clip with a weak hook will always lose to an emotionally charged clip with a strong hook
  - Vulnerability scores higher than expertise
  - Specificity scores higher than generality ("I lost $2M" beats "I lost a lot of money")
  - If a score feels charitable, round it down — the bar is scroll-stopping, not just good

═══════════════════════════════════════════
STEP 5 — AUTOMATIC REJECTION CRITERIA
═══════════════════════════════════════════
Immediately discard any segment that:
  ✗ Opens with filler language (see Step 3)
  ✗ Is purely descriptive with no tension, stakes, or emotion
  ✗ Requires the viewer to have heard the previous 30+ seconds to understand it
  ✗ Has uniformly low vocal/linguistic energy throughout
  ✗ Is educational but emotionally flat — no heat, no weight
  ✗ Ends without resolution, punchline, realization, or definitive statement
  ✗ Contains excessive repetition or circular reasoning with no payoff
  ✗ Has no single memorable, quotable, or shareable moment
  ✗ Is a host recap or summary of what was just discussed
  ✗ Contains heavy sponsor reads, mid-roll ads, or meta-podcast commentary

═══════════════════════════════════════════
STEP 6 — EMOTIONAL PEAK DETECTION
═══════════════════════════════════════════
Scan each candidate for an identifiable emotional peak — a moment of maximum intensity:
  - Escalating or charged language (word choice becomes more extreme)
  - Personal stakes or vulnerability surfacing
  - Conflict, confrontation, confession, or realization
  - A clear turning point where something shifts

THRESHOLD RULE:
  At least 60% of your final selected clips must contain a detectable emotional peak.
  If your selection falls below this threshold, replace the flattest clips with higher-peak alternatives from your candidate pool.

Tag each clip: emotional_peak_detected: true | false

═══════════════════════════════════════════
STEP 7 — DIVERSITY & CONTRAST ENFORCEMENT
═══════════════════════════════════════════
Before finalizing, audit your selection for redundancy.

HARD RULES:
  - No more than 2 clips may share the same core topic
  - No more than 2 clips may share the same emotional register (e.g., all "inspiring")
  - No more than 1 clip per speaker if this is a multi-host format (unless unavoidable)

REQUIRED VARIETY — your final set must include at least one clip from each category:
  □ High-controversy or polarizing opinion
  □ Emotional story or confession
  □ Bold declarative take (quotable, memeable)
  □ Actionable advice or insight
  □ Unexpected or counterintuitive truth

If raw selections skew toward one type: downgrade the lowest-scoring duplicate, pull the next-ranked clip from an underrepresented category.

═══════════════════════════════════════════
STEP 8 — ENDING STRENGTH ENFORCEMENT
═══════════════════════════════════════════
Every clip must close on one of:
  ✓ A punchline or callback
  ✓ A definitive, quotable takeaway
  ✓ A moment of emotional clarity or realization
  ✓ A statement that lands with full-stop finality
  ✓ A question that re-triggers the viewer's curiosity (cliff-hanger style)

If a clip fades, trails off, or ends mid-thought:
  → Extend the end timestamp to capture the natural close
  → If no strong close exists within a 10-second extension window — reject the clip

═══════════════════════════════════════════
STEP 9 — MANDATORY SELF-CRITIQUE PASS
═══════════════════════════════════════════
Before locking in any clip, answer these 6 questions:

  1. Would I personally watch this to the end if I saw it mid-scroll?
  2. Would I share this without hesitation or explanation?
  3. Does the first sentence create real tension, curiosity, or a strong claim?
  4. Does the last sentence land — does it feel finished?
  5. Would this generate comments, debate, or emotional reactions?
  6. Could this clip stand alone with zero knowledge of the podcast or guest?

If ANY answer is NO → replace the clip with the next-ranked candidate and repeat.
Do not finalize a clip that fails this pass under any circumstances.

═══════════════════════════════════════════
OUTPUT FORMAT — STRICT JSON ONLY
═══════════════════════════════════════════
Return a single JSON object with this exact structure. No markdown. No preamble. No explanation. Only JSON.

{{
  "selected_clips": [
    {{
      "rank": 1,
      "start": 542.2,
      "end": 612.4,
      "duration": 70.2,
      "final_score": 92.4,
      "scores": {{
        "hook": 9,
        "emotional": 8,
        "standalone": 9,
        "value": 9,
        "controversy": 8,
        "storytelling": 7,
        "retention": 9
      }},
      "title_suggestion": "The Brutal Truth About Success Nobody Wants to Hear",
      "hook_text": "Exact opening words of the clip — verbatim from transcript",
      "closing_text": "Exact closing words of the clip — verbatim from transcript",
      "emotional_peak_detected": true,
      "emotional_peak_timestamp": 578.5,
      "primary_virality_type": "confession | story | opinion | controversy | advice | insight",
      "platform_fit": ["TikTok", "Reels", "Shorts"],
      "suggested_caption": "One punchy, platform-native caption under 100 characters",
      "reason": "2–3 sentence explanation of why this clip is unmissable.",
      "rejection_reason": null
    }}
  ],
  "scan_summary": {{
    "total_candidates_evaluated": 28,
    "segments_rejected": 21,
    "flagged_virality_patterns": ["confession at 312s", "polarizing opinion at 542s"],
    "diversity_check_passed": true,
    "emotional_peak_coverage": "5 of 7 clips (71%)"
  }}
}}

═══════════════════════════════════════════
CRITICAL REQUIREMENTS
═══════════════════════════════════════════
- Return EXACTLY {clip_count} clips. A short list is a failure.
- All timestamps must be raw float seconds — never HH:MM:SS format.
- Selected clips must NOT overlap with each other (start/end ranges must be mutually exclusive).
- Every podcast has short-form potential — your job is to find it, not to decide it doesn't exist.
- hook_text and closing_text must be verbatim transcript quotes, not paraphrases.
- emotional_peak_timestamp must fall within the clip's start–end range.
- If {clip_count} strong clips cannot be found, select the best available and note weaknesses in the reason field — never return an empty or short list.

═══════════════════════════════════════════
OPERATING PRINCIPLES
═══════════════════════════════════════════
  What weak systems do                    What you do
  ──────────────────────────────────────────────────────────────────
  Score all content evenly                Bias aggressively toward hook + emotion
  Treat advice the same as story          Weight vulnerability and tension above information
  Ignore hook quality                     Reject or recut weak openers without mercy
  Accept soft endings                     Extend or discard clips that fade
  Skip self-review                        Critique every clip before locking it in
  Return whatever is generated            Enforce diversity, peak detection, ending strength
  Ignore platform context                 Tag each clip for its best-fit platform
  Miss the emotional peak moment          Pinpoint its exact timestamp

You are not hunting for content that's good. Good gets scrolled past. Good gets forgotten. You are hunting for content that hijacks attention, triggers a physical reaction, and makes a stranger stop, stare, and share — without knowing why they can't look away."""


class AIClipScoringService:
    """Orchestrates the LLM-based clip selection pipeline using the unified LLM service."""

    def __init__(self):
        self.llm = get_llm_service()

    def analyze_transcript(
        self,
        transcript: List[Dict[str, Any]],
        video_title: str = "",
        clip_count: int = None,
        min_duration: int = None,
        max_duration: int = None,
        client_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Analyze a timestamped transcript and return scored clip candidates.
        Returns list of clip dicts with start, end, score, reason, etc.
        All limits come from Settings (driven by .env).
        """
        _clip_count = clip_count if clip_count is not None else settings.DEFAULT_CLIP_COUNT
        _min_duration = min_duration if min_duration is not None else settings.MIN_CLIP_DURATION
        _max_duration = max_duration if max_duration is not None else settings.MAX_CLIP_DURATION

        # Fetch DNA from Nexearch
        dna_injection = ""
        try:
            nexearch_url = "http://localhost:8002/api/v1/intelligence"
            target_url = f"{nexearch_url}/client/{client_id}" if client_id else f"{nexearch_url}/universal"
            
            # Use synchronous httpx block since this might be running in a sync Celery task
            with httpx.Client(timeout=10.0) as client:
                res = client.get(target_url)
                if res.status_code == 200:
                    dna_data = res.json()
                    
                    # Format DNA string
                    dna_injection = "═══════════════════════════════════════════\\n"
                    dna_injection += f"CLIENT SPECIFIC DNA INSTRUCTIONS ({dna_data.get('client_id', 'UNIVERSAL')})\\n"
                    dna_injection += "═══════════════════════════════════════════\\n"
                    dna_injection += f"TONE: {dna_data.get('tone', 'Not specified')}\\n"
                    dna_injection += f"TOPICS TO AVOID: {', '.join(dna_data.get('topics_to_avoid', [])) or 'None'}\\n"
                    dna_injection += "\\nBEST HOOKS TO LOOK FOR:\\n"
                    for hook in dna_data.get('best_hooks', []):
                        dna_injection += f"- {hook}\\n"
                    dna_injection += "\\nFailure to strictly adhere to these specific DNA rules will result in immediate rejection.\\n"
                    
                    logger.info(f"Successfully injected DNA rules for {client_id or 'Universal'}")
                else:
                    logger.warning(f"Failed to fetch DNA rules. Status code: {res.status_code}")
        except Exception as e:
            logger.warning(f"Could not connect to Nexearch to fetch DNA. Running without specific instructions. Error: {e}")

        # Build the system prompt with parameters
        system_prompt = CLIP_SELECTION_SYSTEM_PROMPT.format(
            clip_count=_clip_count,
            min_duration=_min_duration,
            max_duration=_max_duration,
            dna_injection=dna_injection,
        )

        user_message = json.dumps({
            "video_metadata": {
                "title": video_title,
                "duration_seconds": transcript[-1]["end"] if transcript else 0,
            },
            "transcript": transcript,
        }, ensure_ascii=False)

        # Truncate if too long (limit from settings)
        max_length = settings.LLM_MAX_TRANSCRIPT_LENGTH
        if len(user_message) > max_length:
            logger.warning(f"Transcript too long ({len(user_message)} chars), truncating to {max_length}")
            user_message = user_message[:max_length] + "\n... [TRUNCATED]"

        logger.info(f"Sending transcript for analysis ({len(transcript)} segments, {len(user_message)} chars)")

        try:
            # Use the unified LLM service (handles fallback chain)
            raw_content = self.llm.generate(
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                timeout=settings.LLM_TIMEOUT,
            )

            # Debug: save raw LLM response for inspection
            logger.info(f"Raw LLM response length: {len(raw_content)} chars")
            try:
                with open("ai_response_debug.log", "w", encoding="utf-8") as f:
                    f.write(raw_content or "<empty response>")
            except Exception:
                pass

            # Robust JSON extraction
            result = self.llm.extract_json(raw_content)
            clips = result.get("selected_clips", [])
            logger.info(f"Parsed {len(clips)} clips from LLM response")

            # Validate and clean
            validated_clips = self._validate_clips(clips, _clip_count, _min_duration, _max_duration)

            logger.info(f"AI analysis complete: {len(validated_clips)} clips after validation (from {len(clips)} raw)")

            # Fallback: if LLM returned 0 valid clips, generate time-based segments
            if len(validated_clips) == 0 and len(transcript) > 0:
                logger.warning("LLM returned 0 valid clips — using time-based fallback")
                validated_clips = self._generate_fallback_clips(
                    transcript, _clip_count, _min_duration, _max_duration
                )
                logger.info(f"Fallback generated {len(validated_clips)} clips")

            return validated_clips

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            raise RuntimeError(f"AI returned invalid JSON: {e}")
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            raise

    def _format_transcript(self, transcript: List[Dict]) -> str:
        """Format transcript for readable LLM input."""
        lines = []
        for seg in transcript:
            start = self._format_time(seg["start"])
            end = self._format_time(seg["end"])
            lines.append(f"[{start} → {end}] {seg['text']}")
        return "\n".join(lines)

    def _format_time(self, seconds: float) -> str:
        """Convert seconds to HH:MM:SS format."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _validate_clips(
        self,
        clips: List[Dict],
        clip_count: int,
        min_duration: int,
        max_duration: int,
    ) -> List[Dict[str, Any]]:
        """Validate, filter overlaps, and rank clips."""
        validated = []
        for clip in clips:
            try:
                start = float(clip.get("start", 0))
                end = float(clip.get("end", 0))
                duration = end - start

                if duration < 5 or duration > max_duration * 2.0:
                    logger.warning(f"Clip rejected: duration={duration:.1f}s outside [5-{max_duration*2.0}]s — start={start}, end={end}")
                    continue

                validated.append({
                    "rank": int(clip.get("rank", len(validated) + 1)),
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "duration": round(duration, 2),
                    "final_score": round(float(clip.get("final_score", 0)), 1),
                    "scores": clip.get("scores", {}),
                    "title_suggestion": str(clip.get("title_suggestion", "")),
                    "hook_text": str(clip.get("hook_text", "")),
                    "reason": str(clip.get("reason", "")),
                    "emotional_peak_detected": bool(clip.get("emotional_peak_detected", False)),
                    "primary_virality_type": str(clip.get("primary_virality_type", "")),
                })
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid clip: {e} — data: {clip}")
                continue

        logger.info(f"Validation: {len(validated)} clips passed from {len(clips)} raw (min_dur={min_duration}, max_dur={max_duration})")
        if len(validated) < len(clips):
            logger.warning(f"Dropped {len(clips) - len(validated)} clips during validation")

        # Remove overlapping clips (keep higher scored)
        validated.sort(key=lambda c: c["final_score"], reverse=True)
        non_overlapping = []
        for clip in validated:
            if not any(self._overlaps(clip, selected) for selected in non_overlapping):
                non_overlapping.append(clip)

        # Trim to requested count and re-rank
        final = non_overlapping[:clip_count]
        final.sort(key=lambda c: c["final_score"], reverse=True)
        for i, clip in enumerate(final):
            clip["rank"] = i + 1

        return final

    def _generate_fallback_clips(
        self,
        transcript: List[Dict],
        clip_count: int,
        min_duration: int,
        max_duration: int,
    ) -> List[Dict[str, Any]]:
        """
        Generate clips by evenly spacing through the transcript.
        Used as fallback when the LLM returns 0 clips.
        """
        if not transcript:
            return []

        total_duration = transcript[-1]["end"]
        target_duration = min(max_duration, max(min_duration, 60))  # aim for 60s clips

        # Calculate how many clips we can fit
        actual_count = min(clip_count, max(1, int(total_duration / target_duration)))
        segment_length = total_duration / actual_count

        clips = []
        for i in range(actual_count):
            start = round(i * segment_length, 2)
            end = round(min(start + target_duration, total_duration), 2)
            duration = round(end - start, 2)

            if duration < 10:  # skip very short segments
                continue

            # Find the text for this segment
            segment_text = " ".join(
                s["text"] for s in transcript
                if s["start"] >= start and s["end"] <= end
            )
            first_sentence = segment_text[:100].strip() + "..." if segment_text else ""

            clips.append({
                "rank": i + 1,
                "start": start,
                "end": end,
                "duration": duration,
                "final_score": round(50 - i * 2, 1),  # decreasing scores
                "scores": {
                    "hook": 5, "emotional": 5, "standalone": 5,
                    "value": 5, "controversy": 5, "storytelling": 5, "retention": 5,
                },
                "title_suggestion": f"Clip {i + 1}",
                "hook_text": first_sentence,
                "reason": "Auto-generated segment (AI fallback)",
                "emotional_peak_detected": False,
                "primary_virality_type": "insight",
            })

        return clips

    def _overlaps(self, a: Dict, b: Dict) -> bool:
        """Check if two clips overlap."""
        return a["start"] < b["end"] and b["start"] < a["end"]
