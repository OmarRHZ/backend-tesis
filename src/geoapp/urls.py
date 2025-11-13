"""
URL configuration for geoapp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from biomass.api.views import *
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'change_password', ChangePasswordViewSet, basename="change-password")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/biomass/', include('biomass.api.urls')),
    path('api/user/register/', UserCreateView.as_view(), name='user-create'),
    path('api/token/', TokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('api-auth/', include('rest_framework.urls')),
    path('accounts/', include('allauth.urls')),
    path('callback/', google_login_callback, name='callback'),
    path('api/auth/user/', UserDetailView.as_view(), name='user-detail'),
    path('api/google/validate-token/', validate_google_token, name='validate-token'),
    #path('api/password/reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    #path('api/password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('api/reset-password/', auth_views.PasswordResetView.as_view(), name='reset-password'),
    path('api/reset-password/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('api/reset-password/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('api/reset-password/complete/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),

]

urlpatterns += router.urls
