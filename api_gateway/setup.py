from setuptools import setup, find_packages

setup(
    name="api_gateway",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "pydantic>=1.8.0",
        "pydantic-settings>=2.0.0",
        "python-jose[cryptography]>=3.3.0",
        "passlib[bcrypt]>=1.7.4",
        "python-multipart>=0.0.5",
        "aiohttp>=3.8.0",
        "aiofiles>=0.8.0",
        "prometheus-client>=0.11.0",
        "structlog>=21.1.0",
        "python-dotenv>=0.19.0",
        "tenacity>=8.0.1",
        "httpx>=0.23.0",
        "redis>=4.0.0",
        "aioredis>=2.0.0",
    ],
    python_requires=">=3.8",
) 