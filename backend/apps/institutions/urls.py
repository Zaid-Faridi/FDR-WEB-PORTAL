from rest_framework.routers import DefaultRouter
from .views import InstitutionViewSet

router = DefaultRouter()
router.register(r'', InstitutionViewSet, basename='institution')

urlpatterns = router.urls
