# users/forms.py

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import CustomUser


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="ایمیل",
        widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    password = forms.CharField(
        label="رمز عبور",
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )
 

class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        label="ایمیل",
        widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    username = forms.CharField(
        label="نام کاربری",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    shop_name = forms.CharField(
        label="نام فروشگاه",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True
    )


    shop_website_address = forms.URLField(
        label="آدرس وبسایت فروشگاه",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True
    )

    
    password1 = forms.CharField(
        label="رمز عبور",
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )
    password2 = forms.CharField(
        label="تکرار رمز عبور",
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = CustomUser
        fields = ("email", "username", "shop_name", "shop_website_address" , "password1", "password2")
        

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = [
            "first_name",
            "last_name",
            "phone_number",
            "website_address",
            "position",
            "birth_date",
            "about_me",
            "is_premium",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            
            "about_me": forms.Textarea(attrs={"rows": 4, "placeholder": "توضیح کوتاه درباره فعالیت شما..."}),
        }
