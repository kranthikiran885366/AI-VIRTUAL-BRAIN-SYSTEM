import unittest
import numpy as np
from datetime import datetime
from ..vision import VisionProcessor

class TestVisionProcessor(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            "vision": {
                "target_image_size": [224, 224],
                "face_detection": {
                    "scale_factor": 1.1,
                    "min_neighbors": 5,
                    "min_size": [30, 30]
                }
            }
        }
        self.processor = VisionProcessor(self.config)
        
    def test_process_image(self):
        """Test basic image processing."""
        # Create a test image
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[25:75, 25:75] = 255  # Create a white square
        
        image_data = {
            "image": test_image,
            "timestamp": datetime.now().isoformat(),
            "resolution": (100, 100)
        }
        
        result = self.processor.process(image_data)
        
        self.assertIn("timestamp", result)
        self.assertIn("resolution", result)
        self.assertIn("objects", result)
        self.assertIn("faces", result)
        self.assertIn("scene_description", result)
        self.assertIn("confidence", result)
        
    def test_detect_faces(self):
        """Test face detection."""
        # Create a test image with a face-like pattern
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        # Create a simple face-like pattern
        test_image[30:70, 30:70] = 255  # Face region
        test_image[40:50, 40:60] = 0    # Eyes
        test_image[60:65, 45:55] = 0    # Mouth
        
        result = self.processor._detect_faces(test_image)
        
        self.assertIn("count", result)
        self.assertIn("regions", result)
        self.assertIn("contains_faces", result)
        self.assertIsInstance(result["count"], int)
        self.assertIsInstance(result["regions"], list)
        self.assertIsInstance(result["contains_faces"], bool)
        
    def test_analyze_scene(self):
        """Test scene analysis."""
        # Create a test image
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[25:75, 25:75] = 255  # Create a white square
        
        result = self.processor._analyze_scene(test_image)
        
        self.assertIn("description", result)
        self.assertIn("lighting", result)
        self.assertIn("dominant_colors", result)
        self.assertIn("scene_type", result)
        
    def test_preprocess_image(self):
        """Test image preprocessing."""
        # Create a test image
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[25:75, 25:75] = 255  # Create a white square
        
        processed = self.processor._preprocess_image(test_image)
        
        self.assertEqual(processed.shape[:2], tuple(self.config["vision"]["target_image_size"]))
        self.assertTrue(np.all(processed >= 0) and np.all(processed <= 1))
        
    def test_calculate_confidence(self):
        """Test confidence calculation."""
        # Create a test image
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[25:75, 25:75] = 255  # Create a white square
        
        confidence = self.processor._calculate_confidence(test_image)
        
        self.assertIsInstance(confidence, float)
        self.assertTrue(0 <= confidence <= 1)
        
    def test_process_empty_image(self):
        """Test processing an empty image."""
        image_data = {
            "image": np.zeros((100, 100, 3), dtype=np.uint8),
            "timestamp": datetime.now().isoformat(),
            "resolution": (100, 100)
        }
        
        result = self.processor.process(image_data)
        
        self.assertIn("timestamp", result)
        self.assertIn("resolution", result)
        self.assertIn("objects", result)
        self.assertIn("faces", result)
        self.assertIn("scene_description", result)
        self.assertIn("confidence", result)
        
    def test_process_invalid_image(self):
        """Test processing an invalid image."""
        image_data = {
            "image": None,
            "timestamp": datetime.now().isoformat(),
            "resolution": (100, 100)
        }
        
        result = self.processor.process(image_data)
        
        self.assertIn("error", result)
        
    def test_detect_objects(self):
        """Test object detection."""
        # Create a test image
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[25:75, 25:75] = 255  # Create a white square
        
        result = self.processor._detect_objects(test_image)
        
        self.assertIsInstance(result, list)
        
    def test_decode_image(self):
        """Test image decoding."""
        # Create a test image data
        image_data = "base64_encoded_image_data"
        
        result = self.processor._decode_image(image_data)
        
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result.shape), 3)  # Should be a 3D array (height, width, channels)
        
    def test_process_with_face(self):
        """Test processing an image with a face."""
        # Create a test image with a face-like pattern
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[30:70, 30:70] = 255  # Face region
        test_image[40:50, 40:60] = 0    # Eyes
        test_image[60:65, 45:55] = 0    # Mouth
        
        image_data = {
            "image": test_image,
            "timestamp": datetime.now().isoformat(),
            "resolution": (100, 100)
        }
        
        result = self.processor.process(image_data)
        
        self.assertIn("faces", result)
        self.assertIn("count", result["faces"])
        self.assertIn("regions", result["faces"])
        self.assertIn("contains_faces", result["faces"])

if __name__ == '__main__':
    unittest.main() 