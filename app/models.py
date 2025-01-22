from django.db import models
from django.contrib.auth.models import AbstractUser
import random

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('super_user', 'Super User'),
        ('regular_user', 'Regular User'),
    )
    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='regular_user')
    user_id = models.CharField(max_length=10, unique=True, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.user_id:
            while True:
                user_id = str(random.randint(1000000000, 9999999999))
                if not CustomUser.objects.filter(user_id=user_id).exists():
                    self.user_id = user_id
                    break
        super().save(*args, **kwargs)

        
class Room(models.Model):
    room_id = models.CharField(max_length=20, unique=True)
    creator = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_rooms')
    receiver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_accepted = models.BooleanField(default=False)  # Add this field

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['room_id', 'is_active'],
                name='unique_active_room'
            )
        ]
    
    def __str__(self):
        return f"Room {self.room_id} ({self.creator.username} -> {self.receiver.username})"

