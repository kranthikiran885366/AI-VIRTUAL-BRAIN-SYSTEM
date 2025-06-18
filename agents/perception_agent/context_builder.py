import numpy as np
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ContextConfig:
    """Configuration for context building."""
    max_entities: int
    max_actions: int
    max_relationships: int
    confidence_threshold: float
    temporal_window: int
    location_threshold: float

class ContextBuilder:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the context builder."""
        self.logger = logging.getLogger(__name__)
        self.config = ContextConfig(**config)
        
        # Temporal buffer
        self.temporal_buffer = []
        self.max_buffer_size = self.config.temporal_window
        
        # Performance metrics
        self.processing_times = []
    
    def build(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        """Build context from perception data."""
        start_time = time.time()
        
        try:
            # Update temporal buffer
            self._update_buffer(perception)
            
            # Extract entities
            entities = self._extract_entities(perception)
            
            # Extract actions
            actions = self._extract_actions(perception)
            
            # Extract relationships
            relationships = self._extract_relationships(entities)
            
            # Build scene description
            scene = self._build_scene_description(entities, actions, relationships)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            return {
                "entities": entities,
                "actions": actions,
                "relationships": relationships,
                "scene": scene,
                "processing_time": processing_time,
                "timestamp": time.time()
            }
        
        except Exception as e:
            self.logger.error(f"Error in context building: {str(e)}")
            return {"error": str(e)}
    
    def _update_buffer(self, perception: Dict[str, Any]):
        """Update temporal buffer with new perception."""
        # Add new perception to buffer
        self.temporal_buffer.append({
            "perception": perception,
            "timestamp": time.time()
        })
        
        # Remove old perceptions if buffer is full
        if len(self.temporal_buffer) > self.max_buffer_size:
            self.temporal_buffer.pop(0)
    
    def _extract_entities(self, perception: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities from perception data."""
        entities = []
        
        try:
            # Extract objects
            if "visual_features" in perception and "objects" in perception["visual_features"]:
                for obj in perception["visual_features"]["objects"]:
                    if obj["confidence"] >= self.config.confidence_threshold:
                        entities.append({
                            "type": "object",
                            "class": obj["class"],
                            "confidence": obj["confidence"],
                            "bbox": obj["bbox"],
                            "timestamp": time.time()
                        })
            
            # Extract faces
            if "visual_features" in perception and "faces" in perception["visual_features"]:
                for face in perception["visual_features"]["faces"]:
                    if face["confidence"] >= self.config.confidence_threshold:
                        entities.append({
                            "type": "person",
                            "confidence": face["confidence"],
                            "bbox": face["bbox"],
                            "landmarks": face["landmarks"],
                            "timestamp": time.time()
                        })
            
            # Extract speech
            if "audio_features" in perception and "speech" in perception["audio_features"]:
                speech = perception["audio_features"]["speech"]
                if speech["confidence"] >= self.config.confidence_threshold:
                    entities.append({
                        "type": "speech",
                        "text": speech["text"],
                        "confidence": speech["confidence"],
                        "timestamp": time.time()
                    })
        
        except Exception as e:
            self.logger.error(f"Error in entity extraction: {str(e)}")
        
        return entities[:self.config.max_entities]
    
    def _extract_actions(self, perception: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract actions from perception data."""
        actions = []
        
        try:
            # Extract object movements
            if len(self.temporal_buffer) >= 2:
                prev_perception = self.temporal_buffer[-2]["perception"]
                curr_perception = self.temporal_buffer[-1]["perception"]
                
                # Compare object positions
                if ("visual_features" in prev_perception and "objects" in prev_perception["visual_features"] and
                    "visual_features" in curr_perception and "objects" in curr_perception["visual_features"]):
                    
                    prev_objects = {obj["class"]: obj["bbox"] for obj in prev_perception["visual_features"]["objects"]}
                    curr_objects = {obj["class"]: obj["bbox"] for obj in curr_perception["visual_features"]["objects"]}
                    
                    for obj_class in set(prev_objects.keys()) & set(curr_objects.keys()):
                        prev_bbox = prev_objects[obj_class]
                        curr_bbox = curr_objects[obj_class]
                        
                        # Calculate movement
                        movement = self._calculate_movement(prev_bbox, curr_bbox)
                        if movement > self.config.location_threshold:
                            actions.append({
                                "type": "movement",
                                "entity": obj_class,
                                "movement": movement,
                                "timestamp": time.time()
                            })
            
            # Extract speech actions
            if "audio_features" in perception and "speech" in perception["audio_features"]:
                speech = perception["audio_features"]["speech"]
                if speech["confidence"] >= self.config.confidence_threshold:
                    actions.append({
                        "type": "speech",
                        "text": speech["text"],
                        "confidence": speech["confidence"],
                        "timestamp": time.time()
                    })
        
        except Exception as e:
            self.logger.error(f"Error in action extraction: {str(e)}")
        
        return actions[:self.config.max_actions]
    
    def _extract_relationships(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relationships between entities."""
        relationships = []
        
        try:
            # Extract spatial relationships
            for i, entity1 in enumerate(entities):
                if "bbox" not in entity1:
                    continue
                
                for entity2 in entities[i+1:]:
                    if "bbox" not in entity2:
                        continue
                    
                    # Calculate spatial relationship
                    relationship = self._calculate_spatial_relationship(
                        entity1["bbox"],
                        entity2["bbox"]
                    )
                    
                    if relationship:
                        relationships.append({
                            "type": "spatial",
                            "entity1": entity1.get("class", "unknown"),
                            "entity2": entity2.get("class", "unknown"),
                            "relationship": relationship,
                            "timestamp": time.time()
                        })
            
            # Extract temporal relationships
            if len(self.temporal_buffer) >= 2:
                prev_entities = self._extract_entities(self.temporal_buffer[-2]["perception"])
                curr_entities = self._extract_entities(self.temporal_buffer[-1]["perception"])
                
                for prev_entity in prev_entities:
                    for curr_entity in curr_entities:
                        if prev_entity.get("class") == curr_entity.get("class"):
                            relationships.append({
                                "type": "temporal",
                                "entity": prev_entity.get("class", "unknown"),
                                "relationship": "continued",
                                "timestamp": time.time()
                            })
        
        except Exception as e:
            self.logger.error(f"Error in relationship extraction: {str(e)}")
        
        return relationships[:self.config.max_relationships]
    
    def _build_scene_description(self, entities: List[Dict[str, Any]],
                               actions: List[Dict[str, Any]],
                               relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build a structured scene description."""
        scene = {
            "description": "",
            "entities": [],
            "actions": [],
            "relationships": [],
            "timestamp": time.time()
        }
        
        try:
            # Build entity descriptions
            entity_descriptions = []
            for entity in entities:
                if entity["type"] == "object":
                    entity_descriptions.append(f"a {entity['class']}")
                elif entity["type"] == "person":
                    entity_descriptions.append("a person")
                elif entity["type"] == "speech":
                    entity_descriptions.append(f"speech: {entity['text']}")
            
            # Build action descriptions
            action_descriptions = []
            for action in actions:
                if action["type"] == "movement":
                    action_descriptions.append(f"{action['entity']} is moving")
                elif action["type"] == "speech":
                    action_descriptions.append(f"someone said: {action['text']}")
            
            # Build relationship descriptions
            relationship_descriptions = []
            for rel in relationships:
                if rel["type"] == "spatial":
                    relationship_descriptions.append(
                        f"{rel['entity1']} is {rel['relationship']} {rel['entity2']}"
                    )
                elif rel["type"] == "temporal":
                    relationship_descriptions.append(
                        f"{rel['entity']} {rel['relationship']}"
                    )
            
            # Combine descriptions
            scene["description"] = " ".join([
                "In the scene, " + ", ".join(entity_descriptions),
                ". ".join(action_descriptions),
                ". ".join(relationship_descriptions)
            ])
            
            scene["entities"] = entity_descriptions
            scene["actions"] = action_descriptions
            scene["relationships"] = relationship_descriptions
        
        except Exception as e:
            self.logger.error(f"Error in scene description building: {str(e)}")
        
        return scene
    
    def _calculate_movement(self, bbox1: List[float], bbox2: List[float]) -> float:
        """Calculate movement between two bounding boxes."""
        try:
            # Calculate center points
            center1 = [(bbox1[0] + bbox1[2]) / 2, (bbox1[1] + bbox1[3]) / 2]
            center2 = [(bbox2[0] + bbox2[2]) / 2, (bbox2[1] + bbox2[3]) / 2]
            
            # Calculate Euclidean distance
            return np.sqrt(
                (center2[0] - center1[0]) ** 2 +
                (center2[1] - center1[1]) ** 2
            )
        
        except Exception as e:
            self.logger.error(f"Error in movement calculation: {str(e)}")
            return 0.0
    
    def _calculate_spatial_relationship(self, bbox1: List[float],
                                     bbox2: List[float]) -> Optional[str]:
        """Calculate spatial relationship between two bounding boxes."""
        try:
            # Calculate center points
            center1 = [(bbox1[0] + bbox1[2]) / 2, (bbox1[1] + bbox1[3]) / 2]
            center2 = [(bbox2[0] + bbox2[2]) / 2, (bbox2[1] + bbox2[3]) / 2]
            
            # Calculate relative positions
            dx = center2[0] - center1[0]
            dy = center2[1] - center1[1]
            
            # Determine relationship
            if abs(dx) < self.config.location_threshold:
                if dy > 0:
                    return "below"
                else:
                    return "above"
            elif abs(dy) < self.config.location_threshold:
                if dx > 0:
                    return "to the right of"
                else:
                    return "to the left of"
            else:
                if dx > 0:
                    if dy > 0:
                        return "below and to the right of"
                    else:
                        return "above and to the right of"
                else:
                    if dy > 0:
                        return "below and to the left of"
                    else:
                        return "above and to the left of"
        
        except Exception as e:
            self.logger.error(f"Error in spatial relationship calculation: {str(e)}")
            return None
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics."""
        if not self.processing_times:
            return {}
        
        return {
            "mean": np.mean(self.processing_times),
            "std": np.std(self.processing_times),
            "min": np.min(self.processing_times),
            "max": np.max(self.processing_times)
        }
    
    def reset(self):
        """Reset the context builder."""
        self.temporal_buffer = []
        self.processing_times = []
        self.logger.info("Context builder reset") 