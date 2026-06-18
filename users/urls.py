# users/urls.py

from django.urls import path
from .views import UserLoginView, UserLogoutView, UserRegisterView , AccountDetail

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("register/", UserRegisterView.as_view(), name="register"),
    path("account/" , AccountDetail , name = "account-page")
]
