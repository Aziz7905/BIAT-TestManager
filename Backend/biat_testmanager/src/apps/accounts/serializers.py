from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['matricule', 'email', 'first_name', 'last_name', 'role', 'department']
        read_only_fields = ['matricule', 'email']


class LoginSerializer(serializers.Serializer):
    matricule = serializers.CharField()
    password = serializers.CharField(write_only=True)