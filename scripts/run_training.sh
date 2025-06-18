#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r scripts/requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p data/models
mkdir -p data/datasets
mkdir -p config

# Run the training script
echo "Starting training process..."
python scripts/train_all_agents.py

# Deactivate virtual environment
deactivate 