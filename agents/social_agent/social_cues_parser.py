import logging
from typing import Dict, Any, List, Optional
import re
from datetime import datetime

class SocialCuesParser:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.emotion_patterns = self._load_emotion_patterns()
        self.social_context_patterns = self._load_social_context_patterns()
        
    def _load_emotion_patterns(self) -> Dict[str, List[str]]:
        """Load patterns for emotion detection."""
        return {
            "positive": [
                r"\b(happy|joy|excited|great|wonderful|amazing)\b",
                r"😊|😃|😄|😁|😆",
                r"!+"
            ],
            "negative": [
                r"\b(sad|angry|upset|terrible|awful|horrible)\b",
                r"😢|😠|😡|😞|😔",
                r"\?+"
            ],
            "neutral": [
                r"\b(okay|fine|alright|sure|maybe)\b",
                r"😐|🤔|😶"
            ]
        }
        
    def _load_social_context_patterns(self) -> Dict[str, List[str]]:
        """Load patterns for social context detection."""
        return {
            "greeting": [
                r"\b(hi|hello|hey|greetings|good (morning|afternoon|evening))\b",
                r"👋|🙋"
            ],
            "farewell": [
                r"\b(bye|goodbye|see you|farewell)\b",
                r"👋|👋"
            ],
            "question": [
                r"\b(what|when|where|why|how|who|can|could|would|should)\b.*\?",
                r"\?"
            ],
            "statement": [
                r"\b(i think|i believe|in my opinion|i feel)\b",
                r"\.$"
            ]
        }
        
    def parse(self, cue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and analyze social cues from input data."""
        try:
            content = cue_data.get("content", "")
            parsed_data = {
                "original": cue_data,
                "timestamp": datetime.now().isoformat(),
                "emotions": self._detect_emotions(content),
                "social_context": self._detect_social_context(content),
                "formality_level": self._analyze_formality(content),
                "interaction_type": self._determine_interaction_type(cue_data)
            }
            
            return parsed_data
        except Exception as e:
            self.logger.error(f"Error parsing social cue: {e}")
            return {"error": str(e)}
            
    def _detect_emotions(self, content: str) -> List[str]:
        """Detect emotions in the content."""
        detected_emotions = []
        
        for emotion, patterns in self.emotion_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    detected_emotions.append(emotion)
                    break
                    
        return detected_emotions if detected_emotions else ["neutral"]
        
    def _detect_social_context(self, content: str) -> List[str]:
        """Detect social context in the content."""
        detected_contexts = []
        
        for context, patterns in self.social_context_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    detected_contexts.append(context)
                    break
                    
        return detected_contexts
        
    def _analyze_formality(self, content: str) -> str:
        """Analyze the formality level of the content."""
        formal_indicators = [
            r"\b(please|kindly|would you|could you)\b",
            r"\.$",
            r"proper punctuation",
            r"complete sentences"
        ]
        
        informal_indicators = [
            r"\b(hey|yo|sup|gonna|wanna)\b",
            r"!+",
            r"emojis",
            r"abbreviations"
        ]
        
        formal_score = sum(1 for pattern in formal_indicators 
                         if re.search(pattern, content, re.IGNORECASE))
        informal_score = sum(1 for pattern in informal_indicators 
                           if re.search(pattern, content, re.IGNORECASE))
                           
        if formal_score > informal_score:
            return "formal"
        elif informal_score > formal_score:
            return "informal"
        else:
            return "neutral"
            
    def _determine_interaction_type(self, cue_data: Dict[str, Any]) -> str:
        """Determine the type of interaction based on cue data."""
        if "type" in cue_data:
            return cue_data["type"]
            
        content = cue_data.get("content", "")
        if any(re.search(pattern, content, re.IGNORECASE) 
               for pattern in self.social_context_patterns["greeting"]):
            return "greeting"
        elif any(re.search(pattern, content, re.IGNORECASE) 
                for pattern in self.social_context_patterns["farewell"]):
            return "farewell"
        elif any(re.search(pattern, content, re.IGNORECASE) 
                for pattern in self.social_context_patterns["question"]):
            return "question"
        else:
            return "statement" 