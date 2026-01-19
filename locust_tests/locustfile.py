"""
Locust load testing file
Simulates user traffic for chaos testing
"""

from locust import HttpUser, task, between


class APIUser(HttpUser):
    wait_time = between(0.5, 2.0)  # Random wait between requests
    host = "http://localhost:8000"

    @task(3)
    def create_user(self):
        """Create users (weight=3, most common operation)"""
        payload = {
            "name": f"Load User {self.environment.stats.num_requests}",
            "email": f"loaduser{self.environment.stats.num_requests}@test.com",
            "is_active": True,
        }
        with self.client.post(
            "/users/",
            json=payload,
            catch_response=True,
        ) as response:
            if response.status_code != 201:
                response.failure(f"Expected 201, got {response.status_code}")

    @task(2)
    def list_users(self):
        """List all users (weight=2)"""
        with self.client.get("/users/", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Expected 200, got {response.status_code}")

    @task(1)
    def health_check(self):
        """Health check (weight=1)"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Expected 200, got {response.status_code}")
