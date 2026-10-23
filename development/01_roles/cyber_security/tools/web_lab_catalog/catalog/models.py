from django.db import models


class Item(models.Model):
    code=models.CharField('備品コード',max_length=32,unique=True)
    name=models.CharField('備品名',max_length=100)
    quantity=models.PositiveIntegerField('数量')
    location=models.CharField('保管場所',max_length=100)
    description=models.CharField('説明',max_length=500,blank=True,default='')
    is_public=models.BooleanField('公開する',default=False)
    created_at=models.DateTimeField('作成日時',auto_now_add=True)
    updated_at=models.DateTimeField('更新日時',auto_now=True)

    class Meta:
        db_table='catalog_item'
        ordering=['code']
        verbose_name='備品'
        verbose_name_plural='備品'
        constraints=[models.CheckConstraint(condition=~models.Q(code='')&~models.Q(name='')&~models.Q(location=''),name='catalog_item_required_text')]

    def __str__(self):return self.code+' / '+self.name
