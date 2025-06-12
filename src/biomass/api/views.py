from django.shortcuts import redirect
from django.contrib.auth.models import User
from rest_framework import generics
from .serializers import UserSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

User= get_user_model()

class UserCreateView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

class UserDetailView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
    
@login_required
def google_login_callback(request):
    user = request.user
    social_accounts = SocialAccount.objects.get(user=user)
    print("Social accounts for user:", social_accounts)

    social_account = social_accounts.first()

    if not social_account:
        print("No social account found for user:", user)
        return redirect('http://localhost:5173/login/callback/?error=NoSocialAccount')
    
    social_token = SocialToken.objects.filter(account=social_account, account__provider='google').first()
    
    if social_token:
        print("Google social token for user:", social_token.token)

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        return redirect(f'http://localhost:5173/login/callback/?access_token={access_token}')
    else:
        print("No Google social token found for user:", user)
        return redirect('http://localhost:5173/login/callback/?error=NoGoogleToken')

@csrf_exempt
def validate_google_token(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            google_access_token = data.get('access_token')
            print("Google access token:", google_access_token)

            if not google_access_token:
                return JsonResponse({'detail': 'Google access token is required'}, status=400)
            return JsonResponse({'valid': True})
        
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)
    return JsonResponse({'detail': 'Invalid request method'}, status=405)
