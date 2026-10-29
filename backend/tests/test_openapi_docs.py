import pytest
from django.urls import reverse
from rest_framework import status

@pytest.mark.django_db
def test_openapi_schema_endpoint(api_client):
    url = reverse('schema')
    res = api_client.get(url)
    assert res.status_code == status.HTTP_200_OK
    assert 'openapi' in res.content.decode() or 'openapi' in str(res.data)


@pytest.mark.django_db
def test_swagger_ui_endpoint(api_client):
    url = reverse('swagger-ui')
    res = api_client.get(url)
    assert res.status_code == status.HTTP_200_OK
    assert 'swagger' in res.content.decode().lower()


@pytest.mark.django_db
def test_redoc_ui_endpoint(api_client):
    url = reverse('redoc')
    res = api_client.get(url)
    assert res.status_code == status.HTTP_200_OK
    assert 'redoc' in res.content.decode().lower()
