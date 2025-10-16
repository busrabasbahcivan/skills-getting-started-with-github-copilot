"""
Tests for the Mergington High School Activities API
"""

import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities data before each test"""
    # Store original state
    original_activities = {}
    for name, details in activities.items():
        original_activities[name] = {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }
    
    yield
    
    # Restore original state after test
    activities.clear()
    activities.update(original_activities)


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root endpoint redirects to static/index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestActivitiesEndpoint:
    """Tests for the activities endpoint"""
    
    def test_get_activities_success(self, client, reset_activities):
        """Test getting all activities returns correct data"""
        response = client.get("/activities")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        
        # Check that we have some activities
        assert len(data) > 0
        
        # Check structure of first activity
        first_activity = next(iter(data.values()))
        required_fields = ["description", "schedule", "max_participants", "participants"]
        for field in required_fields:
            assert field in first_activity
        
        # Check data types
        assert isinstance(first_activity["participants"], list)
        assert isinstance(first_activity["max_participants"], int)


class TestSignupEndpoint:
    """Tests for the signup endpoint"""
    
    def test_signup_success(self, client, reset_activities):
        """Test successful signup for an activity"""
        activity_name = "Chess Club"
        email = "test@mergington.edu"
        
        response = client.post(f"/activities/{activity_name}/signup?email={email}")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert email in data["message"]
        assert activity_name in data["message"]
        
        # Verify participant was added
        assert email in activities[activity_name]["participants"]
    
    def test_signup_nonexistent_activity(self, client, reset_activities):
        """Test signup for non-existent activity returns 404"""
        response = client.post("/activities/NonExistent/signup?email=test@mergington.edu")
        assert response.status_code == 404
        
        data = response.json()
        assert data["detail"] == "Activity not found"
    
    def test_signup_duplicate_participant(self, client, reset_activities):
        """Test signing up same participant twice returns 400"""
        activity_name = "Chess Club"
        email = "test@mergington.edu"
        
        # First signup should succeed
        response1 = client.post(f"/activities/{activity_name}/signup?email={email}")
        assert response1.status_code == 200
        
        # Second signup should fail
        response2 = client.post(f"/activities/{activity_name}/signup?email={email}")
        assert response2.status_code == 400
        
        data = response2.json()
        assert "already signed up" in data["detail"]
    
    def test_signup_activity_name_with_spaces(self, client, reset_activities):
        """Test signup works with activity names containing spaces"""
        activity_name = "Programming Class"
        email = "test@mergington.edu"
        
        response = client.post(f"/activities/{activity_name}/signup?email={email}")
        assert response.status_code == 200
        
        # Verify participant was added
        assert email in activities[activity_name]["participants"]


class TestUnregisterEndpoint:
    """Tests for the unregister endpoint"""
    
    def test_unregister_success(self, client, reset_activities):
        """Test successful unregistration from an activity"""
        activity_name = "Chess Club" 
        email = "michael@mergington.edu"  # Pre-existing participant
        
        # Verify participant exists initially
        assert email in activities[activity_name]["participants"]
        
        response = client.delete(f"/activities/{activity_name}/unregister?email={email}")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert email in data["message"]
        assert activity_name in data["message"]
        
        # Verify participant was removed
        assert email not in activities[activity_name]["participants"]
    
    def test_unregister_nonexistent_activity(self, client, reset_activities):
        """Test unregister from non-existent activity returns 404"""
        response = client.delete("/activities/NonExistent/unregister?email=test@mergington.edu")
        assert response.status_code == 404
        
        data = response.json()
        assert data["detail"] == "Activity not found"
    
    def test_unregister_non_registered_participant(self, client, reset_activities):
        """Test unregistering participant not signed up returns 400"""
        activity_name = "Chess Club"
        email = "notregistered@mergington.edu"
        
        response = client.delete(f"/activities/{activity_name}/unregister?email={email}")
        assert response.status_code == 400
        
        data = response.json()
        assert "not registered" in data["detail"]


class TestIntegrationScenarios:
    """Integration tests combining multiple operations"""
    
    def test_signup_and_unregister_flow(self, client, reset_activities):
        """Test complete signup and unregister flow"""
        activity_name = "Basketball Club"
        email = "integration@mergington.edu"
        
        # Initial state - participant should not be registered
        assert email not in activities[activity_name]["participants"]
        
        # Sign up
        signup_response = client.post(f"/activities/{activity_name}/signup?email={email}")
        assert signup_response.status_code == 200
        assert email in activities[activity_name]["participants"]
        
        # Unregister
        unregister_response = client.delete(f"/activities/{activity_name}/unregister?email={email}")
        assert unregister_response.status_code == 200
        assert email not in activities[activity_name]["participants"]
    
    def test_multiple_participants_same_activity(self, client, reset_activities):
        """Test multiple participants can sign up for same activity"""
        activity_name = "Science Club"
        emails = ["student1@mergington.edu", "student2@mergington.edu", "student3@mergington.edu"]
        
        for email in emails:
            response = client.post(f"/activities/{activity_name}/signup?email={email}")
            assert response.status_code == 200
            assert email in activities[activity_name]["participants"]
        
        # All participants should be registered
        for email in emails:
            assert email in activities[activity_name]["participants"]
    
    def test_activity_capacity_tracking(self, client, reset_activities):
        """Test that participant count affects available spots"""
        activity_name = "Chess Club"
        initial_count = len(activities[activity_name]["participants"])
        max_participants = activities[activity_name]["max_participants"]
        
        # Get initial activities data
        response = client.get("/activities")
        data = response.json()
        
        # Calculate expected spots left
        expected_spots = max_participants - initial_count
        
        # Sign up a new participant
        new_email = "capacity@mergington.edu"
        client.post(f"/activities/{activity_name}/signup?email={new_email}")
        
        # Get updated activities data
        updated_response = client.get("/activities")
        updated_data = updated_response.json()
        
        # Verify participant count increased
        new_count = len(updated_data[activity_name]["participants"])
        assert new_count == initial_count + 1
        assert new_email in updated_data[activity_name]["participants"]