import re
from typing import Tuple

class IntentClassifier:
    """
    Classifies user messages to determine the appropriate response strategy,
    especially useful for short-circuiting heavy system checks on simple greetings.
    """
    
    # Common greetings that don't need a full system status dump
    GREETING_PATTERNS = [
        r"^(hi|hello|hey|yo|greetings)( nex)?\b",
        r"good (morning|afternoon|evening|night)",
        r"^i am [\w\s]+$",
        r"^my name is [\w\s]+$"
    ]
    
    def classify(self, user_message: str) -> Tuple[str, bool]:
        """
        Classifies the message.
        Returns (intent_type, should_skip_tools).
        
        intent_type can be: 'greeting', 'status_request', 'action_request', 'unknown'
        """
        msg = user_message.lower().strip()
        
        # Check for simple greetings
        for pattern in self.GREETING_PATTERNS:
            if re.search(pattern, msg):
                # If they say something like "hi, is it running?", it's an action/status request, not just a greeting
                if len(msg.split()) <= 4 and 'status' not in msg and 'running' not in msg:
                    return 'greeting', True
        
        if any(word in msg for word in ['status', 'health', 'running?', 'working?']):
            return 'status_request', False
            
        if any(word in msg for word in ['start', 'stop', 'restart', 'create', 'run']):
            return 'action_request', False
            
        return 'unknown', False
    
    def get_greeting_prompt_override(self, original_user_message: str) -> str:
        """
        Creates a constrained system prompt for greetings to force a casual, brief response.
        Extra strict to prevent reasoning models from echoing their thought process.
        """
        return (
            "You are Nex, the AI agent of NexClip. "
            f"The user said: \"{original_user_message}\"\n\n"
            "RULES — FOLLOW THESE EXACTLY:\n"
            "1. Reply with ONE short sentence greeting them back.\n"
            "2. DO NOT output any reasoning steps, chain of thought, or thinking process.\n"
            "3. DO NOT echo the words UNDERSTAND, PLAN, EXECUTE, VERIFY, REPORT.\n"
            "4. DO NOT mention system status, services, or any technical information.\n"
            "5. DO NOT use bullet points or lists.\n"
            "6. DO NOT prefix your response with 'system' or any XML tags.\n"
            "7. Just say hello naturally in 1-2 sentences maximum.\n\n"
            "Example good responses:\n"
            "- \"Hey Ved! What can I do for you?\"\n"
            "- \"Welcome back, Ved. What needs my attention?\"\n"
        )
