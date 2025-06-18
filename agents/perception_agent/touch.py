import logging
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from datetime import datetime

class TouchProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.touch_history = []
        self.max_history = config.get("max_touch_history", 100)
        
    def process(self, touch_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process tactile input data."""
        try:
            # Validate input data
            validated_data = self._validate_touch_data(touch_data)
            
            # Process touch data
            processed_data = {
                "timestamp": touch_data.get("timestamp", datetime.now().isoformat()),
                "pressure": self._process_pressure(validated_data),
                "location": self._process_location(validated_data),
                "texture": self._analyze_texture(validated_data),
                "temperature": self._process_temperature(validated_data),
                "confidence": self._calculate_confidence(validated_data)
            }
            
            # Update touch history
            self._update_touch_history(processed_data)
            
            # Add movement analysis if history is available
            if len(self.touch_history) > 1:
                processed_data["movement"] = self._analyze_movement()
                
            return processed_data
        except Exception as e:
            self.logger.error(f"Error processing tactile input: {e}")
            return {"error": str(e)}
            
    def _validate_touch_data(self, touch_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize touch input data."""
        try:
            validated = touch_data.copy()
            
            # Ensure required fields
            required_fields = ["pressure", "location"]
            for field in required_fields:
                if field not in validated:
                    raise ValueError(f"Missing required field: {field}")
                    
            # Normalize pressure to 0-1 range
            if "pressure" in validated:
                validated["pressure"] = max(0.0, min(1.0, float(validated["pressure"])))
                
            # Validate location coordinates
            if "location" in validated:
                x, y = validated["location"]
                validated["location"] = (float(x), float(y))
                
            return validated
        except Exception as e:
            self.logger.error(f"Error validating touch data: {e}")
            raise
            
    def _process_pressure(self, touch_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process pressure data from touch input."""
        try:
            pressure = touch_data["pressure"]
            
            return {
                "value": pressure,
                "intensity": self._categorize_pressure_intensity(pressure),
                "trend": self._analyze_pressure_trend(pressure)
            }
        except Exception as e:
            self.logger.error(f"Error processing pressure: {e}")
            return {"value": 0.0, "intensity": "unknown", "trend": "unknown"}
            
    def _categorize_pressure_intensity(self, pressure: float) -> str:
        """Categorize pressure intensity."""
        if pressure < 0.2:
            return "light"
        elif pressure < 0.5:
            return "medium"
        else:
            return "heavy"
            
    def _analyze_pressure_trend(self, current_pressure: float) -> str:
        """Analyze pressure trend based on history."""
        if len(self.touch_history) < 2:
            return "stable"
            
        prev_pressure = self.touch_history[-1]["pressure"]["value"]
        diff = current_pressure - prev_pressure
        
        if abs(diff) < 0.1:
            return "stable"
        elif diff > 0:
            return "increasing"
        else:
            return "decreasing"
            
    def _process_location(self, touch_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process location data from touch input."""
        try:
            x, y = touch_data["location"]
            
            return {
                "coordinates": (x, y),
                "region": self._determine_touch_region(x, y),
                "movement": self._calculate_movement(x, y)
            }
        except Exception as e:
            self.logger.error(f"Error processing location: {e}")
            return {"coordinates": (0, 0), "region": "unknown", "movement": "unknown"}
            
    def _determine_touch_region(self, x: float, y: float) -> str:
        """Determine the region of touch based on coordinates."""
        # This is a placeholder - implement actual region determination
        return "center"
        
    def _calculate_movement(self, x: float, y: float) -> Dict[str, Any]:
        """Calculate movement metrics."""
        if len(self.touch_history) < 2:
            return {"direction": "unknown", "speed": 0.0}
            
        prev_x, prev_y = self.touch_history[-1]["location"]["coordinates"]
        dx = x - prev_x
        dy = y - prev_y
        
        return {
            "direction": self._calculate_direction(dx, dy),
            "speed": np.sqrt(dx*dx + dy*dy)
        }
        
    def _calculate_direction(self, dx: float, dy: float) -> str:
        """Calculate movement direction."""
        if abs(dx) < 0.1 and abs(dy) < 0.1:
            return "stationary"
            
        angle = np.arctan2(dy, dx) * 180 / np.pi
        
        if -45 <= angle < 45:
            return "right"
        elif 45 <= angle < 135:
            return "up"
        elif -135 <= angle < -45:
            return "down"
        else:
            return "left"
            
    def _analyze_texture(self, touch_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze texture from touch input."""
        try:
            # This is a placeholder - implement actual texture analysis
            return {
                "roughness": 0.5,
                "pattern": "unknown",
                "consistency": "unknown"
            }
        except Exception as e:
            self.logger.error(f"Error analyzing texture: {e}")
            return {"error": str(e)}
            
    def _process_temperature(self, touch_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process temperature data if available."""
        try:
            temperature = touch_data.get("temperature", 25.0)  # Default to room temperature
            
            return {
                "value": temperature,
                "category": self._categorize_temperature(temperature)
            }
        except Exception as e:
            self.logger.error(f"Error processing temperature: {e}")
            return {"value": 25.0, "category": "unknown"}
            
    def _categorize_temperature(self, temp: float) -> str:
        """Categorize temperature."""
        if temp < 15:
            return "cold"
        elif temp < 25:
            return "cool"
        elif temp < 35:
            return "warm"
        else:
            return "hot"
            
    def _calculate_confidence(self, touch_data: Dict[str, Any]) -> float:
        """Calculate confidence score for touch processing."""
        try:
            # Implement confidence calculation
            # This is a placeholder - replace with actual confidence calculation
            return 0.9
        except Exception as e:
            self.logger.error(f"Error calculating confidence: {e}")
            return 0.0
            
    def _update_touch_history(self, processed_data: Dict[str, Any]):
        """Update touch history with new processed data."""
        self.touch_history.append(processed_data)
        
        # Maintain history size limit
        if len(self.touch_history) > self.max_history:
            self.touch_history = self.touch_history[-self.max_history:]
            
    def _analyze_movement(self) -> Dict[str, Any]:
        """Analyze movement patterns from touch history."""
        if len(self.touch_history) < 2:
            return {"pattern": "unknown", "consistency": "unknown"}
            
        # Implement movement pattern analysis
        # This is a placeholder - replace with actual movement analysis
        return {
            "pattern": "linear",
            "consistency": "high",
            "speed_trend": "stable"
        } 