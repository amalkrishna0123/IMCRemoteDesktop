from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('superuser/', views.superuser_dashboard, name='superuser_dashboard'),
    path('superuser/create-user/', views.create_user, name='create_user'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('create-room/', views.create_room, name='create_room'),
    path('end-room/<str:room_id>/', views.end_room, name='end_room'),
    path('logout/', views.logout_view, name='logout'),  # Use the new logout view
]
