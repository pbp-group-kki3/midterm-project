from django.shortcuts import render
from django.http import HttpResponse

def show_main(request):
    return HttpResponse("<h1>Welcome to SpoonFeed!</h1><p>Our Sustainable Living App is under construction!</p>")
