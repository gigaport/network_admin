from django.shortcuts import render

def index (request): 
    return render(request, 'index.html')

# def multicast (request): 
#     return render(request, 'multicast.html')
