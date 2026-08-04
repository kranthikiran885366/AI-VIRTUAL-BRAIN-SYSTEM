import sys, asyncio, traceback
sys.path.insert(0, '.')

async def run():
    from agents.memory_agent.agent import MemoryAgent
    from agents.memory_agent.memory_processor import MemoryProcessor
    agent = MemoryAgent(agent_id='diag_test')
    await agent.initialize()

    # Test store directly
    result = await agent.store(
        content='Test memory content for validation',
        memory_type='short_term',
        importance=0.7,
        user_id='test_user',
    )
    print('STORE RESULT:', result)
    print('STATUS:', result.get('status'))
    print('MEMORY_ID:', result.get('memory_id'))

    # Test execute_task store
    task_result = await agent.execute_task({
        'action': 'store',
        'input_data': {'content': 'pipeline test', 'memory_type': 'short_term', 'importance': 0.5},
        'user_id': 'test_user',
    })
    print('TASK RESULT:', task_result)
    print('TASK STATUS:', task_result.get('status'))

    # Test recall
    memories = await agent.recall(query='test memory', user_id='test_user', limit=5)
    print('RECALL COUNT:', len(memories))

    await agent.shutdown()

asyncio.run(run())
