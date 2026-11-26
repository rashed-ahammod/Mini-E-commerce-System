"""Serializers for registration, login and the current-user endpoint."""

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Profile, Role, profile_for

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public representation of a user. Never includes the password.

    `role` and `is_organization` travel with every login and `/auth/me/`
    response, so the frontend can decide which interface to show without a
    second request — and without guessing from which endpoints happen to
    return 403.
    """

    role = serializers.SerializerMethodField()
    is_organization = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "is_organization",
            "phone",
            "department",
            "date_joined",
        ]
        read_only_fields = fields

    def get_role(self, user) -> str:
        profile = profile_for(user)
        # A superuser without an explicit organization role still answers
        # "admin", matching what the permission classes allow them to do.
        if profile and profile.is_organization_admin:
            return Role.ADMIN
        return profile.role if profile else Role.CUSTOMER

    def get_is_organization(self, user) -> bool:
        profile = profile_for(user)
        return bool(profile and profile.is_organization)

    def get_phone(self, user) -> str:
        profile = profile_for(user)
        return profile.phone if profile else ""

    def get_department(self, user) -> str:
        profile = profile_for(user)
        return profile.department if profile else ""


class ProfileSerializer(serializers.ModelSerializer):
    """The editable part of a profile, used by the organization endpoints."""

    class Meta:
        model = Profile
        fields = ["role", "phone", "department"]


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
        # Note there is no `role` field on this serializer: public
        # registration always produces a customer. Organization accounts are
        # created by an organization admin, never by self-service.
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
