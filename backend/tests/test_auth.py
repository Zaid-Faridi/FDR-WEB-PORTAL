import pytest
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.institutions.models import Institution
from apps.users.models import UserRole

User = get_user_model()

@pytest.fixture
def test_setup(db):
    inst = Institution.objects.create(
        aicte_id="1-TEST-001",
        name="Test Institute of Technology",
        state="Delhi"
    )
    user_inst = User.objects.create_user(
        username="user_college",
        password="Password@123",
        role=UserRole.INSTITUTION,
        institution=inst
    )
    user_officer = User.objects.create_user(
        username="user_officer",
        password="Password@123",
        role=UserRole.SCRUTINY_OFFICER
    )
    return inst, user_inst, user_officer


@pytest.mark.django_db
def test_jwt_login_success(api_client, test_setup):
    _, user_inst, _ = test_setup
    url = reverse('token_obtain_pair')
    res = api_client.post(url, {'username': 'user_college', 'password': 'Password@123'}, format='json')
    assert res.status_code == status.HTTP_200_OK
    assert 'access' in res.data
    assert 'refresh' in res.data
    assert res.data['user']['role'] == UserRole.INSTITUTION
    assert res.data['user']['institution_name'] == 'Test Institute of Technology'


@pytest.mark.django_db
def test_jwt_login_invalid_credentials(api_client, test_setup):
    url = reverse('token_obtain_pair')
    res = api_client.post(url, {'username': 'user_college', 'password': 'WrongPassword'}, format='json')
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_current_user_me_endpoint(api_client, test_setup):
    _, user_inst, _ = test_setup
    # Login to get token
    login_res = api_client.post(reverse('token_obtain_pair'), {'username': 'user_college', 'password': 'Password@123'})
    token = login_res.data['access']

    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    me_res = api_client.get(reverse('current_user'))
    assert me_res.status_code == status.HTTP_200_OK
    assert me_res.data['username'] == 'user_college'
    assert me_res.data['role'] == UserRole.INSTITUTION
    assert me_res.data['institution']['aicte_id'] == '1-TEST-001'
