import re
import json
from typing import Tuple, List, Dict, Any, Optional

class ToolCallInterceptor:
    """
    Intercepts tool call patterns in LLM output regardless of format.
    Local models often output tool calls as plain text JSON.
    This layer catches all formats before they reach the frontend.
    """
    
    # Patterns that indicate a tool call embedded in text
    TOOL_CALL_PATTERNS = [
        # JSON object with "name" and "arguments" keys
        r'\{[\s]*"name"[\s]*:[\s]*"[^"]+"[\s]*,[\s]*"arguments"[\s]*:[^}]+\}',
        r'\{[\s]*\'name\'[\s]*:[\s]*\'[^\']+\'[\s]*,[\s]*\'arguments\'[\s]*:[^}]+\}',
        
        # XML-style tool calls some models use
        r'<tool_call>.*?</tool_call>',
        
        # Function call syntax
        r'<function_calls>.*?</function_calls>',
        
        # Backtick-wrapped JSON tool calls
        r'```(?:json|tool_call)?\n?[\s]*\{[^`]+\}[\s]*\n?```',
    ]
    
    def extract_and_strip_tool_calls(self, content: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Extract all tool call patterns from content.
        Returns (clean_content, list_of_tool_calls).
        The clean_content has all tool call JSON removed.
        """
        if not content:
            return "", []
            
        tool_calls = []
        clean_content = content
        
        for pattern in self.TOOL_CALL_PATTERNS:
            # re.DOTALL makes . match newlines too
            matches = re.findall(pattern, clean_content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    # Try to parse as a tool call
                    parsed = self._parse_tool_call(match)
                    if parsed:
                        tool_calls.append(parsed)
                        # Remove from content - replace exactly that match
                        clean_content = clean_content.replace(match, '', 1)
                except Exception:
                    pass  # Not a valid tool call, leave it
        
        # Clean up artifacts left by removal (extra newlines/spaces)
        clean_content = re.sub(r'\n{3,}', '\n\n', clean_content).strip()
        
        return clean_content, tool_calls
    
    def _parse_tool_call(self, raw: str) -> Optional[Dict[str, Any]]:
        """Parse a raw tool call string into a structured dict."""
        # Strip backticks and whitespace
        raw = re.sub(r'```(?:json|tool_call)?', '', raw, flags=re.IGNORECASE).strip('`').strip()
        
        # Strip XML tags
        raw = re.sub(r'</?tool_call>', '', raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r'</?function_calls>', '', raw, flags=re.IGNORECASE).strip()
        
        # Some models use single quotes for JSON (which is invalid JSON, but common for LLMs)
        raw = raw.replace("'", '"')
        
        try:
            data = json.loads(raw)
            if 'name' in data:
                args = data.get('arguments', data.get('parameters', {}))
                
                # If arguments is a string (often double-encoded by local LLMs), try to parse it
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        pass
                
                return {
                    'name': data['name'],
                    'arguments': args if isinstance(args, dict) else {}
                }
        except json.JSONDecodeError:
            return None
        
        return None
    
    def is_streaming_tool_call(self, token_buffer: str) -> bool:
        """
        Called during streaming to detect if we're accumulating a tool call.
        Returns True if the buffer looks like it's building up a tool call.
        Prevents partial tool call JSON from being sent to frontend.
        """
        stripped = token_buffer.strip()
        if not stripped:
            return False
            
        # Check if buffer starts with tool call markers
        tool_call_starters = [
            '{"name":', '{"name" :', '{"name":', "{ 'name':", "{'name':",
            '<tool_call>', '<function_calls>',
            '```json\n{', '```\n{'
        ]
        
        # We also need to catch the fallback output logic where models just output [ {"name"...
        if stripped.startswith('[') and ('"' in stripped or "'" in stripped):
            if '"name"' in stripped or "'name'" in stripped:
                return True
        
        return any(stripped.startswith(marker) for marker in tool_call_starters)
        
    def format_tool_result_for_display(self, tool_name: str, result_data: Dict[str, Any]) -> str:
        """
        Format tool results as human-readable markdown.
        Never raw JSON in the chat.
        """
        success = result_data.get('success', False)
        error = result_data.get('error', 'Unknown error')
        
        if not success:
            return f"\n\n> ⚠️ **{tool_name} failed:** {error}\n\n"
            
        # Generic graceful execution marker
        return f"\n\n> ⚙️ **Executed system tool:** `{tool_name}`\n\n"
