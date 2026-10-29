from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model

from .serializers import (
    CustomTokenObtainPairSerializer,
    UserSerializer,
    UserProfileSerializer,
)
from apps.common.permissions import IsAdminUserRole

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class CurrentUserView(APIView):
    """
    Returns the authenticated user's profile, active role, and institution details.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    """
    Admin user management viewset.
    Only system administrators can create, list, and modify user accounts and roles.
    """
    queryset = User.objects.all().select_related('institution')
    serializer_class = UserSerializer
    permission_classes = [IsAdminUserRole]
    search_fields = ['username', 'email', 'first_name', 'last_name', 'role']
    ordering_fields = ['date_joined', 'username', 'role']
