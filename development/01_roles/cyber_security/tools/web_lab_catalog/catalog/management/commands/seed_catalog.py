from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from catalog.models import Item

SAMPLES=[
    {'code':'DEMO-PC-001','name':'練習用ノートPC','quantity':3,'location':'練習室A','description':'授業用の架空サンプルです。','is_public':True},
    {'code':'DEMO-KB-001','name':'練習用キーボード','quantity':5,'location':'練習棚B','description':'授業用の架空サンプルです。','is_public':True},
    {'code':'DEMO-PRIVATE-001','name':'確認用アダプター','quantity':1,'location':'確認棚C','description':'非公開表示を確認する架空サンプルです。','is_public':False}]


class Command(BaseCommand):
    help='Seed an empty catalog once; never reset or overwrite existing inventory.'
    requires_migrations_checks=False
    requires_system_checks=[]

    def handle(self,*args,**options):
        with transaction.atomic():
            if Item.objects.exists():raise CommandError('Existing inventory is preserved; initial seeding was not repeated.')
            Item.objects.bulk_create([Item(**x) for x in SAMPLES])
        self.stdout.write('Three fictional samples created: two public, one private.')
