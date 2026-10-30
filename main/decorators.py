# change: new file (step 2). Our own security decorators for the Product Discovery views.
# A decorator wraps a view: it runs first, and either lets the request through or answers by itself.
from functools import wraps                      # keeps the view's name, so URLs and tests still see it
from urllib.parse import urlencode

from django.core.cache import cache              # the same memory cache the API results use
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse

# How many requests one person may send per minute. Normal use stays far below this,
# a script hammering our server (and the Open Food Facts API behind it) does not
WINDOW_SECONDS = 60
SEARCH_LIMIT = 60        # Discover page loads and searches
FAVORITE_LIMIT = 30      # heart clicks
COMPARE_LIMIT = 40       # "+ Compare" and the tray's x together


# True when the request comes from our JavaScript (fetch) or from HTMX, not a normal page load.
# Those callers need JSON back, a redirect or an HTML page would break them
def wants_json(request):
    return (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or request.headers.get("hx-request") == "true"
    )


# Django's test client always calls itself "testserver". The real site refuses that host name
# (it isn't in ALLOWED_HOSTS), so this is only ever true inside tests. There every test client looks like
# the same visitor (127.0.0.1), so without this the counters would add up across the whole team's test run
def is_test_client(request):
    return request.get_host() == "testserver"


# Who is asking: the user id when logged in, otherwise the IP address
def client_id(request):
    if request.user.is_authenticated:
        return f"user:{request.user.pk}"
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")   # behind the deployment proxy the real IP is here
    ip = forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "unknown")
    return f"ip:{ip}"


# @login_required_json: like Django's @login_required, but a JavaScript/HTMX click gets
# 401 + JSON {"message", "login_url"} instead of a redirect, so main.js can send the user to the login page itself
def login_required_json(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view(request, *args, **kwargs)
        if wants_json(request):
            next_url = request.headers.get("referer") or reverse("main:show_main")   # come back to the page they were on
            return JsonResponse(
                {
                    "message": "Please log in first.",
                    "login_url": reverse("login") + "?" + urlencode({"next": next_url}),
                },
                status=401,
            )
        return redirect_to_login(request.get_full_path(), reverse("login"))   # normal forms: same as before
    return wrapper


# @rate_limit("favorite", 30): at most 30 requests per minute per person for this group of views.
# The counter lives in the cache and disappears by itself after the window
def rate_limit(name, limit, window=WINDOW_SECONDS):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if is_test_client(request):          # other tests aren't counted (our RateLimitTests use a real host name)
                return view(request, *args, **kwargs)
            key = f"ratelimit:{name}:{client_id(request)}"
            cache.add(key, 0, window)            # creates the counter only if it doesn't exist yet (starts the minute)
            try:
                count = cache.incr(key)          # +1 for this request
            except ValueError:                   # the counter expired between add and incr: start again
                cache.set(key, 1, window)
                count = 1
            if count > limit:
                message = "You're going a bit fast. Please wait a minute and try again."
                if wants_json(request):
                    response = JsonResponse({"message": message}, status=429)
                else:
                    response = render(request, "main/too_many_requests.html", {"message": message}, status=429)
                response["Retry-After"] = str(window)   # tells browsers and scripts how long to wait
                return response
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
