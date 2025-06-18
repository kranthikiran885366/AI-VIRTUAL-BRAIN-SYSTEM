import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid

from structlog import get_logger

from ...config import settings

logger = get_logger()

class TaskAnalyzer:
    """Task analyzer component for the Task Agent."""
    
    def __init__(self):
        """Initialize the task analyzer."""
        self.analysis_history: List[Dict] = []
        self.max_history = settings.TASK_ANALYSIS_HISTORY_SIZE
        self.task_patterns: Dict[str, Dict] = {}
        self.task_metrics: Dict[str, float] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize the task analyzer component."""
        if self._initialized:
            return
        
        logger.info("Initializing task analyzer")
        self._initialized = True
    
    async def shutdown(self):
        """Shutdown the task analyzer component."""
        logger.info("Shutting down task analyzer")
        self._initialized = False
    
    async def analyze_task(self, task: Dict) -> Dict:
        """Analyze a task and its impact."""
        if not self._initialized:
            raise RuntimeError("Task analyzer not initialized")
        
        # Create analysis entry
        analysis = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "task_id": task["id"],
            "title": task["title"],
            "priority": task["priority"],
            "status": task["status"],
            "patterns": await self._detect_patterns(task),
            "metrics": await self._calculate_metrics(task),
            "recommendations": await self._generate_recommendations(task)
        }
        
        # Add to history
        self.analysis_history.append(analysis)
        
        # Trim history if needed
        if len(self.analysis_history) > self.max_history:
            self.analysis_history = self.analysis_history[-self.max_history:]
        
        # Update patterns and metrics
        await self._update_patterns(task)
        await self._update_metrics(task)
        
        logger.debug(f"Analyzed task: {task['id']}")
        return analysis
    
    async def _detect_patterns(self, task: Dict) -> List[Dict]:
        """Detect patterns in the task."""
        patterns = []
        
        # Check for recurring tasks
        recent_tasks = [
            t for t in self.analysis_history[-10:]
            if t["title"] == task["title"]
        ]
        
        if len(recent_tasks) >= 3:
            patterns.append({
                "type": "recurring",
                "title": task["title"],
                "count": len(recent_tasks),
                "frequency": "high"
            })
        
        # Check for task combinations
        if task["tags"]:
            for pattern_type, pattern_data in self.task_patterns.items():
                if self._matches_pattern(task, pattern_data):
                    patterns.append({
                        "type": "combination",
                        "pattern_type": pattern_type,
                        "confidence": pattern_data["confidence"]
                    })
        
        return patterns
    
    def _matches_pattern(self, task: Dict, pattern: Dict) -> bool:
        """Check if a task matches a pattern."""
        # Check tags
        if not all(tag in task["tags"] for tag in pattern["tags"]):
            return False
        
        # Check priority
        if pattern["priority"] != task["priority"]:
            return False
        
        return True
    
    async def _calculate_metrics(self, task: Dict) -> Dict:
        """Calculate task metrics."""
        metrics = {
            "complexity": self._calculate_complexity(task),
            "urgency": self._calculate_urgency(task),
            "importance": self._calculate_importance(task)
        }
        
        # Calculate overall score
        metrics["score"] = (
            metrics["complexity"] * 0.3 +
            metrics["urgency"] * 0.4 +
            metrics["importance"] * 0.3
        )
        
        return metrics
    
    def _calculate_complexity(self, task: Dict) -> float:
        """Calculate task complexity."""
        complexity = 0.5  # Base complexity
        
        # Adjust for dependencies
        if task["dependencies"]:
            complexity += len(task["dependencies"]) * 0.1
        
        # Adjust for description length
        if task["description"]:
            complexity += min(len(task["description"]) / 1000, 0.3)
        
        return min(complexity, 1.0)
    
    def _calculate_urgency(self, task: Dict) -> float:
        """Calculate task urgency."""
        urgency = 0.5  # Base urgency
        
        # Adjust for priority
        urgency += task["priority"] * 0.1
        
        # Adjust for due date
        if task["due_date"]:
            due_date = datetime.fromisoformat(task["due_date"])
            time_left = (due_date - datetime.utcnow()).total_seconds()
            if time_left < 86400:  # Less than 24 hours
                urgency += 0.3
            elif time_left < 604800:  # Less than a week
                urgency += 0.2
        
        return min(urgency, 1.0)
    
    def _calculate_importance(self, task: Dict) -> float:
        """Calculate task importance."""
        importance = 0.5  # Base importance
        
        # Adjust for priority
        importance += task["priority"] * 0.1
        
        # Adjust for tags
        if "important" in task["tags"]:
            importance += 0.2
        if "critical" in task["tags"]:
            importance += 0.3
        
        return min(importance, 1.0)
    
    async def _generate_recommendations(self, task: Dict) -> List[Dict]:
        """Generate recommendations based on task analysis."""
        recommendations = []
        
        # Check complexity
        metrics = await self._calculate_metrics(task)
        if metrics["complexity"] > 0.8:
            recommendations.append({
                "type": "complexity",
                "action": "break_down",
                "suggestion": "Consider breaking down this task into smaller subtasks"
            })
        
        # Check urgency
        if metrics["urgency"] > 0.8:
            recommendations.append({
                "type": "urgency",
                "action": "prioritize",
                "suggestion": "This task requires immediate attention"
            })
        
        # Check patterns
        patterns = await self._detect_patterns(task)
        for pattern in patterns:
            if pattern["type"] == "recurring" and pattern["frequency"] == "high":
                recommendations.append({
                    "type": "pattern",
                    "action": "automate",
                    "suggestion": "Consider automating this recurring task"
                })
        
        return recommendations
    
    async def _update_patterns(self, task: Dict):
        """Update task patterns based on new task."""
        # Update pattern confidence
        for pattern_type, pattern_data in self.task_patterns.items():
            if self._matches_pattern(task, pattern_data):
                pattern_data["confidence"] = min(1.0, pattern_data["confidence"] + 0.1)
            else:
                pattern_data["confidence"] = max(0.0, pattern_data["confidence"] - 0.05)
        
        # Add new pattern if needed
        if task["tags"]:
            pattern_key = f"{task['priority']}_{hash(frozenset(task['tags']))}"
            if pattern_key not in self.task_patterns:
                self.task_patterns[pattern_key] = {
                    "priority": task["priority"],
                    "tags": task["tags"],
                    "confidence": 0.5
                }
    
    async def _update_metrics(self, task: Dict):
        """Update task metrics based on new task."""
        metrics = await self._calculate_metrics(task)
        
        # Update average metrics
        for key, value in metrics.items():
            current_avg = self.task_metrics.get(key, 0.5)
            self.task_metrics[key] = (current_avg + value) / 2
    
    async def get_analysis(self) -> Dict:
        """Get current analysis state."""
        if not self._initialized:
            raise RuntimeError("Task analyzer not initialized")
        
        return {
            "patterns": self.task_patterns,
            "metrics": self.task_metrics,
            "history_size": len(self.analysis_history),
            "max_history": self.max_history,
            "oldest_analysis": min(a["timestamp"] for a in self.analysis_history) if self.analysis_history else None,
            "newest_analysis": max(a["timestamp"] for a in self.analysis_history) if self.analysis_history else None
        }
    
    async def get_stats(self) -> Dict:
        """Get task analyzer statistics."""
        if not self._initialized:
            raise RuntimeError("Task analyzer not initialized")
        
        return {
            "analysis_count": len(self.analysis_history),
            "pattern_count": len(self.task_patterns),
            "metric_count": len(self.task_metrics),
            "max_history": self.max_history,
            "oldest_analysis": min(a["timestamp"] for a in self.analysis_history) if self.analysis_history else None,
            "newest_analysis": max(a["timestamp"] for a in self.analysis_history) if self.analysis_history else None
        }
    
    async def clear_analysis(self):
        """Clear all analysis data."""
        if not self._initialized:
            raise RuntimeError("Task analyzer not initialized")
        
        self.analysis_history.clear()
        self.task_patterns.clear()
        self.task_metrics.clear()
        logger.info("Cleared all analysis data") 