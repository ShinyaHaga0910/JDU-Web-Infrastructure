from django.contrib import admin
from .models import Item


class ClassroomAdminSite(admin.AdminSite):
    site_header='JDU 備品管理'
    site_title='備品管理'
    index_title='備品管理'
    site_url=None
    enable_nav_sidebar=False

    def get_urls(self):
        return [u for u in super().get_urls() if getattr(u,'name',None) not in ('password_change','password_change_done')]


class ItemAdmin(admin.ModelAdmin):
    list_display=['code','name','quantity','location','is_public','updated_at']
    list_filter=['is_public']
    search_fields=['code','name','location']
    readonly_fields=['created_at','updated_at']
    fields=['code','name','quantity','location','description','is_public','created_at','updated_at']
    actions=None
    save_on_top=True

    def has_delete_permission(self,request,obj=None):return False


classroom_admin=ClassroomAdminSite(name='admin')
classroom_admin.register(Item,ItemAdmin)
