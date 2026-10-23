from getpass import getpass
import sys
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError


def password_for(user):
    if not sys.stdin.isatty():raise CommandError('Run this command in an interactive terminal; passwords are never arguments.')
    first=getpass('Lab password (12 or more characters): ')
    second=getpass('Confirm Lab password: ')
    if first!=second:raise CommandError('Passwords do not match; no changes made.')
    try:validate_password(first,user)
    except ValidationError as error:raise CommandError('\n'.join(error.messages)) from None
    return first
