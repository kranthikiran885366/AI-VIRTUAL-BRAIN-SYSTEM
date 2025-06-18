import os
import sys
import json
import yaml
import shutil
import requests
import zipfile
import tarfile
from pathlib import Path
from tqdm import tqdm
import kaggle
from kaggle.api.kaggle_api_extended import KaggleApi

def download_file(url: str, output_path: Path, chunk_size: int = 8192):
    """Download a file with progress bar."""
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(output_path, 'wb') as f, tqdm(
        desc=output_path.name,
        total=total_size,
        unit='iB',
        unit_scale=True
    ) as pbar:
        for data in response.iter_content(chunk_size=chunk_size):
            size = f.write(data)
            pbar.update(size)

def setup_kaggle():
    """Setup Kaggle API credentials."""
    kaggle_dir = Path.home() / '.kaggle'
    kaggle_dir.mkdir(exist_ok=True)
    
    # Check if kaggle.json exists
    if not (kaggle_dir / 'kaggle.json').exists():
        print("Please download your kaggle.json from https://www.kaggle.com/settings/account")
        print("and place it in ~/.kaggle/kaggle.json")
        sys.exit(1)
    
    # Set permissions
    os.chmod(kaggle_dir / 'kaggle.json', 0o600)

def download_emotions_dataset():
    """Download and organize emotions dataset."""
    print("\nDownloading Emotions Dataset...")
    dataset_dir = Path('datasets/emotions_dataset')
    raw_dir = dataset_dir / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    # Download FER2013
    print("Downloading FER2013...")
    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(
        'msambare/fer2013',
        path=str(raw_dir / 'fer2013'),
        unzip=True
    )
    
    # Download AffectNet
    print("Downloading AffectNet...")
    affectnet_dir = raw_dir / 'affectnet'
    affectnet_dir.mkdir(exist_ok=True)
    print("Please visit http://mohammadmahoor.com/affectnet/")
    print("Request access and download the dataset manually")
    print(f"Extract the contents to: {affectnet_dir}")

def download_face_dataset():
    """Download and organize face dataset."""
    print("\nDownloading Face Dataset...")
    dataset_dir = Path('datasets/face_images')
    raw_dir = dataset_dir / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    # Download LFW
    print("Downloading LFW dataset...")
    lfw_url = "http://vis-www.cs.umass.edu/lfw/lfw.tgz"
    lfw_archive = raw_dir / 'lfw.tgz'
    
    download_file(lfw_url, lfw_archive)
    
    # Extract LFW
    print("Extracting LFW dataset...")
    with tarfile.open(lfw_archive) as tar:
        tar.extractall(path=raw_dir)
    
    # Clean up
    lfw_archive.unlink()

def download_conversations_dataset():
    """Download and organize conversations dataset."""
    print("\nDownloading Conversations Dataset...")
    dataset_dir = Path('datasets/conversations_dataset')
    dataset_dir.mkdir(parents=True, exist_ok=True)
    
    # Download MultiWOZ
    print("Downloading MultiWOZ dataset...")
    multiwoz_url = "https://github.com/budzianowski/multiwoz/raw/master/data/MultiWOZ_2.1.zip"
    multiwoz_archive = dataset_dir / 'multiwoz.zip'
    
    download_file(multiwoz_url, multiwoz_archive)
    
    # Extract MultiWOZ
    print("Extracting MultiWOZ dataset...")
    with zipfile.ZipFile(multiwoz_archive) as zip_ref:
        zip_ref.extractall(dataset_dir)
    
    # Clean up
    multiwoz_archive.unlink()

def download_movement_dataset():
    """Download and organize movement dataset."""
    print("\nDownloading Movement Dataset...")
    dataset_dir = Path('datasets/movement_data')
    sensor_logs_dir = dataset_dir / 'sensor_logs'
    sensor_logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Download UCI HAR dataset
    print("Downloading UCI HAR dataset...")
    uci_url = "https://archive.ics.uci.edu/ml/machine-learning-databases/00240/UCI%20HAR%20Dataset.zip"
    uci_archive = dataset_dir / 'uci_har.zip'
    
    download_file(uci_url, uci_archive)
    
    # Extract UCI HAR
    print("Extracting UCI HAR dataset...")
    with zipfile.ZipFile(uci_archive) as zip_ref:
        zip_ref.extractall(dataset_dir)
    
    # Move files to sensor_logs
    uci_dir = dataset_dir / 'UCI HAR Dataset'
    for file in uci_dir.glob('**/*'):
        if file.is_file():
            shutil.move(str(file), str(sensor_logs_dir / file.name))
    
    # Clean up
    shutil.rmtree(uci_dir)
    uci_archive.unlink()

def main():
    """Main function to download all datasets."""
    print("Starting dataset downloads...")
    
    # Setup Kaggle
    setup_kaggle()
    
    # Download datasets
    download_emotions_dataset()
    download_face_dataset()
    download_conversations_dataset()
    download_movement_dataset()
    
    print("\nAll datasets downloaded successfully!")
    print("\nNote: For AffectNet dataset, please:")
    print("1. Visit http://mohammadmahoor.com/affectnet/")
    print("2. Request access to the dataset")
    print("3. Download and extract to datasets/emotions_dataset/raw/affectnet/")

if __name__ == "__main__":
    main() 