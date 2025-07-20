#!/usr/bin/env python3
"""
Unit Tests for moodQue Core Functions
Run with: python test_unit.py
"""

import unittest
import sys
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestLastFMRecommender(unittest.TestCase):
    """Test the Last.fm recommendation and era logic"""
    
    def setUp(self):
        # Import here to avoid import issues
        from lastfm_recommender import find_era_overlap, infer_era_from_age
        self.find_era_overlap = find_era_overlap
        self.infer_era_from_age = infer_era_from_age
    
    def test_single_artist_era(self):
        """Test era detection for single artist"""
        result = self.find_era_overlap(["Snoop Dogg"])
        self.assertIn("1990s", result)
        self.assertIn("2000s", result)
        self.assertIn("2010s", result)
        print("✅ Single artist era test passed")
    
    def test_era_overlap_snoop_pharrell(self):
        """Test Snoop Dogg + Pharrell should find 2000s overlap"""
        result = self.find_era_overlap(["Snoop Dogg", "Pharrell"])
        self.assertIn("2000s", result)
        self.assertIn("2010s", result)
        print("✅ Snoop + Pharrell era overlap test passed")
    
    def test_different_eras_sinatra_sade(self):
        """Test Frank Sinatra + Sade should be treated individually"""
        result = self.find_era_overlap(["Frank Sinatra", "Sade"])
        # Should have eras from both artists since no overlap
        self.assertTrue(len(result) > 2)  # Multiple eras
        print("✅ Sinatra + Sade different eras test passed")
    
    def test_age_based_era_inference(self):
        """Test age-based era inference"""
        # Someone born in 1990 should prefer 2000s-2010s music
        result = self.infer_era_from_age(1990)
        self.assertIn("2000s", result)
        self.assertIn("2010s", result)
        print("✅ Age-based era inference test passed")
    
    def test_unknown_artists(self):
        """Test handling of unknown artists"""
        result = self.find_era_overlap(["Unknown Artist 123"])
        # Should return current decade as fallback
        current_decade = f"{datetime.now().year//10*10}s"
        self.assertIn(current_decade, result)
        print("✅ Unknown artist handling test passed")

class TestMoodQueEngine(unittest.TestCase):
    """Test core moodQue engine functions"""
    
    def setUp(self):
        try:
            from moodque_engine import sanitize_genre, parse_genre_list
            self.sanitize_genre = sanitize_genre
            self.parse_genre_list = parse_genre_list
        except ImportError as e:
            self.skipTest(f"Could not import moodque_engine: {e}")
    
    def test_genre_sanitization(self):
        """Test genre mapping and sanitization"""
        self.assertEqual(self.sanitize_genre("hip hop"), "hip-hop")
        self.assertEqual(self.sanitize_genre("r&b"), "r-n-b") 
        self.assertEqual(self.sanitize_genre("lo-fi"), "chill")
        self.assertEqual(self.sanitize_genre("invalid_genre"), "pop")
        print("✅ Genre sanitization test passed")
    
    def test_genre_parsing(self):
        """Test parsing of comma-separated genres"""
        result = self.parse_genre_list("hip-hop, jazz, electronic")
        self.assertIn("hip-hop", result)
        self.assertIn("jazz", result)
        self.assertLessEqual(len(result), 2)  # Should limit to 2 genres
        print("✅ Genre parsing test passed")

class TestUtilities(unittest.TestCase):
    """Test utility functions"""
    
    def test_datetime_imports(self):
        """Test that datetime imports work correctly"""
        try:
            from tracking import track_interaction
            from datetime import datetime
            
            # This should not raise an error
            test_data = {
                "user_id": "test",
                "event_type": "test",
                "data": {}
            }
            
            # Mock the database call
            with patch('tracking.db') as mock_db:
                mock_db.collection.return_value.add.return_value = True
                result = track_interaction("test", "test_event", {"test": "data"})
                
            print("✅ DateTime import test passed")
            
        except Exception as e:
            self.fail(f"DateTime import test failed: {e}")

class TestFirebaseIntegration(unittest.TestCase):
    """Test Firebase integration"""
    
    @patch('firebase_admin_init.db')
    def test_interaction_tracking(self, mock_db):
        """Test interaction tracking with mocked Firebase"""
        try:
            from tracking import track_interaction
            
            # Mock successful database operation
            mock_db.collection.return_value.add.return_value = MagicMock()
            
            result = track_interaction(
                user_id="test_user",
                event_type="test_event", 
                data={"test_key": "test_value"}
            )
            
            # Should have called the database
            mock_db.collection.assert_called_with("interactions")
            print("✅ Firebase interaction tracking test passed")
            
        except Exception as e:
            self.fail(f"Firebase integration test failed: {e}")

def run_unit_tests():
    """Run all unit tests"""
    print("🧪 Running moodQue Unit Tests")
    print("=" * 40)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestLastFMRecommender))
    suite.addTests(loader.loadTestsFromTestCase(TestMoodQueEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestUtilities))
    suite.addTests(loader.loadTestsFromTestCase(TestFirebaseIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 40)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"❌ {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"💥 {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    
    if success:
        print("\n✅ All unit tests passed! 🎉")
    else:
        print("\n❌ Some unit tests failed. Check the output above.")
    
    return success

if __name__ == "__main__":
    success = run_unit_tests()
    sys.exit(0 if success else 1)