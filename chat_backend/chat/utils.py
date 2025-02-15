# chat/utils.py
import re
from typing import Dict, Optional

class ChatbotResponder:
    @staticmethod
    def get_predefined_responses() -> Dict[str, str]:
        return {
            r'hello|hi|hey': 'Hello! How can I help you today?',
            r'how are you': 'I am doing well, thank you for asking! How can I assist you?',
            r'what is your name': 'I am ChatBot, your AI assistant!',
            r'bye|goodbye': 'Goodbye! Have a great day!',
            r'help': 'I can help you with various topics. Just ask me anything!',
            r'thank you|thanks': "You're welcome! Is there anything else I can help you with?",
            r'what can you do': 'I can chat with you, answer questions, and help you with various topics!',
        }

    @staticmethod
    def get_response(message: str) -> str:
        message = message.lower().strip()
        responses = ChatbotResponder.get_predefined_responses()
        
        for pattern, response in responses.items():
            if re.search(pattern, message):
                return response
        
        # Default responses based on message type
        if '?' in message:
            return f"That's an interesting question about {message.split()[0]}. Could you please provide more details?"
        else:
            return f"I understand you're talking about {message.split()[0]}. How can I help you with that?"
