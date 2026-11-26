"""Serializers for registration, login and the current-user endpoint."""

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public representation of a user. Never includes the password."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "date_joined"]
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    """Create a new account.

    The password is write-only and is run through Django's configured
    password validators (length, common passwords, all-numeric).
    """

    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        validators=[validate_password],
    )
    email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is already taken.")
        return value

    def create(self, validated_data):
        # create_user hashes the password; User.objects.create() would not.
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )


class LoginSerializer(serializers.Serializer):
    """Validate credentials and expose the matching user as `validated_data`."""

    username = serializers.CharField()
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["password"],
        )
        if user is None:
            # One message for both cases, so the endpoint cannot be used to
            # discover which usernames exist.
            raise serializers.ValidationError("Invalid username or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account is disabled.")
        attrs["user"] = user
        return attrs
