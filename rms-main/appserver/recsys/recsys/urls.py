"""recsys URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from recsys import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # key api
    path("recommend_v3/", views.recommend_v3, name="recommend_v3"),
    # path("chat/", views.chat_service_stream, name="chat_stream"),
    path("pingback/", views.pingback, name="pingback"),
    # end key api

    path("meta/", views.get_meta_data, name="get_meta_data"),
    path("test_except_mail/", views.test_except_mail, name="test_except_mail"),
]
