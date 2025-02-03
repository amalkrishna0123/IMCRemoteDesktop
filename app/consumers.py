from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
import logging
import pyautogui
from keyboard import press, release
import asyncio
from asgiref.sync import sync_to_async
from django.db.models import Q

logger = logging.getLogger(__name__)

class RoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            self.room_id = self.scope['url_route']['kwargs']['room_id']
            self.user = self.scope["user"]
            
            # Get room and verify access
            self.room = await self.get_room()
            if not self.room:
                await self.close()
                return
                
            await self.channel_layer.group_add(self.room_id, self.channel_name)
            await self.accept()
            
            # Notify others about connection
            await self.channel_layer.group_send(
                self.room_id,
                {
                    "type": "user_connected",
                    "user_id": str(self.user.user_id),
                    "room_id": self.room_id
                }
            )
            
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection
        """
        try:
            logger.info(f"Disconnecting from room: {self.room_id}")
            await self.channel_layer.group_discard(
                self.room_id,
                self.channel_name
            )
            
            # Notify room members about disconnection
            await self.channel_layer.group_send(
                self.room_id,
                {
                    "type": "user_disconnected",
                    "user_id": str(self.user.user_id),
                    "room_id": self.room_id
                }
            )
            
        except Exception as e:
            logger.error(f"Error in disconnect for room {self.room_id}: {str(e)}")

    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            logger.debug(f"Received message type: {message_type} for room: {self.room_id}")

            if message_type == 'webrtc.offer':
                await self.handle_webrtc_offer(data)
            elif message_type == 'webrtc.answer':
                await self.handle_webrtc_answer(data)
            elif message_type == 'ice_candidate':
                await self.handle_ice_candidate(data)
            elif message_type == 'screen_data':
                await self.handle_screen_data(data)
            else:
                logger.warning(f"Unknown message type received: {message_type}")

        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")

    async def handle_webrtc_offer(self, data):
        """
        Handle WebRTC offer messages
        """
        await self.channel_layer.group_send(
            self.room_id,
            {
                'type': 'webrtc.offer',
                'offer': data['offer'],
                'roomId': self.room_id,
                'sender_id': str(self.user.user_id)
            }
        )

    async def handle_webrtc_answer(self, data):
        """
        Handle WebRTC answer messages
        """
        await self.channel_layer.group_send(
            self.room_id,
            {
                'type': 'webrtc.answer',
                'answer': data['answer'],
                'roomId': self.room_id,
                'sender_id': str(self.user.user_id)
            }
        )

    async def handle_ice_candidate(self, data):
        """
        Handle ICE candidate messages
        """
        await self.channel_layer.group_send(
            self.room_id,
            {
                'type': 'ice_candidate',
                'candidate': data['candidate'],
                'roomId': self.room_id,
                'sender_id': str(self.user.user_id)
            }
        )

    async def handle_screen_data(self, data):
        """
        Handle screen control data messages
        """
        screen_data = data.get('data', {})
        try:
            if await self.verify_control_permission():
                await self.process_screen_data(screen_data)
            else:
                logger.warning(f"Unauthorized screen control attempt from user: {self.user.user_id}")
        except Exception as e:
            logger.error(f"Error processing screen data: {str(e)}")

    @sync_to_async
    def process_screen_data(self, data):
        """
        Process screen control data synchronously
        """
        try:
            if data["type"] == "mouse":
                if data["action"] == "move":
                    pyautogui.moveTo(data["x"], data["y"])
                elif data["action"] == "down":
                    pyautogui.mouseDown(button=data["button"])
                elif data["action"] == "up":
                    pyautogui.mouseUp(button=data["button"])
            elif data["type"] == "keyboard":
                if data["action"] == "down":
                    press(data["key"])
                elif data["action"] == "up":
                    release(data["key"])
        except Exception as e:
            logger.error(f"Error in process_screen_data: {str(e)}")

    @database_sync_to_async
    def verify_control_permission(self):
        """
        Verify if user has permission to control the screen
        """
        try:
            return (self.room.creator == self.user or 
                   self.room.receiver == self.user and 
                   self.room.is_accepted)
        except Exception as e:
            logger.error(f"Error verifying control permission: {str(e)}")
            return False

    @database_sync_to_async
    def get_room(self):
        from .models import Room
        try:
            return Room.objects.get(
                Q(room_id=self.room_id) & 
                Q(is_active=True) &
                (Q(creator=self.scope["user"]) | Q(receiver=self.scope["user"]))
            )
        except Room.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting room: {str(e)}")
            return None

    # WebRTC message handlers
    async def webrtc_offer(self, event):
        """
        Send WebRTC offer to clients
        """
        if str(self.user.user_id) != event.get('sender_id'):
            await self.send(text_data=json.dumps(event))

    async def webrtc_answer(self, event):
        """
        Send WebRTC answer to clients
        """
        if str(self.user.user_id) != event.get('sender_id'):
            await self.send(text_data=json.dumps(event))

    async def ice_candidate(self, event):
        """
        Send ICE candidate to clients
        """
        if str(self.user.user_id) != event.get('sender_id'):
            await self.send(text_data=json.dumps(event))

    async def user_connected(self, event):
        """
        Handle user connection notification
        """
        if str(self.user.user_id) != event.get('user_id'):
            await self.send(text_data=json.dumps({
                'type': 'user_connected',
                'user_id': event['user_id'],
                'room_id': event['room_id']
            }))

    async def user_disconnected(self, event):
        """
        Handle user disconnection notification
        """
        if str(self.user.user_id) != event.get('user_id'):
            await self.send(text_data=json.dumps({
                'type': 'user_disconnected',
                'user_id': event['user_id'],
                'room_id': event['room_id']
            }))