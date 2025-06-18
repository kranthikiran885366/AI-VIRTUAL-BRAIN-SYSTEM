import cv2
import numpy as np
import logging
from typing import Dict, Any, Tuple, Optional
import asyncio
from datetime import datetime
import json
from pathlib import Path

class ImageProcessor:
    def __init__(self, config: Dict[str, Any]):
        """Initialize image processor with configuration."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Processing settings
        self.enable_denoising = config.get("enable_denoising", True)
        self.enable_sharpening = config.get("enable_sharpening", True)
        self.enable_contrast = config.get("enable_contrast", True)
        self.enable_color_correction = config.get("enable_color_correction", True)
        
        # Denoising parameters
        self.denoising_strength = config.get("denoising_strength", 10)
        self.denoising_template_size = config.get("denoising_template_size", 7)
        self.denoising_search_size = config.get("denoising_search_size", 21)
        
        # Sharpening parameters
        self.sharpen_kernel = np.array([[-1,-1,-1],
                                      [-1, 9,-1],
                                      [-1,-1,-1]])
        
        # Contrast parameters
        self.clahe_clip_limit = config.get("clahe_clip_limit", 2.0)
        self.clahe_grid_size = config.get("clahe_grid_size", (8,8))
        
        # Color correction parameters
        self.color_temperature = config.get("color_temperature", 0)
        self.color_tint = config.get("color_tint", 0)
        self.color_saturation = config.get("color_saturation", 1.0)
        
        # Initialize CLAHE
        self.clahe = cv2.createCLAHE(
            clipLimit=self.clahe_clip_limit,
            tileGridSize=self.clahe_grid_size
        )
        
        # Metrics
        self.metrics = {
            "total_frames_processed": 0,
            "average_processing_time": 0,
            "processing_times": [],
            "start_time": datetime.utcnow().isoformat()
        }
        
        self.logger.info("Image processor initialized")

    async def process(self, frame: np.ndarray) -> np.ndarray:
        """Process the input frame."""
        if frame is None:
            return None
            
        try:
            start_time = datetime.utcnow()
            
            # Create a copy of the frame
            processed = frame.copy()
            
            # Apply denoising
            if self.enable_denoising:
                processed = self._denoise(processed)
            
            # Apply sharpening
            if self.enable_sharpening:
                processed = self._sharpen(processed)
            
            # Apply contrast enhancement
            if self.enable_contrast:
                processed = self._enhance_contrast(processed)
            
            # Apply color correction
            if self.enable_color_correction:
                processed = self._correct_color(processed)
            
            # Update metrics
            self._update_metrics(start_time)
            
            return processed
            
        except Exception as e:
            self.logger.error(f"Error in image processing: {str(e)}")
            return frame

    def _denoise(self, frame: np.ndarray) -> np.ndarray:
        """Apply denoising to the frame."""
        return cv2.fastNlMeansDenoisingColored(
            frame,
            None,
            self.denoising_strength,
            self.denoising_strength,
            self.denoising_template_size,
            self.denoising_search_size
        )

    def _sharpen(self, frame: np.ndarray) -> np.ndarray:
        """Apply sharpening to the frame."""
        return cv2.filter2D(frame, -1, self.sharpen_kernel)

    def _enhance_contrast(self, frame: np.ndarray) -> np.ndarray:
        """Enhance contrast using CLAHE."""
        # Convert to LAB color space
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        
        # Split channels
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE to L channel
        cl = self.clahe.apply(l)
        
        # Merge channels
        enhanced = cv2.merge((cl, a, b))
        
        # Convert back to BGR
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    def _correct_color(self, frame: np.ndarray) -> np.ndarray:
        """Apply color correction to the frame."""
        # Convert to float32 for processing
        corrected = frame.astype(np.float32) / 255.0
        
        # Apply color temperature
        if self.color_temperature != 0:
            # Adjust blue channel for temperature
            corrected[:,:,0] *= (1.0 + self.color_temperature * 0.1)
            # Adjust red channel for temperature
            corrected[:,:,2] *= (1.0 - self.color_temperature * 0.1)
        
        # Apply tint
        if self.color_tint != 0:
            # Adjust green channel for tint
            corrected[:,:,1] *= (1.0 + self.color_tint * 0.1)
        
        # Apply saturation
        if self.color_saturation != 1.0:
            # Convert to HSV
            hsv = cv2.cvtColor(corrected, cv2.COLOR_BGR2HSV)
            # Adjust saturation
            hsv[:,:,1] *= self.color_saturation
            # Convert back to BGR
            corrected = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        # Clip values to valid range
        corrected = np.clip(corrected, 0.0, 1.0)
        
        # Convert back to uint8
        return (corrected * 255.0).astype(np.uint8)

    def _update_metrics(self, start_time: datetime):
        """Update processing metrics."""
        # Update total frames
        self.metrics["total_frames_processed"] += 1
        
        # Update processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        self.metrics["processing_times"].append(processing_time)
        
        # Update average processing time
        current_avg = self.metrics["average_processing_time"]
        new_avg = (current_avg * (self.metrics["total_frames_processed"] - 1) + 
                  processing_time) / self.metrics["total_frames_processed"]
        self.metrics["average_processing_time"] = new_avg
        
        # Keep only last 100 processing times
        if len(self.metrics["processing_times"]) > 100:
            self.metrics["processing_times"] = self.metrics["processing_times"][-100:]

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the image processor."""
        return {
            "enable_denoising": self.enable_denoising,
            "enable_sharpening": self.enable_sharpening,
            "enable_contrast": self.enable_contrast,
            "enable_color_correction": self.enable_color_correction,
            "denoising_strength": self.denoising_strength,
            "clahe_clip_limit": self.clahe_clip_limit,
            "color_temperature": self.color_temperature,
            "color_tint": self.color_tint,
            "color_saturation": self.color_saturation,
            "metrics": self.metrics
        }

    def update_config(self, new_config: Dict[str, Any]):
        """Update processor configuration."""
        try:
            # Update processing flags
            if "enable_denoising" in new_config:
                self.enable_denoising = new_config["enable_denoising"]
            
            if "enable_sharpening" in new_config:
                self.enable_sharpening = new_config["enable_sharpening"]
            
            if "enable_contrast" in new_config:
                self.enable_contrast = new_config["enable_contrast"]
            
            if "enable_color_correction" in new_config:
                self.enable_color_correction = new_config["enable_color_correction"]
            
            # Update denoising parameters
            if "denoising_strength" in new_config:
                self.denoising_strength = new_config["denoising_strength"]
            
            if "denoising_template_size" in new_config:
                self.denoising_template_size = new_config["denoising_template_size"]
            
            if "denoising_search_size" in new_config:
                self.denoising_search_size = new_config["denoising_search_size"]
            
            # Update CLAHE parameters
            if "clahe_clip_limit" in new_config:
                self.clahe_clip_limit = new_config["clahe_clip_limit"]
                self.clahe = cv2.createCLAHE(
                    clipLimit=self.clahe_clip_limit,
                    tileGridSize=self.clahe_grid_size
                )
            
            if "clahe_grid_size" in new_config:
                self.clahe_grid_size = new_config["clahe_grid_size"]
                self.clahe = cv2.createCLAHE(
                    clipLimit=self.clahe_clip_limit,
                    tileGridSize=self.clahe_grid_size
                )
            
            # Update color correction parameters
            if "color_temperature" in new_config:
                self.color_temperature = new_config["color_temperature"]
            
            if "color_tint" in new_config:
                self.color_tint = new_config["color_tint"]
            
            if "color_saturation" in new_config:
                self.color_saturation = new_config["color_saturation"]
            
            # Update configuration
            self.config.update(new_config)
            
            self.logger.info("Image processor configuration updated successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to update image processor configuration: {str(e)}")
            raise

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Process the input frame."""
        try:
            # Create a copy of the frame
            processed = frame.copy()
            
            # Resize if enabled
            if self.resize:
                processed = self._resize(processed)
            
            # Apply histogram equalization if enabled
            if self.enable_histogram_equalization:
                processed = self._apply_histogram_equalization(processed)
            
            # Apply Gaussian blur if enabled
            if self.enable_gaussian_blur:
                processed = self._apply_gaussian_blur(processed)
            
            # Normalize if enabled
            if self.normalize:
                processed = self._normalize(processed)
            
            return processed
            
        except Exception as e:
            self.logger.error(f"Error in image processing: {e}")
            return frame

    def _resize(self, frame: np.ndarray) -> np.ndarray:
        """Resize the frame to target dimensions."""
        return cv2.resize(frame, (self.target_width, self.target_height))

    def _apply_histogram_equalization(self, frame: np.ndarray) -> np.ndarray:
        """Apply histogram equalization to the frame."""
        # Convert to LAB color space
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        
        # Split channels
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE to L channel
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        # Merge channels
        lab = cv2.merge([l, a, b])
        
        # Convert back to BGR
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def _apply_gaussian_blur(self, frame: np.ndarray) -> np.ndarray:
        """Apply Gaussian blur to the frame."""
        return cv2.GaussianBlur(frame, (self.blur_kernel_size, self.blur_kernel_size), 0)

    def _normalize(self, frame: np.ndarray) -> np.ndarray:
        """Normalize the frame using mean and standard deviation."""
        # Convert to float32
        frame = frame.astype(np.float32)
        
        # Normalize
        frame = (frame / 255.0 - self.mean) / self.std
        
        # Convert back to uint8
        frame = np.clip(frame * 255.0, 0, 255).astype(np.uint8)
        
        return frame

    def adjust_brightness(self, frame: np.ndarray, factor: float) -> np.ndarray:
        """Adjust the brightness of the frame."""
        return cv2.convertScaleAbs(frame, alpha=factor, beta=0)

    def adjust_contrast(self, frame: np.ndarray, factor: float) -> np.ndarray:
        """Adjust the contrast of the frame."""
        return cv2.convertScaleAbs(frame, alpha=factor, beta=0)

    def adjust_saturation(self, frame: np.ndarray, factor: float) -> np.ndarray:
        """Adjust the saturation of the frame."""
        # Convert to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Adjust saturation
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * factor, 0, 255)
        
        # Convert back to BGR
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    def apply_sharpening(self, frame: np.ndarray, kernel_size: int = 3) -> np.ndarray:
        """Apply sharpening filter to the frame."""
        # Create sharpening kernel
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        
        # Apply convolution
        return cv2.filter2D(frame, -1, kernel)

    def apply_noise_reduction(self, frame: np.ndarray) -> np.ndarray:
        """Apply noise reduction to the frame."""
        return cv2.fastNlMeansDenoisingColored(frame, None, 10, 10, 7, 21)

    def apply_edge_detection(self, frame: np.ndarray) -> np.ndarray:
        """Apply edge detection to the frame."""
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply Canny edge detection
        edges = cv2.Canny(gray, 100, 200)
        
        # Convert back to BGR
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

    def apply_segmentation(self, frame: np.ndarray) -> np.ndarray:
        """Apply image segmentation to the frame."""
        # Convert to LAB color space
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        
        # Reshape the image
        pixel_values = lab.reshape((-1, 3))
        pixel_values = np.float32(pixel_values)
        
        # Define criteria
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
        
        # Number of clusters
        k = 3
        
        # Apply k-means clustering
        _, labels, centers = cv2.kmeans(pixel_values, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        
        # Convert back to uint8
        centers = np.uint8(centers)
        segmented_data = centers[labels.flatten()]
        
        # Reshape back to original image dimensions
        segmented_image = segmented_data.reshape(lab.shape)
        
        # Convert back to BGR
        return cv2.cvtColor(segmented_image, cv2.COLOR_LAB2BGR)

    def get_image_stats(self, frame: np.ndarray) -> Dict[str, Any]:
        """Get statistics about the image."""
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate statistics
        mean = np.mean(gray)
        std = np.std(gray)
        min_val = np.min(gray)
        max_val = np.max(gray)
        
        # Calculate histogram
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()
        
        return {
            "mean": mean,
            "std": std,
            "min": min_val,
            "max": max_val,
            "histogram": hist.tolist()
        } 