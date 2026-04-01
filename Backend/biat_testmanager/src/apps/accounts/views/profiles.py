from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import (
    ChangeMyPasswordSerializer,
    MyProfileSerializer,
    UpdateMyProfileSerializer,
)


class MyProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MyProfileSerializer(request.user.profile).data)

    def patch(self, request):
        profile = request.user.profile
        serializer = UpdateMyProfileSerializer(
            profile,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(MyProfileSerializer(profile).data)


class ChangeMyPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangeMyPasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password updated successfully."})