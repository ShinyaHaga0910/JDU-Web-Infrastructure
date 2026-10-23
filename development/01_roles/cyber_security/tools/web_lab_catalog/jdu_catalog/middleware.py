from django.http import HttpResponseNotFound


class AdminEntryMiddleware:
    """The local proxy must overwrite X-JDU-Entry on both public/admin listeners."""
    def __init__(self,get_response):self.get_response=get_response

    def __call__(self,request):
        if request.path=='/admin' or request.path.startswith('/admin/'):
            if (request.META.get('REMOTE_ADDR')!='127.0.0.1'
                    or request.META.get('HTTP_X_JDU_ENTRY')!='admin'):
                return HttpResponseNotFound('Not found')
        return self.get_response(request)
