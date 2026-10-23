from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from .models import Item


@require_GET
@never_cache
def inventory(request):
    return render(request,'catalog/inventory.html',{'items':Item.objects.filter(is_public=True),'site_name':settings.CATALOG_SITE_NAME})
