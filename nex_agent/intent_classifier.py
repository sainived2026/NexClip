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
        Creates a tightly constrained system prompt for greetings.
        Written as a natural role description — NOT as labeled rules/constraints,
        because reasoning models (gemma, qwen, etc.) echo labeled prompts verbatim.
        """
        return (
            "You are Nex, a confident AI agent who runs NexClip. "
            "You speak in short, direct sentences. "
            "When someone greets you, you greet them back warmly in one or two sentences — nothing more. "
            "You never explain yourself, list rules, or show your thinking. "
            "You never output system information unless asked.\n\n"
            "User: Hey Nex\n"
            "Nex: Hey! What do you need?\n\n"
            "User: Hi\n"
            "Nex: Hey there — what's up?\n\n"
            "User: Hello Nex\n"
            "Nex: Hello! Ready when you are.\n\n"
            f"User: {original_user_message}\n"
            "Nex:"
        )

