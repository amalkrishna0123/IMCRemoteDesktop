import json
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CustomUser, Room
from .forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.db.models import Q 
from django.views.decorators.csrf import ensure_csrf_cookie
from channels.layers import get_channel_layer


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
    
    active_rooms = Room.objects.filter(
        (Q(creator=request.user) | Q(receiver=request.user)),
        is_active=True
    )
    
    pending_invitations = Room.objects.filter(
        receiver=request.user,
        is_active=True,
        is_accepted=False
    )
    
    # Determine which template to use
    template = 'user/controller_dashboard.html' if any(room.creator == request.user for room in active_rooms) else 'user/dashboard.html'
    
    return render(request, template, {
        'active_rooms': active_rooms,
        'pending_invitations': pending_invitations,
        'user_id': request.user.user_id
    })

@ensure_csrf_cookie
@login_required
def create_room(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            receiver_id = data.get('receiver_id')
            
            if not receiver_id:
                return JsonResponse({'success': False, 'error': 'Receiver ID is required'})
            
            try:
                # Check if room already exists
                existing_room = Room.objects.filter(
                    (Q(creator=request.user, receiver__user_id=receiver_id, is_active=True) |
                    Q(receiver=request.user, creator__user_id=receiver_id, is_active=True))
                ).first()
                
                if existing_room:
                    return JsonResponse({
                        'success': False, 
                        'error': 'Active room already exists with this user'
                    })
                
                # Find the receiver
                receiver = CustomUser.objects.get(user_id=receiver_id)
                
                # Prevent creating room with yourself
                if receiver == request.user:
                    return JsonResponse({
                        'success': False, 
                        'error': 'Cannot create room with yourself'
                    })
                
                # Create new room
                room = Room.objects.create(
                    creator=request.user,
                    receiver=receiver,
                    room_id=f"room_{request.user.user_id}_{receiver_id}"
                )
                
                return JsonResponse({
                    'success': True,
                    'room_id': room.room_id
                })
                
            except CustomUser.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'User not found'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Error creating room: {str(e)}'
                })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            })
            
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })


@login_required
def accept_room(request, room_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    try:
        room = Room.objects.get(
            room_id=room_id,
            receiver=request.user,
            is_active=True,
            is_accepted=False
        )
        room.is_accepted = True
        room.save()
        return JsonResponse({'success': True})
    except Room.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Room not found'})

@login_required
def reject_room(request, room_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    try:
        room = Room.objects.get(
            room_id=room_id,
            receiver=request.user,
            is_active=True,
            is_accepted=False
        )
        room.is_active = False
        room.save()
        return JsonResponse({'success': True})
    except Room.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Room not found'})


@login_required
def end_room(request, room_id):
    try:
        # Only allow creator or receiver to end the room
        room = Room.objects.get(
            room_id=room_id,
            is_active=True,
            creator=request.user,
        ) | Room.objects.get(
            room_id=room_id,
            is_active=True,
            receiver=request.user
        )
        room.is_active = False
        room.save()
        return redirect('user_dashboard')
    except Room.DoesNotExist:
        messages.error(request, 'Room not found or you do not have permission.')
        return redirect('user_dashboard')

# @login_required
# def reject_room(request, room_id):
#     room = Room.objects.get(room_id=room_id, receiver=request.user)
#     room.is_active = False
#     room.save()
#     return JsonResponse({'success': True})


def logout_view(request):
    logout(request)  # Logs out the user
    return redirect('login')  # Redirects to the login page (or any other page)

@login_required
def send_offer(request, room_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            offer = data.get('offer')
            
            if not offer:
                return JsonResponse({'success': False, 'error': 'Offer data is required'})
            
            # Save or process the offer as needed (e.g., store in the database or send it via WebSocket)
            room = Room.objects.get(room_id=room_id)
            
            # Logic to send offer, for example, via WebSocket
            channel_layer = get_channel_layer()
            # You can send the offer to the corresponding room channel
            channel_layer.send(
                f"room_{room_id}",
                {
                    'type': 'webrtc.offer',
                    'offer': offer
                }
            )

            return JsonResponse({'success': True})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
        except Room.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Room not found'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})