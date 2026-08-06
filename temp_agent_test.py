import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))
from orchestrator.agent_manager import AgentManager

agents = [
    'memory_agent', 'emotion_agent', 'decision_agent',
    'learning_agent', 'reasoning_agent', 'creativity_agent', 'task_agent',
    'planning_agent', 'perception_agent', 'language_agent', 'social_agent',
    'motivation_agent', 'ethics_agent', 'eyes_agent', 'ear_agent', 'mouth_agent',
]

async def test():
    manager = AgentManager({'agents': {name: {} for name in agents}})
    await manager.initialize()
    for name in agents:
        print(f'=== TEST {name} ===')
        try:
            await asyncio.wait_for(manager.load_agent(name, {}, reload=True), timeout=20)
            print(f'LOADED {name}')
        except Exception as e:
            print(f'FAILED {name}:', type(e).__name__, e)

asyncio.run(test())