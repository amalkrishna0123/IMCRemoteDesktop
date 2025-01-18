from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CustomUser, Room
from .forms import UserCreationForm
from django.contrib.auth import get_user_model


User = get_user_model()

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        try:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                if hasattr(user, 'user_type') and user.user_type == 'super_user':
                    return redirect('superuser_dashboard')
                return redirect('user_dashboard')
            else:
                messages.error(request, 'Invalid credentials')
        except Exception as e:
            messages.error(request, f'Login error: {str(e)}')
    
    return render(request, 'login.html')

@login_required
def superuser_dashboard(request):
    if not hasattr(request.user, 'user_type') or request.user.user_type != 'super_user':
        return redirect('user_dashboard')
    
    users = User.objects.filter(user_type='regular_user')
    return render(request, 'superuser/dashboard.html', {'users': users})

@login_required
def create_user(request):
    if request.user.user_type != 'super_user':
        return redirect('user_dashboard')
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.user_type = 'regular_user'
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, 'User created successfully')
            return redirect('superuser_dashboard')
    else:
        form = UserCreationForm()
    
    return render(request, 'superuser/create_user.html', {'form': form})

@login_required
def user_dashboard(request):
    if hasattr(request.user, 'user_type') and request.user.user_type == 'super_user':
        return redirect('superuser_dashboard')
    
    active_room = Room.objects.filter(
        creator=request.user,
        is_active=True
    ).first()
    
    return render(request, 'user/dashboard.html', {
        'active_room': active_room,
        'user_id': request.user.user_id
    })

@login_required
def create_room(request):
    if request.method == 'POST':
        receiver_id = request.POST.get('receiver_id')
        try:
            receiver = CustomUser.objects.get(user_id=receiver_id)
            room = Room.objects.create(
                creator=request.user,
                receiver=receiver,
                room_id=f"room_{request.user.user_id}_{receiver_id}"
            )
            return JsonResponse({'success': True, 'room_id': room.room_id})
        except CustomUser.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def end_room(request, room_id):
    room = Room.objects.get(room_id=room_id)
    if room.creator == request.user:
        room.is_active = False
        room.save()
    return redirect('user_dashboard')


def logout_view(request):
    logout(request)  # Logs out the user
    return redirect('login')  # Redirects to the login page (or any other page)