from allauth.account.adapter import DefaultAccountAdapter
from django.http import HttpResponseForbidden


class NoSignupAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter to disable self-registration.
    Only admins can create new accounts.
    """
    def is_open_for_signup(self, request):
        """
        Disable signup for all users.
        Accounts must be created by admins via Django admin.
        """
        return False
