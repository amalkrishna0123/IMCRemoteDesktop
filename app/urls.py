from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('superuser/', views.superuser_dashboard, name='superuser_dashboard'),
    path('superuser/create-user/', views.create_user, name='create_user'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('room/<str:room_id>/', views.room_router, name='room_router'),
    path('create_room/', views.create_room, name='create_room'),
    path('end-room/<str:room_id>/', views.end_room, name='end_room'),
    path('logout/', views.logout_view, name='logout'),
    path('accept_room/<str:room_id>/', views.accept_room, name='accept_room'),
    path('reject-room/<str:room_id>/', views.reject_room, name='reject_room'),
    path('send-offer/<str:room_id>/', views.send_offer, name='send_offer'),
    path('room/<str:room_id>/control/', views.controller_dashboard, name='controller_dashboard'),
    path('room/<str:room_id>/controlled/', views.controlled_dashboard, name='controlled_dashboard'),
]