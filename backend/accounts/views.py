"""Authentication endpoints.

The API uses DRF's token authentication: a client posts credentials once,
stores the returned token, and sends it on every later request as

    Authorization: Token <key>
"""

from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    LoginSerializer,
    MyProfileSerializer,
    RegisterSerializer,
    UserSerializer,
)


def token_response(user, status_code=status.HTTP_200_OK):
    """Build the common {token, user} payload for register and login."""
    token, _created = Token.objects.get_or_create(user=user)
    return Response(
        {"token": token.key, "user": UserSerializer(user).data},
        status=status_code,
    )


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ -> create an account and return a token.

    Returning the token here means a new user is logged in immediately and
    the frontend does not have to call login straight after registering.
    """

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return token_response(user, status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/auth/login/ {username, password} -> {token, user}."""

    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer  # for the browsable API form

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        return token_response(serializer.validated_data["user"])


class LogoutView(APIView):
    """POST /api/auth/logout/ -> delete the caller's token.

    The next login issues a fresh token, so an old key cannot be reused.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveAPIView):
    """GET /api/auth/me/ -> the user the token belongs to.

    Useful for the frontend to check on startup whether a stored token is
    still valid.
    """

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class MyProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH/PUT /api/auth/profile/ -> the caller's own details.

    Separate from `/auth/me/`, which is the read-only "who am I" check the
    frontend makes on startup. This one writes, and it writes only to the
    account the token belongs to — there is no id in the URL, so there is no
    way to aim it at someone else. Changing another person's details is an
    organization job, under /api/org/.

    PATCH is the normal case (send only what changed). A field that is sent
    still has to be valid, so this cannot be used to blank out a phone
    number or an address that checkout depends on.
    """

    serializer_class = MyProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
