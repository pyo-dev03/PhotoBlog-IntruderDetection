from django.urls import include, path
from rest_framework import routers

from . import views

# 강의자료 p.5 : REST API URL 설정
router = routers.DefaultRouter()
router.register('Post', views.BlogImages)

urlpatterns = [
    path('', views.post_list, name='post_list'),
    path('post/<int:pk>/', views.post_detail, name='post_detail'),
    path('post/new/', views.post_new, name='post_new'),
    path('post/<int:pk>/edit/', views.post_edit, name='post_edit'),
    path('post/<int:pk>/ack/', views.post_ack, name='post_ack'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('js_test/', views.js_test, name='js_test'),
    path('api_root/', include(router.urls)),
]
