import os
import sys
import requests
import gdown
import zipfile
import tarfile
import shutil
from pathlib import Path
from tqdm import tqdm
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "models"
DATASETS_DIR = BASE_DIR / "datasets"
TEMP_DIR = BASE_DIR / "temp"

# Create directories if they don't exist
for dir_path in [MODELS_DIR, DATASETS_DIR, TEMP_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Model URLs and paths
MODELS = {
    "yolov4": {
        "weights": "https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v3_optimal/yolov4.weights",
        "config": "https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4.cfg",
        "classes": "https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names"
    },
    "face_detection": {
        "haarcascade_frontalface": "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml",
        "haarcascade_eye": "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_eye.xml"
    },
    "face_landmarks": {
        "model": "https://drive.google.com/uc?id=1m3Rqu6JsZJqVz_9wDxQjZqX3yD3Z3Z3Z",
        "config": "https://raw.githubusercontent.com/opencv/opencv_extra/master/testdata/dnn/download_models.py"
    }
}

# Dataset URLs and paths
DATASETS = {
    "wider_face": {
        "url": "https://drive.google.com/uc?id=0B6eKvaijfFUDQUUwd21EckhUbWs",
        "type": "zip"
    },
    "celeba": {
        "url": "https://drive.google.com/uc?id=0B7EVK8r0v71pZjFTYXZWM3FlRnM",
        "type": "zip"
    },
    "coco": {
        "url": "http://images.cocodataset.org/zips/train2017.zip",
        "type": "zip"
    }
}

def download_file(url: str, output_path: Path, description: str = None):
    """Download a file with progress bar."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024
        
        with open(output_path, 'wb') as f, tqdm(
            desc=description,
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            for data in response.iter_content(block_size):
                size = f.write(data)
                pbar.update(size)
                
    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
        raise

def download_gdrive_file(file_id: str, output_path: Path, description: str = None):
    """Download a file from Google Drive."""
    try:
        url = f"https://drive.google.com/uc?id={file_id}"
        gdown.download(url, str(output_path), quiet=False)
    except Exception as e:
        logger.error(f"Error downloading from Google Drive: {str(e)}")
        raise

def extract_archive(archive_path: Path, extract_dir: Path):
    """Extract a zip or tar archive."""
    try:
        if archive_path.suffix == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        elif archive_path.suffix in ['.tar', '.gz']:
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                tar_ref.extractall(extract_dir)
    except Exception as e:
        logger.error(f"Error extracting {archive_path}: {str(e)}")
        raise

def download_models():
    """Download all required models."""
    logger.info("Downloading models...")
    
    # Download YOLOv4
    logger.info("Downloading YOLOv4...")
    download_file(
        MODELS["yolov4"]["weights"],
        MODELS_DIR / "yolov4.weights",
        "YOLOv4 weights"
    )
    download_file(
        MODELS["yolov4"]["config"],
        MODELS_DIR / "yolov4.cfg",
        "YOLOv4 config"
    )
    download_file(
        MODELS["yolov4"]["classes"],
        MODELS_DIR / "coco.names",
        "COCO classes"
    )
    
    # Download face detection models
    logger.info("Downloading face detection models...")
    download_file(
        MODELS["face_detection"]["haarcascade_frontalface"],
        MODELS_DIR / "haarcascade_frontalface_default.xml",
        "Face cascade"
    )
    download_file(
        MODELS["face_detection"]["haarcascade_eye"],
        MODELS_DIR / "haarcascade_eye.xml",
        "Eye cascade"
    )
    
    # Download face landmarks model
    logger.info("Downloading face landmarks model...")
    download_gdrive_file(
        MODELS["face_landmarks"]["model"].split("id=")[1],
        MODELS_DIR / "face_landmarks_model.pb",
        "Face landmarks model"
    )
    download_file(
        MODELS["face_landmarks"]["config"],
        MODELS_DIR / "face_landmarks_config.pbtxt",
        "Face landmarks config"
    )

def download_datasets():
    """Download all required datasets."""
    logger.info("Downloading datasets...")
    
    for dataset_name, dataset_info in DATASETS.items():
        logger.info(f"Downloading {dataset_name} dataset...")
        
        # Create dataset directory
        dataset_dir = DATASETS_DIR / dataset_name
        dataset_dir.mkdir(exist_ok=True)
        
        # Download dataset
        temp_file = TEMP_DIR / f"{dataset_name}.{dataset_info['type']}"
        if "drive.google.com" in dataset_info["url"]:
            download_gdrive_file(
                dataset_info["url"].split("id=")[1],
                temp_file,
                f"{dataset_name} dataset"
            )
        else:
            download_file(
                dataset_info["url"],
                temp_file,
                f"{dataset_name} dataset"
            )
        
        # Extract dataset
        logger.info(f"Extracting {dataset_name} dataset...")
        extract_archive(temp_file, dataset_dir)
        
        # Clean up
        temp_file.unlink()

def main():
    """Main function to download all requirements."""
    try:
        # Download models
        download_models()
        
        # Download datasets
        download_datasets()
        
        # Clean up
        shutil.rmtree(TEMP_DIR)
        
        logger.info("All downloads completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 