import re
from typing import Any, Dict, List, Tuple


class ResponseValidator:
    """
    Validates LLM responses — strips thinking/reasoning tokens and
    catches hallucinations before the text reaches the user.

    Key capability added: raw-prose thinking paragraph stripper.
    Gemini and some OpenRouter reasoning models emit their internal
    chain-of-thought as plain paragraphs that start with phrases like
    "I need to...", "The user is asking...", "Wait,", "Actually,"
    BEFORE writing the actual clean answer. This class detects and
    strips those leading paragraph blocks, leaving only the real reply.
    """

    # ── Hallucination patterns ────────────────────────────────────
    HALLUCINATION_PATTERNS = [
        r"database is running on port 5432",
        r"PostgreSQL.*running",
        r"All systems are (green|operational|running)",
        r"CPU usage is.*%",
        r"Memory usage is.*%",
    ]

    # ── Reasoning-framework keyword echoes ────────────────────────
    REASONING_KEYWORDS = [
        "UNDERSTAND:", "PLAN:", "EXECUTE:", "VERIFY:", "REPORT:",
        "FOLLOW THROUGH:", "FOLLOW-THROUGH:", "ANALYSIS:", "REASONING:",
        "THOUGHT:", "THINKING:", "OBSERVATION:", "ACTION:", "REFLECTION:",
    ]

    # ── Leaked prompt-structure line prefixes ─────────────────────
    # These are labels that appear when a reasoning model echoes the
    # few-shot prompt structure back verbatim (seen in screenshot).
    _LEAKED_PROMPT_LINE_PREFIXES: Tuple[str, ...] = (
        "User input:",
        "User said:",
        "Role:",
        "Constraints:",
        "RULES —",
        "RULES:",
        "Example good responses:",
        "Example responses:",
        "Natural hello,",
        "No reasoning",
        "No keywords",
        "No technical",
        "No lists",
        "No prefixes",
        "One short sentence",
        "Just say hello",
    )

    # ── Raw-prose thinking sentence starters ──────────────────────
    # If a paragraph's opening text matches any of these, the paragraph is
    # treated as internal chain-of-thought and silently dropped.
    _THINKING_STARTERS: Tuple[str, ...] = (
        "The user is asking",
        "The user wants",
        "The user asked",
        "The user has asked",
        "I need to inform",
        "I need to explain",
        "I need to think",
        "I need to check",
        "I need to figure",
        "I need to call",
        "I need to determine",
        "I need to identify",
        "I need to understand",
        "I need to",
        "I am thinking",
        "I should think",
        "I should first",
        "I should check",
        "I should call",
        "I should inform",
        "I should consider",
        "I should note",
        "I should make",
        "I should explain",
        "I should let",
        "I should be",
        "I should",
        "I can see",
        "I can note",
        "I think",
        "Let me think",
        "Let me check",
        "Let me analyze",
        "Let me consider",
        "Let me figure",
        "Let me look",
        "Let me break",
        "Let me re-read",
        "Let me",
        "Wait,",
        "Wait —",
        "Actually,",
        "Actually —",
        "But wait,",
        "But actually,",
        "Hmm,",
        "Hmm —",
        "OK so",
        "OK, ",
        "Okay,",
        "So I ",
        "So the ",
        "So, ",
        "Right,",
        "Now, ",
        "Now I ",
        "First, ",
        "First I ",
        "Since I am",
        "Since I'm",
        "Since the",
        "For this specific",
        "For this case",
        "Based on",
        "Looking at the",
        "Looking at",
        "Thinking about",
        "Reviewing",
        "Checking",
        "Given that",
        "Given the",
        "In this case",
        "In order to",
        "To do this",
        "To answer this",
        "To handle this",
        "To respond to",
        "The pipeline",
        "The tool output",
        "The prompt",
        "The context",
        "The user's request",
        "The request",
        "My response",
        "My plan",
        "My approach",
        # Screenshot-specific patterns seen in the UI
        "Identify the Client",
        "Identify the ",
        "Determine the Method",
        "Coordinate with Arc Agent",
        "Client Lookup:",
        "Method Selection:",
        "Asset Handoff:",
        "Arc Execution:",
        "Execution:",
        "Coordinate:",
        "I'll be one",
        "I'll just tell",
        "Instead, I will",
        "Instead, I'll",
    )

    # ─────────────────────────────────────────────────────────────

    def validate_and_fix(
        self,
        response_text: str,
        recent_tools: List[str] = None,
    ) -> Tuple[bool, str]:
        """
        Validates the text and returns (is_valid, cleaned_text).
        Always strips thinking tokens first.
        """
        if not response_text:
            return True, response_text

        # Step 0: Strip all thinking/reasoning content first
        cleaned = self.strip_thinking_tokens(response_text)
        was_cleaned = cleaned != response_text
        response_text = cleaned

        if not response_text.strip():
            return False, "Hey! How can I help you today?"

        recent = recent_tools or []
        has_status_data = any("status" in t or "health" in t for t in recent)

        # Strip hallucinated PostgreSQL/port references when no DB tool was used
        if not any("db" in t for t in recent):
            clean_text = self._strip_hallucinated_bullet_points(response_text, "PostgreSQL")
            clean_text = self._strip_hallucinated_bullet_points(clean_text, "port 5432")
            if clean_text != response_text:
                return False, clean_text

        # Strip fake Markdown metrics tables
        if "| Metric | Value |" in response_text and not has_status_data:
            clean_text = re.sub(
                r"\|.*\|.*\n\|.*[-]+.*[-]+.*\|(\n\|.*\|.*)+\n?",
                "\n*(Metrics hidden pending tool verification)*\n",
                response_text,
            )
            return False, clean_text

        return (not was_cleaned), response_text

    # ─────────────────────────────────────────────────────────────

    def strip_thinking_tokens(self, text: str) -> str:
        """
        Strips ALL internal reasoning content from model output.

        Handles five distinct patterns:

        1. <think>...</think> XML blocks       (Qwen3, DeepSeek-R1, some OpenRouter)
        2. <|thinking|>...</|thinking|> tokens  (variant format)
        3. Reasoning keyword echo lines         (PLAN:, UNDERSTAND:, EXECUTE: …)
        4. Raw-prose thinking paragraph blocks  (Gemini/OpenRouter CoT paragraphs)
        5. Leaked prompt-structure blocks       (gemma echoing User input:/Role:/Constraints:)
        """
        if not text:
            return text

        # 0. Strip leaked prompt structure FIRST (catches gemma-style echoed prompts)
        text = self._strip_leaked_prompt_structure(text)

        # 1. <think>…</think>
        text = re.sub(
            r"<think>.*?</think>",
            "",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # 2. <|thinking|>…</|thinking|>
        text = re.sub(
            r"<\|thinking\|>.*?<\|/thinking\|>",
            "",
            text,
            flags=re.DOTALL,
        )

        # 3. Reasoning keyword echo lines
        text = self._strip_keyword_block_lines(text)

        # 4. Raw-prose thinking paragraphs
        text = self._strip_raw_thinking_paragraphs(text)

        # 5. Strip leading 'Nex:' prefix (from few-shot prompt tail)
        text = re.sub(r"^\s*Nex:\s*", "", text, flags=re.IGNORECASE)

        # Tidy up extra blank lines left by stripping
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    # ─────────────────────────────────────────────────────────────

    def _strip_leaked_prompt_structure(self, text: str) -> str:
        """
        Removes blocks where the model echoed the system-prompt structure.
        Detects ANY line starting with a known leaked-prompt prefix and drops
        ALL consecutive lines that are part of that block.

        Also handles the specific pattern seen in the screenshot where the
        model outputs:
            User input: "..."
            Role: ...
            Constraints:
            ...
            <actual answer>
        We find the last quoted string in the block and return only that.
        """
        lines = text.split("\n")

        # Quick check — if none of the known prefixes appear, skip expensive work
        joined_lower = "\n".join(lines[:20]).lower()
        has_leak = any(
            p.lower() in joined_lower for p in self._LEAKED_PROMPT_LINE_PREFIXES
        )
        if not has_leak:
            return text

        # Walk lines, stripping any that start with a known leaked-prompt prefix
        # OR that are part of a numbered/bulleted list in such a block.
        clean: List[str] = []
        in_leaked_block = False
        for line in lines:
            stripped = line.strip()
            if any(stripped.startswith(p) for p in self._LEAKED_PROMPT_LINE_PREFIXES):
                in_leaked_block = True
                continue
            # Numbered rules or dash-quoted examples inside a leaked block
            if in_leaked_block and re.match(r'^(\d+\.|-|\*)\s', stripped):
                continue
            # Exit leaked block on first blank line or real content
            if in_leaked_block:
                if not stripped:
                    continue  # skip blank lines inside the block
                else:
                    in_leaked_block = False  # real content follows
            clean.append(line)

        result = "\n".join(clean).strip()

        # If the whole text was wiped, try extracting the last quoted string
        # (which is usually the actual intended response in few-shot prompts)
        if not result and text:
            quoted = re.findall(r'"([^"]{5,200})"', text)
            if quoted:
                return quoted[-1].strip()

        return result

    def _strip_keyword_block_lines(self, text: str) -> str:
        """
        Removes lines that start with recognised reasoning-framework keywords
        such as PLAN:, UNDERSTAND:, EXECUTE:, etc.
        """
        lines = text.split("\n")
        clean_lines: List[str] = []
        in_block = False

        for line in lines:
            stripped = line.strip()

            if any(stripped.startswith(kw) for kw in self.REASONING_KEYWORDS):
                in_block = True
                continue

            if stripped.lower() == "system":
                in_block = True
                continue

            # Reset block flag when we hit real content
            if in_block and stripped and not any(
                stripped.startswith(kw) for kw in self.REASONING_KEYWORDS
            ):
                in_block = False

            if not in_block:
                clean_lines.append(line)

        return "\n".join(clean_lines)

    def _strip_raw_thinking_paragraphs(self, text: str) -> str:
        """
        Splits the text into paragraphs and drops any LEADING run of paragraphs
        that look like internal chain-of-thought reasoning.

        We stop stripping as soon as we encounter the first paragraph whose
        opening does NOT match a thinking-sentence starter — that is treated as
        the beginning of the real user-facing answer, and everything from there
        onwards is preserved verbatim.

        Edge case: if the ENTIRE text looks like reasoning (single-paragraph
        response or all paragraphs stripped), the last paragraph is returned
        unchanged so the user always gets *something*.
        """
        paragraphs = re.split(r"\n{2,}", text.strip())

        # Nothing to do for a single-paragraph response — leave it alone
        if len(paragraphs) <= 1:
            return text

        result: List[str] = []
        stripping = True  # We start by dropping leading thinking paragraphs

        for para in paragraphs:
            trimmed = para.strip()
            if not trimmed:
                if not stripping:
                    result.append(para)
                continue

            if stripping:
                if self._is_thinking_paragraph(trimmed):
                    continue        # Silently drop this internal-reasoning block
                else:
                    stripping = False
                    result.append(para)   # First real-content paragraph → keep
            else:
                result.append(para)   # We are past the thinking block → keep all

        # Safety: if everything was stripped, fall back to the last paragraph
        if not result and paragraphs:
            return paragraphs[-1].strip()

        return "\n\n".join(result)

    def _is_thinking_paragraph(self, paragraph: str) -> bool:
        """
        Returns True if the start of the paragraph matches a known
        internal-reasoning sentence opener.
        We only inspect the first 250 characters to keep this fast.
        """
        first = paragraph[:250].lstrip()
        for starter in self._THINKING_STARTERS:
            if first.startswith(starter):
                return True
        return False

    def _strip_hallucinated_bullet_points(self, text: str, keyword: str) -> str:
        """Removes bullet/numbered list items that contain a hallucinated keyword."""
        lines = text.split("\n")
        clean = [
            line
            for line in lines
            if keyword.lower() not in line.lower()
            or not (
                line.strip().startswith("-")
                or line.strip().startswith("*")
                or re.match(r"^\d+\.", line.strip())
            )
        ]
        return "\n".join(clean)
