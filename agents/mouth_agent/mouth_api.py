import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import asyncio

class MouthAPI:
    def __init__(self, mouth_agent):
        self.logger = logging.getLogger(__name__)
        self.mouth_agent = mouth_agent
        self.app = FastAPI(title="Mouth Agent API")
        self._setup_routes()
        
    def _setup_routes(self):
        """Setup API routes"""
        
        class SpeakRequest(BaseModel):
            text: str
            emotion: Optional[str] = None
            
        class RespondRequest(BaseModel):
            context: Dict[str, Any]
            
        class ThoughtRequest(BaseModel):
            thought: Dict[str, Any]
            
        class VoiceSettingsRequest(BaseModel):
            settings: Dict[str, Any]
        
        @self.app.post("/speak")
        async def speak(request: SpeakRequest):
            try:
                await self.mouth_agent.speak(request.text, request.emotion)
                return {"status": "success", "message": "Speech generated successfully"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/respond")
        async def respond(request: RespondRequest):
            try:
                await self.mouth_agent.respond(request.context)
                return {"status": "success", "message": "Response generated successfully"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/say_thought")
        async def say_thought(request: ThoughtRequest):
            try:
                await self.mouth_agent.say_thought(request.thought)
                return {"status": "success", "message": "Thought spoken successfully"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/adjust_voice")
        async def adjust_voice(request: VoiceSettingsRequest):
            try:
                self.mouth_agent.adjust_voice(request.settings)
                return {"status": "success", "message": "Voice settings adjusted successfully"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/status")
        async def get_status():
            try:
                return {
                    "status": "active",
                    "is_speaking": self.mouth_agent.is_speaking,
                    "current_emotion": self.mouth_agent.current_emotion,
                    "current_voice_profile": self.mouth_agent.current_voice_profile
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    async def start(self, host: str = "0.0.0.0", port: int = 8000):
        """Start the API server"""
        try:
            config = uvicorn.Config(
                self.app,
                host=host,
                port=port,
                log_level="info"
            )
            server = uvicorn.Server(config)
            await server.serve()
        except Exception as e:
            self.logger.error(f"Error starting API server: {e}")
            raise

    async def stop(self):
        """Stop the API server"""
        try:
            # Implement graceful shutdown
            pass
        except Exception as e:
            self.logger.error(f"Error stopping API server: {e}")
            raise

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run the API server
    async def main():
        from main import MouthAgent
        agent = MouthAgent()
        api = MouthAPI(agent)
        await api.start()
    
    asyncio.run(main()) 