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
    # few-shot / system prompt structure back verbatim.
    # Source: direct observation from UI screenshots.
    _LEAKED_PROMPT_LINE_PREFIXES: Tuple[str, ...] = (
        # ── User message echoes ──────────────────────────
        "User says:",
        "User said:",
        "User input:",
        "User identity:",
        "User message:",
        "User query:",
        "User request:",
        # ── Persona / identity labels ────────────────────
        "Persona:",
        "Persona guidelines:",
        "Identity:",
        "Role:",
        "Agent role:",
        "My role:",
        # ── Style / tone labels ──────────────────────────
        "Style:",
        "Tone:",
        "Voice:",
        "Format:",
        # ── Context / situation labels ───────────────────
        "Context:",
        "Current situation:",
        "Situation:",
        "Background:",
        # ── Instruction / rule labels ────────────────────
        "Instruction:",
        "Instructions:",
        "Constraint:",
        "Constraints:",
        "Greeting rule:",
        "Greeting:",
        "Rule:",
        "RULES —",
        "RULES:",
        "QUALITY OVER QUANTITY",
        "Call to action:",
        "Acknowledge",
        # ── Draft / example labels ───────────────────────
        "Draft 1",
        "Draft 2",
        "Draft 3",
        "Draft 4",
        "Draft 5",
        "Example good responses:",
        "Example responses:",
        "Example:",
        "Response option",
        "Option 1",
        "Option 2",
        "Option 3",
        # ── Reasoning / action labels ────────────────────
        "Action:",
        "Action plan:",
        "Plan:",
        "Decision:",
        "Output:",
        "Execution:",
        "Coordinate:",
        "Identify the ",
        "Determine the ",
        "Client Lookup:",
        "Method Selection:",
        "Asset Handoff:",
        "Arc Execution:",
        # ── Old patterns ─────────────────────────────────
        "Natural hello,",
        "No reasoning",
        "No keywords",
        "No technical",
        "No lists",
        "No prefixes",
        "One short sentence",
        "Just say hello",
        # ── Arc-specific labels seen in screenshots ──────
        "I should acknowledge",
        "I need to maintain",
        "Since Ved is",
        "Since the user is",
        "The user is addressing",
        "The user is greeting",
        "The user is not",
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

    def extract_thinking_and_clean(self, raw_text: str) -> tuple:
        """
        Separate LLM output into (thinking_content, clean_answer).

        Returns a 2-tuple:
          - thinking_content: everything that looks like internal reasoning
            / leaked prompt structure (may be empty string)
          - clean_answer: the actual user-facing response

        Uses a 3-pass strategy:
          Pass 1 — Strip <think>...</think> XML blocks.
          Pass 2 — Detect and pull out leaked prompt structure blocks
                    (labeled fields like 'User says:', 'Persona:', etc.)
                    AND their continuation lines (reasoning prose that
                    follows directly after a matched label block).
          Pass 3 — Strip standalone reasoning keyword lines
                    (PLAN:, UNDERSTAND:, EXECUTE:, etc.)

        Safety — if stripping leaves nothing, returns the raw text as the
        clean answer so we never show a blank message.
        """
        if not raw_text or not raw_text.strip():
            return "", raw_text

        thinking_parts: list = []

        # ─── Pass 1: Extract explicit <think>...</think> XML blocks ──
        think_matches = re.findall(
            r"<think>(.*?)</think>", raw_text, re.DOTALL | re.IGNORECASE
        )
        for match in think_matches:
            thinking_parts.append(match.strip())
        remaining = re.sub(
            r"<think>.*?</think>", "", raw_text, flags=re.DOTALL | re.IGNORECASE
        ).strip()

        # ─── Pass 2: Leaked prompt-structure + continuation lines ────
        #
        # State machine:
        #   CLEAN   – normal content
        #   LEAKED  – inside a labeled block (User says:, Persona:, ...)
        #   REASON  – continuation prose after a labeled block
        #             ("The user is greeting me.", "I should acknowledge..")
        #
        # Continuation prose starters (follow a leaked block):
        _CONTINUATION_STARTERS: Tuple[str, ...] = (
            "The user is", "The user has", "The user said",
            "I should", "I need to", "I am going to", "I will",
            "I must", "I want to",
            "Since ", "Since the", "Since Ved",
            "Let me", "Let's",
            "My response", "My goal", "My plan",
            "For this", "In this case", "In order to",
            "To respond", "To answer",
            "Based on", "Given that", "Given the",
        )

        STATE_CLEAN  = "clean"
        STATE_LEAKED = "leaked"
        STATE_REASON = "reason"

        lines = remaining.split("\n")
        leaked_block: list = []
        clean_lines: list  = []
        state = STATE_CLEAN

        for line in lines:
            stripped = line.strip()

            if state == STATE_CLEAN:
                # Does this line start a leaked block?
                if any(stripped.startswith(p) for p in self._LEAKED_PROMPT_LINE_PREFIXES):
                    state = STATE_LEAKED
                    leaked_block.append(line)
                else:
                    clean_lines.append(line)

            elif state == STATE_LEAKED:
                if not stripped:
                    leaked_block.append(line)  # blank inside block
                elif any(stripped.startswith(p) for p in self._LEAKED_PROMPT_LINE_PREFIXES):
                    leaked_block.append(line)  # another labeled line
                elif re.match(r'^["\u201c\u2018]', stripped):
                    # Quoted example line — still part of leaked block
                    leaked_block.append(line)
                elif any(stripped.startswith(c) for c in _CONTINUATION_STARTERS):
                    state = STATE_REASON
                    leaked_block.append(line)  # continuation is also thinking
                elif re.match(r'^Draft \d', stripped, re.IGNORECASE):
                    leaked_block.append(line)
                else:
                    # First non-matching, non-blank line → clean answer
                    state = STATE_CLEAN
                    clean_lines.append(line)

            elif state == STATE_REASON:
                if not stripped:
                    leaked_block.append(line)
                elif any(stripped.startswith(p) for p in self._LEAKED_PROMPT_LINE_PREFIXES):
                    state = STATE_LEAKED
                    leaked_block.append(line)
                elif any(stripped.startswith(c) for c in _CONTINUATION_STARTERS):
                    leaked_block.append(line)
                elif re.match(r'^["\u201c\u2018]', stripped):
                    leaked_block.append(line)
                else:
                    # End of reasoning prose — treat rest as clean
                    state = STATE_CLEAN
                    clean_lines.append(line)

        if leaked_block:
            thinking_parts.append("\n".join(leaked_block).strip())

        remaining = "\n".join(clean_lines).strip()

        # ─── Pass 3: Reasoning keyword echo lines ────────────────────
        kw_lines: list   = []
        final_lines: list = []
        in_kw_block = False
        for line in remaining.split("\n"):
            stripped = line.strip()
            if any(stripped.startswith(kw) for kw in self.REASONING_KEYWORDS):
                in_kw_block = True
                kw_lines.append(line)
            elif in_kw_block and stripped:
                in_kw_block = False
                final_lines.append(line)
            elif in_kw_block:
                kw_lines.append(line)
            else:
                final_lines.append(line)
        if kw_lines:
            thinking_parts.append("\n".join(kw_lines).strip())
        clean = "\n".join(final_lines).strip()

        # ─── Strip leading Nex:/Arc: role prefix ─────────────────────
        clean = re.sub(r"^\s*(Nex|Arc):\s*", "", clean, flags=re.IGNORECASE)

        # ─── Safety: never return an empty clean answer ───────────────
        if not clean:
            return "", raw_text

        thinking_str = "\n\n".join(t for t in thinking_parts if t)
        return thinking_str, clean

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
