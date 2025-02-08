import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CustomUser, Room
from .forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.db.models import Q 
from django.views.decorators.csrf import ensure_csrf_cookie
from channels.layers import get_channel_layer
import logging
logger = logging.getLogger(__name__)


User = get_user_model()

def login_view(request):
    """
    Handle user login with support for both regular and super users.
    Includes comprehensive error handling and logging.
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if not username or not password:
            messages.error(request, 'Both username and password are required.')
            return render(request, 'login.html', {'error': 'Missing credentials'})
        
        try:
            # Attempt to authenticate user
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                if user.is_active:
                    # Log the user in
                    login(request, user)
                    logger.info(f"Successful login for user: {username}")
                    
                    # Check user type and redirect accordingly
                    if hasattr(user, 'user_type'):
                        if user.user_type == 'super_user':
                            return redirect('superuser_dashboard')
                        elif user.user_type == 'regular_user':
                            return redirect('user_dashboard')
                    
                    # Default fallback if user_type is not set
                    return redirect('user_dashboard')
                else:
                    logger.warning(f"Login attempt for inactive user: {username}")
                    messages.error(request, 'Your account is inactive. Please contact support.')
            else:
                logger.warning(f"Failed login attempt for username: {username}")
                messages.error(request, 'Invalid username or password.')
                
        except Exception as e:
            logger.error(f"Login error for user {username}: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred during login. Please try again.')
            
        # If we get here, login failed - return to login page with error
        return render(request, 'login.html', {'error': 'Login failed'})
    
    # If user is already logged in, redirect to appropriate dashboard
    if request.user.is_authenticated:
        if hasattr(request.user, 'user_type') and request.user.user_type == 'super_user':
            return redirect('superuser_dashboard')
        return redirect('user_dashboard')
    
    # GET request - show login form
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
def controller_dashboard(request, room_id):
    """
    View for users controlling remote desktop
    """
    try:
        # Get room and verify user is the creator
        room = get_object_or_404(Room, 
                               room_id=room_id, 
                               creator=request.user,
                               is_active=True,
                               is_accepted=True)
        
        return render(request, 'controller_dashboard.html', {
            'room': room,
            'receiver': room.receiver,
            'room_id': room_id
        })
        
    except Room.DoesNotExist:
        messages.error(request, 'Room not found or you do not have permission.')
        return redirect('user_dashboard')
    except Exception as e:
        logger.error(f"Error in controller dashboard: {str(e)}")
        messages.error(request, 'An error occurred while loading the dashboard.')
        return redirect('user_dashboard')

@login_required
def controlled_dashboard(request, room_id):
    """
    View for users sharing their desktop
    """
    try:
        # Get room and verify user is the receiver
        room = get_object_or_404(Room, 
                               room_id=room_id, 
                               receiver=request.user,
                               is_active=True,
                               is_accepted=True)
        
        return render(request, 'controlled_dashboard.html', {
            'room': room,
            'controller': room.creator,
            'room_id': room_id
        })
        
    except Room.DoesNotExist:
        messages.error(request, 'Room not found or you do not have permission.')
        return redirect('user_dashboard')
    except Exception as e:
        logger.error(f"Error in controlled dashboard: {str(e)}")
        messages.error(request, 'An error occurred while loading the dashboard.')
        return redirect('user_dashboard')

@login_required
def room_router(request, room_id):
    """
    Routes users to appropriate dashboard based on their role in the room
    """
    try:
        room = get_object_or_404(Room, room_id=room_id, is_active=True)
        
        # Verify user has access to this room
        if request.user not in [room.creator, room.receiver]:
            messages.error(request, 'Access denied.')
            return redirect('user_dashboard')
        
        # Check if room is accepted
        if not room.is_accepted and request.user == room.creator:
            messages.info(request, 'Waiting for receiver to accept the invitation.')
            return redirect('user_dashboard')
            
        # Route to appropriate dashboard based on user role
        if request.user == room.creator:
            return render(request, 'controller_dashboard.html', {
                'room': room,
                'receiver': room.receiver,
                'room_id': room_id
            })
        else:
            return render(request, 'controlled_dashboard.html', {
                'room': room,
                'controller': room.creator,
                'room_id': room_id
            })
            
    except Room.DoesNotExist:
        messages.error(request, 'Room not found.')
        return redirect('user_dashboard')
    except Exception as e:
        logger.error(f"Error in room router: {str(e)}", exc_info=True)
        messages.error(request, 'An error occurred while loading the dashboard.')
        return redirect('user_dashboard')

@login_required
def user_dashboard(request):
    """
    Main dashboard view for all users
    """
    active_rooms = Room.objects.filter(
        (Q(creator=request.user) | Q(receiver=request.user)),
        is_active=True
    )
    
    pending_invitations = Room.objects.filter(
        receiver=request.user,
        is_active=True,
        is_accepted=False
    )
    
    return render(request, 'common_dashboard.html', {
        'active_rooms': active_rooms,
        'pending_invitations': pending_invitations,
        'user_id': request.user.user_id
    })


@login_required
def create_room(request):
    """
    Create a new room between two users.
    Handles AJAX POST requests with JSON data.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Invalid request method'
        }, status=405)

    try:
        data = json.loads(request.body)
        receiver_id = data.get('receiver_id')

        if not receiver_id:
            return JsonResponse({
                'success': False,
                'error': 'Receiver ID is required'
            }, status=400)

        # Validate receiver exists
        try:
            receiver = CustomUser.objects.get(user_id=receiver_id)
        except CustomUser.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)

        # Check if trying to create room with self
        if receiver == request.user:
            return JsonResponse({
                'success': False,
                'error': 'Cannot create room with yourself'
            }, status=400)

        # Check for existing active room
        existing_room = Room.objects.filter(
            Q(creator=request.user, receiver=receiver, is_active=True) |
            Q(creator=receiver, receiver=request.user, is_active=True)
        ).first()

        if existing_room:
            return JsonResponse({
                'success': True,  # Changed to true since we're returning a valid room
                'room_id': existing_room.room_id
            })

        # Create new room with unique ID
        import uuid
        room_id = f"room_{uuid.uuid4().hex[:10]}"
        room = Room.objects.create(
            room_id=room_id,
            creator=request.user,
            receiver=receiver
        )

        return JsonResponse({
            'success': True,
            'room_id': room.room_id
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating room: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred'
        }, status=500)


