from channels.generic.websocket import AsyncWebsocketConsumer
import json
import pyautogui
from keyboard import press, release
import asyncio

class RoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        await self.channel_layer.group_add(
            self.room_id,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_id,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'webrtc.offer':
            await self.channel_layer.group_send(
                self.room_id,
                {
                    'type': 'webrtc.offer',
                    'offer': data['offer'],
                    'roomId': self.room_id
                }
            )
        elif message_type == 'webrtc.answer':
            await self.channel_layer.group_send(
                self.room_id,
                {
                    'type': 'webrtc.answer',
                    'answer': data['answer'],
                    'roomId': self.room_id
                }
            )
        elif message_type == 'ice_candidate':
            await self.channel_layer.group_send(
                self.room_id,
                {
                    'type': 'ice_candidate',
                    'candidate': data['candidate'],
                    'roomId': self.room_id
                }
            )
        elif message_type == 'screen_data':
            # Handle input events asynchronously
            asyncio.create_task(self.handle_screen_data(data['data']))

    async def handle_screen_data(self, data):
        """
        Handle screen data events asynchronously
        """
        try:
            if data["type"] == "mouse":
                if data["action"] == "mousemove":
                    pyautogui.moveTo(data["x"], data["y"])
                elif data["action"] == "mousedown":
                    pyautogui.mouseDown(button=data["button"])
                elif data["action"] == "mouseup":
                    pyautogui.mouseUp(button=data["button"])
            elif data["type"] == "keyboard":
                if data["action"] == "keydown":
                    press(data["key"])
                elif data["action"] == "keyup":
                    release(data["key"])
        except Exception as e:
            print(f"Error handling screen data: {e}")

    async def webrtc_offer(self, event):
        await self.send(text_data=json.dumps(event))

    async def webrtc_answer(self, event):
        await self.send(text_data=json.dumps(event))

    async def ice_candidate(self, event):
        await self.send(text_data=json.dumps(event))