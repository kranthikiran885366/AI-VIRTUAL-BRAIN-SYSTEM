import logging
from typing import Dict, Any, Optional
import re
from datetime import datetime
import json
from pathlib import Path

class SpeechGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.context_history = []
        self.max_history = 10
        self.templates = self._load_templates()
        
    def _load_templates(self) -> Dict[str, Any]:
        """Load speech templates for different contexts"""
        default_templates = {
            "greeting": {
                "joy": "Hey there! How are you today?",
                "neutral": "Hello. How can I help you?",
                "sad": "Hi... I hope you're doing okay."
            },
            "alert": {
                "fear": "Warning! {message} Please stay alert!",
                "urgent": "Attention! {message}",
                "neutral": "Notice: {message}"
            },
            "thought": {
                "neutral": "I think {content}",
                "joy": "I'm happy to say that {content}",
                "sad": "I'm sad to report that {content}"
            }
        }
        
        try:
            config_path = Path("config/speech_templates.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return json.load(f)
            return default_templates
        except Exception as e:
            self.logger.error(f"Error loading speech templates: {e}")
            return default_templates

    async def generate(self, text: str) -> str:
        """Generate appropriate speech from input text"""
        try:
            # Clean and normalize text
            cleaned_text = self._clean_text(text)
            
            # Add context awareness
            contextualized_text = await self._add_context(cleaned_text)
            
            # Update history
            self._update_history(contextualized_text)
            
            return contextualized_text
        except Exception as e:
            self.logger.error(f"Error generating speech: {e}")
            return text

    async def generate_response(self, context: Dict[str, Any]) -> str:
        """Generate a response based on context"""
        try:
            # Extract relevant information from context
            intent = context.get("intent", "")
            emotion = context.get("emotion", "neutral")
            previous_text = context.get("previous_text", "")
            
            # Get appropriate template
            template = self._get_template(intent, emotion)
            
            # Fill template with context
            response = self._fill_template(template, context)
            
            return response
        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return "I'm having trouble generating a response right now."

    async def thought_to_speech(self, thought: Dict[str, Any]) -> str:
        """Convert a thought into natural speech"""
        try:
            content = thought.get("content", "")
            emotion = thought.get("emotion", "neutral")
            priority = thought.get("priority", "normal")
            
            # Get appropriate template
            template = self.templates["thought"].get(emotion, self.templates["thought"]["neutral"])
            
            # Add priority context
            if priority == "high":
                prefix = "Important: "
            elif priority == "low":
                prefix = "By the way, "
            else:
                prefix = ""
                
            # Format the speech
            speech = template.format(content=content)
            
            return prefix + speech
        except Exception as e:
            self.logger.error(f"Error converting thought to speech: {e}")
            return "I'm having trouble expressing this thought."

    def _clean_text(self, text: str) -> str:
        """Clean and normalize input text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Fix common punctuation issues
        text = re.sub(r'\s+([.,!?])', r'\1', text)
        
        # Ensure proper sentence endings
        if not text[-1] in '.!?':
            text += '.'
            
        return text

    async def _add_context(self, text: str) -> str:
        """Add contextual information to the text"""
        # Add temporal context if needed
        if "today" in text.lower():
            text = text.replace("today", f"today, {datetime.now().strftime('%B %d')}")
            
        # Add personal context if available
        # This would integrate with other agents to get personal context
        
        return text

    def _update_history(self, text: str):
        """Update conversation history"""
        self.context_history.append({
            "text": text,
            "timestamp": datetime.now().isoformat()
        })
        
        # Maintain history size
        if len(self.context_history) > self.max_history:
            self.context_history.pop(0)

    def _get_template(self, intent: str, emotion: str) -> str:
        """Get appropriate speech template"""
        templates = self.templates.get(intent, {})
        return templates.get(emotion, templates.get("neutral", ""))

    def _fill_template(self, template: str, context: Dict[str, Any]) -> str:
        """Fill template with context data"""
        try:
            return template.format(**context)
        except KeyError as e:
            self.logger.error(f"Missing context key: {e}")
            return template

    def get_history(self) -> list:
        """Get conversation history"""
        return self.context_history.copy() 