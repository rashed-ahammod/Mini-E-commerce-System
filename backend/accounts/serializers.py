"""Serializers for registration, login and the current-user endpoint."""

import re

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Profile, Role, profile_for

User = get_user_model()

# Deliberately loose: digits with the punctuation people actually type, and
# at least seven of them. Anything stricter rejects valid numbers from some
# country or other, which is worse than accepting a typo the shop can ask
# about when it calls.
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9\s().-]{5,}$")


def validate_phone(value):
    """A phone number someone could plausibly dial."""
    value = (value or "").strip()
    digits = re.sub(r"\D", "", value)
    if len(digits) < 7 or not PHONE_PATTERN.match(value):
        raise serializers.ValidationError(
            "Enter a phone number with at least 7 digits, e.g. +880 1711 123456."
        )
    return value


def validate_address(value):
    """An address with enough in it to deliver to."""
    value = (value or "").strip()
    if len(value) < 10:
        raise serializers.ValidationError(
            "Enter a full delivery address — street, area and city."
        )
    return value


def unique_email(value, *, exclude_pk=None):
    """One account per email address, so a reset can never be ambiguous."""
    value = (value or "").strip()
    taken = User.objects.filter(email__iexact=value)
    if exclude_pk is not None:
        taken = taken.exclude(pk=exclude_pk)
    if taken.exists():
        raise serializers.ValidationError("An account with that email already exists.")
    return value


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
    address = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    # So the shop can prompt for what is missing, and prefill checkout from
    # the profile, without a second request after login.
    profile_complete = serializers.SerializerMethodField()
    missing_details = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "is_organization",
            "phone",
            "address",
            "department",
            "profile_complete",
            "missing_details",
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

    def get_address(self, user) -> str:
        profile = profile_for(user)
        return profile.address if profile else ""

    def get_department(self, user) -> str:
        profile = profile_for(user)
        return profile.department if profile else ""

    def get_profile_complete(self, user) -> bool:
        profile = profile_for(user)
        return bool(profile and profile.is_complete)

    def get_missing_details(self, user) -> list:
        profile = profile_for(user)
        return profile.missing_details if profile else ["email", "phone", "address"]


class ProfileSerializer(serializers.ModelSerializer):
    """The editable part of a profile, used by the organization endpoints."""

    class Meta:
        model = Profile
        fields = ["role", "phone", "address", "department"]


class MyProfileSerializer(serializers.Serializer):
    """The account's own details, for GET/PATCH /api/auth/profile/.

    Email, phone and address are all required: an order has to reach a real
    person at a real address, and the shop prefills checkout from here. They
    live on two tables — email on User, the rest on Profile — which this
    serializer hides, so the frontend sees one flat form.

    PATCH is partial, but a field that *is* sent may not be blanked: that
    would quietly undo the requirement.
    """

    # Only the writable fields are declared. `to_representation` below builds
    # the response by hand — it has to, because it reads from two tables — so
    # declaring the read-only keys here as well would be two descriptions of
    # one payload, free to drift apart. What the response also carries:
    # username, role, department, date_joined, profile_complete and
    # missing_details.
    #
    # Nothing that grants privileges is accepted. `role` in particular is
    # reported but never read, so this endpoint is not a way to become staff.
    first_name = serializers.CharField(
        required=False, allow_blank=True, max_length=150
    )
    last_name = serializers.CharField(
        required=False, allow_blank=True, max_length=150
    )
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, validators=[validate_phone])
    address = serializers.CharField(max_length=500, validators=[validate_address])

    def validate_email(self, value):
        return unique_email(value, exclude_pk=self.instance.pk if self.instance else None)

    def to_representation(self, user):
        profile = profile_for(user)
        return {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": profile.phone if profile else "",
            "address": profile.address if profile else "",
            "role": profile.role if profile else Role.CUSTOMER,
            "department": profile.department if profile else "",
            "date_joined": user.date_joined,
            "profile_complete": bool(profile and profile.is_complete),
            "missing_details": profile.missing_details if profile else [],
        }

    def update(self, instance, validated_data):
        user_fields = [
            field
            for field in ("email", "first_name", "last_name")
            if field in validated_data
        ]
        for field in user_fields:
            setattr(instance, field, validated_data[field].strip())
        if user_fields:
            instance.save(update_fields=user_fields)

        profile = profile_for(instance)
        for field in ("phone", "address"):
            if field in validated_data:
                setattr(profile, field, validated_data[field].strip())
        profile.save()
        return instance


class RegisterSerializer(serializers.ModelSerializer):
    """Create a new account.

    Email, phone and address are all required here, not optional extras: the
    shop cannot deliver an order or tell anyone about it otherwise. Asking at
    sign-up means checkout can be prefilled from the profile the very first
    time, instead of stopping a new customer to collect details mid-purchase.

    The password is write-only and is run through Django's configured
    password validators (length, common passwords, all-numeric).
    """

    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        validators=[validate_password],
    )
    email = serializers.EmailField()
    phone = serializers.CharField(
        max_length=30, write_only=True, validators=[validate_phone]
    )
    address = serializers.CharField(
        max_length=500, write_only=True, validators=[validate_address]
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "phone", "address", "password"]

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is already taken.")
        return value

    def validate_email(self, value):
        return unique_email(value)

    def create(self, validated_data):
        # Note there is no `role` field on this serializer: public
        # registration always produces a customer. Organization accounts are
        # created by an organization admin, never by self-service.
        # create_user hashes the password; User.objects.create() would not.
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"].strip(),
            password=validated_data["password"],
        )
        # The profile already exists — the post_save signal made it — so this
        # fills it in rather than creating a second one.
        profile = profile_for(user)
        profile.phone = validated_data["phone"].strip()
        profile.address = validated_data["address"].strip()
        profile.save(update_fields=["phone", "address", "updated_at"])
        return user


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
