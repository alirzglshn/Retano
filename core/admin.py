from django.contrib import admin
from .models import (
    Campaign,
    Tenant,
    Coupon,
    CustomerFileUpload,
    ProductFileUpload,
    CouponFileUpload,
    UsersUnNormalizedDataStaging,
    ProductsUnNormalizedDataStaging,
    ErrorLog
)


# Register your models here.

admin.site.register(Campaign)
admin.site.register(Tenant)
admin.site.register(CustomerFileUpload)
admin.site.register(ProductFileUpload)
admin.site.register(UsersUnNormalizedDataStaging)
admin.site.register(CouponFileUpload)
admin.site.register(ProductsUnNormalizedDataStaging)
admin.site.register(Coupon)
admin.site.register(ErrorLog)