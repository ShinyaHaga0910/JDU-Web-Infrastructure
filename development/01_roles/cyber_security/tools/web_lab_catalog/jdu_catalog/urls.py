from django.urls import path
from catalog.admin import classroom_admin
from catalog.views import inventory

urlpatterns=[path('',inventory,name='inventory'),path('admin/',classroom_admin.urls)]
