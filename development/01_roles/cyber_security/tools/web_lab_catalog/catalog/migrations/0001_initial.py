from django.db import migrations,models


class Migration(migrations.Migration):
    initial=True
    dependencies=[]
    operations=[migrations.CreateModel(name='Item',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('code',models.CharField(max_length=32,unique=True,verbose_name='備品コード')),
        ('name',models.CharField(max_length=100,verbose_name='備品名')),
        ('quantity',models.PositiveIntegerField(verbose_name='数量')),
        ('location',models.CharField(max_length=100,verbose_name='保管場所')),
        ('description',models.CharField(blank=True,default='',max_length=500,verbose_name='説明')),
        ('is_public',models.BooleanField(default=False,verbose_name='公開する')),
        ('created_at',models.DateTimeField(auto_now_add=True,verbose_name='作成日時')),
        ('updated_at',models.DateTimeField(auto_now=True,verbose_name='更新日時')),
    ],options={'db_table':'catalog_item','ordering':['code'],'verbose_name':'備品','verbose_name_plural':'備品',
        'constraints':[models.CheckConstraint(condition=~models.Q(code='')&~models.Q(name='')&~models.Q(location=''),name='catalog_item_required_text')]})]
