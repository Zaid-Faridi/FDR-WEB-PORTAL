from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import InstrumentViewSet, SecureDocumentDownloadView

router = DefaultRouter()
router.register(r'', InstrumentViewSet, basename='instrument')

urlpatterns = [
    path('documents/<int:pk>/download/', SecureDocumentDownloadView.as_view(), name='document-download'),
] + router.urls
