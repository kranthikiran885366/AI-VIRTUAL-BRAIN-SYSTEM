import os
import yaml
import logging
import torch
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from emotion_service import EmotionService
from face_service import FaceService
from language_service import LanguageService
from planning_service import PlanningService
from motivation_service import MotivationService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Model Inference API")

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Initialize services
services = {
    'emotion': EmotionService(config['emotion_model']),
    'face': FaceService(config['face_model']),
    'language': LanguageService(config['language_model']),
    'planning': PlanningService(config['planning_model']),
    'motivation': MotivationService(config['motivation_model'])
}

# Request models
class EmotionRequest(BaseModel):
    image: str  # Base64 encoded image

class FaceRequest(BaseModel):
    image: str  # Base64 encoded image

class LanguageRequest(BaseModel):
    text: str

class PlanningRequest(BaseModel):
    state: Dict[str, Any]
    goal: Dict[str, Any]

class MotivationRequest(BaseModel):
    state: Dict[str, Any]
    action: Dict[str, Any]

# Response models
class EmotionResponse(BaseModel):
    emotion: str
    confidence: float

class FaceResponse(BaseModel):
    person_id: str
    confidence: float

class LanguageResponse(BaseModel):
    intent: str
    confidence: float
    entities: Dict[str, Any]

class PlanningResponse(BaseModel):
    action: Dict[str, Any]
    next_state: Dict[str, Any]
    confidence: float

class MotivationResponse(BaseModel):
    reward: float
    value: float

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Model Inference API"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/emotion", response_model=EmotionResponse)
async def predict_emotion(request: EmotionRequest):
    """Predict emotion from image."""
    try:
        result = await services['emotion'].predict(request.image)
        return EmotionResponse(**result)
    except Exception as e:
        logger.error(f"Error in emotion prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/face", response_model=FaceResponse)
async def recognize_face(request: FaceRequest):
    """Recognize face in image."""
    try:
        result = await services['face'].predict(request.image)
        return FaceResponse(**result)
    except Exception as e:
        logger.error(f"Error in face recognition: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/language", response_model=LanguageResponse)
async def process_language(request: LanguageRequest):
    """Process language input."""
    try:
        result = await services['language'].predict(request.text)
        return LanguageResponse(**result)
    except Exception as e:
        logger.error(f"Error in language processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/planning", response_model=PlanningResponse)
async def plan_action(request: PlanningRequest):
    """Plan action based on state and goal."""
    try:
        result = await services['planning'].predict(
            request.state,
            request.goal
        )
        return PlanningResponse(**result)
    except Exception as e:
        logger.error(f"Error in planning: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/motivation", response_model=MotivationResponse)
async def predict_motivation(request: MotivationRequest):
    """Predict motivation based on state and action."""
    try:
        result = await services['motivation'].predict(
            request.state,
            request.action
        )
        return MotivationResponse(**result)
    except Exception as e:
        logger.error(f"Error in motivation prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models")
async def list_models():
    """List available models."""
    return {
        name: {
            "status": service.status,
            "version": service.version
        }
        for name, service in services.items()
    }

@app.post("/models/{model_name}/reload")
async def reload_model(model_name: str):
    """Reload a specific model."""
    if model_name not in services:
        raise HTTPException(
            status_code=404,
            detail=f"Model {model_name} not found"
        )
    
    try:
        await services[model_name].reload()
        return {"message": f"Model {model_name} reloaded successfully"}
    except Exception as e:
        logger.error(f"Error reloading model {model_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "inference_api:app",
        host=config['host'],
        port=config['port'],
        reload=config['reload']
    ) 