from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CustomTokenObtainPairView,
    CurrentUserView,
    UserViewSet,
    TotpSetupView,
    TotpEnableView,
    TotpDisableView,
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('auth/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', CurrentUserView.as_view(), name='current_user'),
    path('auth/2fa/setup/', TotpSetupView.as_view(), name='totp_setup'),
    path('auth/2fa/enable/', TotpEnableView.as_view(), name='totp_enable'),
    path('auth/2fa/disable/', TotpDisableView.as_view(), name='totp_disable'),
    path('', include(router.urls)),
]
