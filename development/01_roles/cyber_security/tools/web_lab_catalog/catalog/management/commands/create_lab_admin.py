from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from catalog.management.password_input import password_for


class Command(BaseCommand):
    help='Create one classroom staff user with view/add/change permissions only.'
    requires_migrations_checks=False
    requires_system_checks=[]

    def add_arguments(self,parser):parser.add_argument('--username',default='lab_admin')

    def handle(self,*args,**options):
        username=options['username'];User=get_user_model()
        user=User(username=username,is_staff=True,is_superuser=False,is_active=True)
        if User.objects.filter(username=username).exists():raise CommandError('User already exists; existing credentials are preserved.')
        user.full_clean(exclude=['password'])
        permissions=Permission.objects.filter(content_type__app_label='catalog',content_type__model='item',
            codename__in=['view_item','add_item','change_item'])
        if permissions.count()!=3:raise CommandError('Run the fixed migrations with the setup role first.')
        password=password_for(user)
        with transaction.atomic():
            user.set_password(password);user.save();user.user_permissions.set(permissions)
        self.stdout.write('Classroom administrator created with view/add/change rights; no delete or user-management rights.')
