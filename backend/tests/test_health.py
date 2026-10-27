import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_health_check_endpoint(api_client):
    url = reverse('api-health-check')
    response = api_client.get(url)
    assert response.status_code in [200, 503]
    data = response.json()
    assert 'status' in data
    assert 'checks' in data
    assert 'bank_verification_adapter' in data
    assert data['bank_verification_adapter']['is_mock'] is True
