# users/urls_legacy.py
"""
Legacy SSR auth URL routes — kept alive during the DRF transition period.
DO NOT add new routes here.  All new routes go into users/urls.py.
"""

from django.urls import path

from .views import AccountDetail, UserLoginView, UserLogoutView, UserRegisterView

urlpatterns = [
    path("login/", UserLoginView.as_view(), name="login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("register/", UserRegisterView.as_view(), name="register"),
    path("account/", AccountDetail, name="account-page"),
]
