# apps/accounts/serializers/users.py
import uuid

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.models import (
    Team,
    TeamMembership,
    TeamMembershipRole,
    UserProfile,
    UserProfileRole,
)
from apps.accounts.serializers.profiles import UserProfileSerializer
from apps.accounts.services.access import get_managed_team_ids_for_user
from apps.accounts.services.memberships import (
    map_profile_role_to_membership_role,
    sync_user_profile_team_from_memberships,
    upsert_team_membership,
)
from apps.accounts.services.user_identity import (
    build_unique_username,
    generate_org_email,
    update_user_identity_from_name,
)
from apps.accounts.services.validation import validate_generated_email_is_available

User = get_user_model()
PASSWORD_MIN_LENGTH = 8


class CurrentUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "is_superuser",
            "profile",
        ]


class AdminUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "is_superuser",
            "profile",
            "date_joined",
        ]


class AdminCreateUserSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=PASSWORD_MIN_LENGTH)
    team = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=UserProfileRole.choices, required=False)
    is_staff = serializers.BooleanField(default=False)

    def validate(self, attrs):
        request = self.context["request"]
        requester = request.user
        requester_profile = getattr(requester, "profile", None)
        requester_role = getattr(requester_profile, "role", None)
        team = None
        organization = None

        team_id = attrs.get("team")

        if team_id:
            try:
                parsed_team_id = uuid.UUID(str(team_id))
                team = Team.objects.select_related("organization").get(id=parsed_team_id)
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    {"team": "Selected team is not a valid UUID."}
                )
            except Team.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"team": "Selected team does not exist."}
                ) from exc

            if (
                requester_role == UserProfileRole.ORG_ADMIN
                and requester_profile.organization_id != team.organization_id
            ):
                raise serializers.ValidationError(
                    {"team": "You can only assign users to teams in your organization."}
                )
            organization = team.organization
        else:
            organization = getattr(requester_profile, "organization", None)

        if organization is None:
            raise serializers.ValidationError(
                {"team": "Team is required when the organization cannot be inferred."}
            )

        role = attrs.get("role", UserProfileRole.TESTER)

        if role == UserProfileRole.PLATFORM_OWNER:
            raise serializers.ValidationError(
                {"role": "Platform owner cannot be created from this endpoint."}
            )

        first_name = attrs["first_name"].strip()
        last_name = attrs["last_name"].strip()

        validate_generated_email_is_available(
            first_name=first_name,
            last_name=last_name,
            organization=organization,
        )

        attrs["clean_first_name"] = first_name
        attrs["clean_last_name"] = last_name
        attrs["team_obj"] = team
        attrs["target_organization"] = organization
        attrs["role"] = role
        return attrs

    def create(self, validated_data):
        team = validated_data.get("team_obj")
        organization = validated_data["target_organization"]
        role = validated_data["role"]
        password = validated_data["password"]
        is_staff = validated_data.get("is_staff", False)

        first_name = validated_data["clean_first_name"]
        last_name = validated_data["clean_last_name"]

        email = generate_org_email(first_name, last_name, organization)
        base_username = email.split("@")[0]
        username = build_unique_username(base_username)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_staff=is_staff,
        )

        profile = UserProfile.objects.create(
            user=user,
            organization=organization,
            team=team,
            role=role,
        )

        membership_role = map_profile_role_to_membership_role(role)
        if team and membership_role:
            upsert_team_membership(
                user,
                team,
                membership_role,
                is_primary=True,
            )
        else:
            sync_user_profile_team_from_memberships(user)

        return user


class AdminUpdateUserSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    team = serializers.UUIDField(required=False)
    role = serializers.ChoiceField(choices=UserProfileRole.choices, required=False)
    is_staff = serializers.BooleanField(required=False)
    password = serializers.CharField(
        write_only=True,
        required=False,
        min_length=PASSWORD_MIN_LENGTH,
    )

    def validate(self, attrs):
        request = self.context["request"]
        requester = request.user
        requester_profile = getattr(requester, "profile", None)
        requester_role = getattr(requester_profile, "role", None)

        instance = self.instance
        profile = getattr(instance, "profile", None)

        first_name = attrs.get("first_name", instance.first_name).strip()
        last_name = attrs.get("last_name", instance.last_name).strip()

        if profile and profile.organization:
            current_organization = profile.organization
        else:
            current_organization = None

        team_obj = None
        if "team" in attrs:
            try:
                team_obj = Team.objects.select_related("organization").get(id=attrs["team"])
            except Team.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"team": "Selected team does not exist."}
                ) from exc

            if (
                requester_role == UserProfileRole.ORG_ADMIN
                and requester_profile.organization_id != team_obj.organization_id
            ):
                raise serializers.ValidationError(
                    {"team": "You can only assign users to teams in your organization."}
                )

            current_organization = team_obj.organization

        if requester_role == UserProfileRole.TEAM_MANAGER:
            managed_team_ids = get_managed_team_ids_for_user(requester)

            if (
                profile is None
                or not managed_team_ids
                or not TeamMembership.objects.filter(
                    user=instance,
                    team_id__in=managed_team_ids,
                    is_active=True,
                ).exists()
            ):
                raise serializers.ValidationError(
                    {"detail": "You can only manage users in your managed teams."}
                )

            if profile.role not in {
                UserProfileRole.TESTER,
                UserProfileRole.VIEWER,
            }:
                raise serializers.ValidationError(
                    {"detail": "You can only manage tester and viewer accounts."}
                )

            if team_obj is not None and team_obj.id not in managed_team_ids:
                raise serializers.ValidationError(
                    {"team": "You can only assign users inside your managed teams."}
                )

            if (
                "role" in attrs
                and attrs["role"] not in {
                    UserProfileRole.TESTER,
                    UserProfileRole.VIEWER,
                }
            ):
                raise serializers.ValidationError(
                    {"role": "You can only assign tester or viewer roles."}
                )

            attrs["managed_team_ids"] = managed_team_ids

        if attrs.get("role") == UserProfileRole.PLATFORM_OWNER:
            raise serializers.ValidationError(
                {"role": "Platform owner cannot be assigned from this endpoint."}
            )

        if current_organization:
            validate_generated_email_is_available(
                first_name=first_name,
                last_name=last_name,
                organization=current_organization,
                exclude_user_id=instance.id,
            )

        attrs["clean_first_name"] = first_name
        attrs["clean_last_name"] = last_name
        attrs["team_obj"] = team_obj
        attrs["target_organization"] = current_organization
        return attrs

    def update(self, instance, validated_data):
        profile = getattr(instance, "profile", None)
        requester = self.context["request"].user
        requester_role = getattr(getattr(requester, "profile", None), "role", None)

        first_name = validated_data["clean_first_name"]
        last_name = validated_data["clean_last_name"]
        team_obj = validated_data.get("team_obj")
        target_organization = validated_data.get("target_organization")

        if target_organization:
            update_user_identity_from_name(
                user=instance,
                organization=target_organization,
                first_name=first_name,
                last_name=last_name,
            )
        else:
            instance.first_name = first_name
            instance.last_name = last_name
            instance.save(update_fields=["first_name", "last_name"])

        if profile:
            update_fields = []

            if team_obj is not None:
                profile.team = team_obj
                profile.organization = team_obj.organization
                update_fields.extend(["team", "organization"])

            if "role" in validated_data:
                profile.role = validated_data["role"]
                update_fields.append("role")

            if update_fields:
                profile.save(update_fields=update_fields)

            membership_role = map_profile_role_to_membership_role(profile.role)

            if requester_role == UserProfileRole.TEAM_MANAGER:
                managed_team_ids = validated_data.get("managed_team_ids", [])
                if membership_role in {
                    TeamMembershipRole.TESTER,
                    TeamMembershipRole.VIEWER,
                }:
                    TeamMembership.objects.filter(
                        user=instance,
                        team_id__in=managed_team_ids,
                        is_active=True,
                    ).update(role=membership_role)

                    if team_obj is not None and team_obj.id in managed_team_ids:
                        upsert_team_membership(
                            instance,
                            team_obj,
                            membership_role,
                            is_primary=False,
                        )

            elif membership_role:
                if (
                    membership_role in {
                        TeamMembershipRole.TESTER,
                        TeamMembershipRole.VIEWER,
                    }
                ):
                    TeamMembership.objects.filter(
                        user=instance,
                        is_active=True,
                    ).exclude(role=TeamMembershipRole.MANAGER).update(
                        role=membership_role
                    )

                target_team = team_obj or profile.team
                if target_team is not None:
                    upsert_team_membership(
                        instance,
                        target_team,
                        membership_role,
                        is_primary=True,
                    )
            else:
                sync_user_profile_team_from_memberships(instance)

        if "is_staff" in validated_data:
            instance.is_staff = validated_data["is_staff"]

        if "password" in validated_data and validated_data["password"]:
            instance.set_password(validated_data["password"])

        instance.save()
        return instance
