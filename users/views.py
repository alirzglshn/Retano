# users/views.py

from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import CreateView
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from .forms import UserUpdateForm
from django.shortcuts import render  , redirect


from .forms import LoginForm, RegisterForm


class UserLoginView(LoginView):
    template_name = "users/login.html"
    authentication_form = LoginForm


class UserLogoutView(LogoutView):
    next_page = reverse_lazy("login")


class UserRegisterView(CreateView):
    template_name = "users/register.html"
    form_class = RegisterForm
    success_url = reverse_lazy("login") 
    
    
@login_required
def AccountDetail(request):
    user = request.user

    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect("account-page")  # reload page after saving
    else:
        form = UserUpdateForm(instance=user)

    return render(request, "users/account.html", {"form": form})