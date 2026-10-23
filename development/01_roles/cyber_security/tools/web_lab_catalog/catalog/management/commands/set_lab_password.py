from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from catalog.management.password_input import password_for


class Command(BaseCommand):
    help='Change only the password column using the runtime DB role.'
    requires_migrations_checks=False
    requires_system_checks=[]

    def add_arguments(self,parser):parser.add_argument('--username',default='lab_admin')

    def handle(self,*args,**options):
        try:user=get_user_model().objects.get(username=options['username'],is_staff=True,is_superuser=False)
        except get_user_model().DoesNotExist:raise CommandError('Classroom administrator not found.') from None
        password=password_for(user)
        user.set_password(password);user.save(update_fields=['password'])
        self.stdout.write('Classroom password changed; permissions and other user fields are preserved.')