@login_required
def room_view(request, room_id):
    try:
        room = Room.objects.get(room_id=room_id, is_active=True)
        
        # Verify user has access to this room
        if request.user not in [room.creator, room.receiver]:
            messages.error(request, 'Access denied.')
            return redirect('user_dashboard')
            
        # Determine which template to use
        template = 'controller_dashboard.html' if request.user == room.creator else 'controlled_dashboard.html'
        
        return render(request, template, {'room': room})
    except Room.DoesNotExist:
        messages.error(request, 'Room not found.')
        return redirect('user_dashboard')

@login_required
def accept_room(request, room_id):
    """
    Handle room acceptance with proper error handling and logging
    """
    logger.info(f"Room acceptance request received for room_id: {room_id}")
    
    if request.method != 'POST':
        logger.warning(f"Invalid method {request.method} for room acceptance")
        return JsonResponse({
            'success': False,
            'error': 'Invalid method'
        }, status=405)
    
    try:
        # Get the room with detailed validation
        room = Room.objects.get(
            room_id=room_id,
            receiver=request.user,
            is_active=True,
            is_accepted=False
        )
        
        # Update room status
        room.is_accepted = True
        room.save()
        
        logger.info(f"Room {room_id} successfully accepted by user {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'room_id': room_id,
            'message': 'Room accepted successfully'
        })
        
    except Room.DoesNotExist:
        logger.error(f"Room {room_id} not found or invalid permissions for user {request.user.username}")
        return JsonResponse({
            'success': False,
            'error': 'Room not found or already accepted'
        }, status=404)
        
    except Exception as e:
        logger.error(f"Error accepting room {room_id}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

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