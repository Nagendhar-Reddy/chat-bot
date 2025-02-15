import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from datetime import datetime, timedelta
from django.core.cache import cache

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Import models here to avoid AppRegistryNotReady error
        from .models import ChatRoom
        self.room_name = self.scope['url_route']['kwargs'].get('room_name', 'default_room')
        self.room_group_name = f'chat_{self.room_name}'
        self.user = self.scope.get("user", None)
        self.username = self.user.username if self.user and not self.user.is_anonymous else "Anonymous"

        # Create or get chat room
        self.room = await self.get_or_create_room()

        # Add the user to the group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # Send welcome message
        await self.send(text_data=json.dumps({
            'type': 'welcome',
            'message': 'System',
            'response': f'Welcome to the chat, {self.username}! How can I help you today?'
        }))

        # Load chat history
        await self.load_chat_history()

    async def disconnect(self, close_code):
        # Notify others that the user has left
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': '',
                'response': f'{self.username} has left the chat.',
                'user': 'System',
            }
        )

        # Remove the user from the group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # Parse incoming message
        data = json.loads(text_data)
        raw_message = data.get('message', '').strip()

        # Ignore empty messages
        if not raw_message:
            return

        # Check for commands
        if raw_message.startswith('/'):
            await self.handle_command(raw_message)
            return

        # Rate limiting: Allow only one message every 2 seconds per user
        if not await self.is_within_rate_limit():
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'You are sending messages too quickly. Please wait a moment.'
            }))
            return

        # Generate bot response
        bot_response = self.get_chatbot_response(raw_message)

        # Save the message and response to the database
        await self.save_message(raw_message, bot_response)

        # Broadcast the message to the group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': raw_message,
                'response': bot_response,
                'user': self.username,
            }
        )

    async def chat_message(self, event):
        # Send the message to the WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'response': event['response'],
            'user': event['user']
        }))

    async def handle_command(self, command):
        """Handle special commands like /help, /clear."""
        if command == '/help':
            response = (
                "Available commands:\n"
                "/help - Show this help message\n"
                "/clear - Clear the chat history\n"
                "/typing - Notify others that you're typing"
            )
        elif command == '/clear':
            response = "Chat history cleared."
        elif command == '/typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_indicator',
                    'user': self.username,
                }
            )
            return
        else:
            response = "Unknown command. Type /help for a list of available commands."

        # Send the response to the user
        await self.send(text_data=json.dumps({
            'type': 'command_response',
            'response': response,
        }))

    async def typing_indicator(self, event):
        """Notify others that a user is typing."""
        if event['user'] != self.username:  # Don't notify the user themselves
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user': event['user'],
                'response': f"{event['user']} is typing...",
            }))

    @database_sync_to_async
    def get_or_create_room(self):
        """Create or retrieve a ChatRoom instance."""
        from .models import ChatRoom
        room, _ = ChatRoom.objects.get_or_create(name=self.room_name)
        return room

    @database_sync_to_async
    def save_message(self, message, response):
        """Save a ChatMessage instance."""
        from .models import ChatMessage
        if self.user and not self.user.is_anonymous:
            return ChatMessage.objects.create(
                room=self.room,
                user=self.user,
                message=message,
                response=response
            )

    @database_sync_to_async
    def load_chat_history(self):
        """Load the last 10 messages from the database."""
        from .models import ChatMessage
        messages = ChatMessage.objects.filter(room=self.room).order_by('-timestamp')[:10][::-1]
        for msg in messages:
            self.send(text_data=json.dumps({
                'message': msg.message,
                'response': msg.response,
                'user': msg.user.username if msg.user else 'Anonymous',
            }))

    async def is_within_rate_limit(self):
        """Check if the user is within the rate limit."""
        key = f"rate_limit:{self.username}"
        last_message_time = cache.get(key)
        if last_message_time and (datetime.now() - last_message_time) < timedelta(seconds=2):
            return False
        cache.set(key, datetime.now(), timeout=2)
        return True

    def get_chatbot_response(self, message):
        if "hi" in message.lower():
            return "Hi! How are you today?"
        elif "hello" in message.lower():
            return "Hello! How can I assist you today?"
        elif "bye" in message.lower():
            return "Goodbye! Have a great day!"
        else:
            return f"Echo: {message}"