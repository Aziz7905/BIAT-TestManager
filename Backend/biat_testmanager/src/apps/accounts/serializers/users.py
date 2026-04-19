# apps/accounts/serializers/users.py
from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.models import (
    OrganizationRole,
    Team,
    TeamMembership,
    TeamMembershipRole,
    UserProfile,
)
from apps.accounts.serializers.profiles import UserProfileSerializer
from apps.accounts.services.access import get_managed_team_ids_for_user
from apps.accounts.services.memberships import (
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
    team_membership_role = serializers.ChoiceField(choices=TeamMembershipRole.choices, required=False)
    organization_role = serializers.ChoiceField(
        choices=OrganizationRole.choices,
        required=False,
    )
    is_staff = serializers.BooleanField(default=False)

    def validate(self, attrs):
        request = self.context["request"]
        requester = request.user
        requester_profile = getattr(requester, "profile", None)
        requester_organization_role = getattr(
            requester_profile,
            "organization_role",
            None,
        )
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
                requester_organization_role == OrganizationRole.ORG_ADMIN
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

        membership_role = attrs.get("team_membership_role")
        if membership_role is None and "organization_role" not in attrs and team:
            membership_role = TeamMembershipRole.TESTER

        resolved_organization_role = attrs.get("organization_role") or OrganizationRole.MEMBER

        if resolved_organization_role == OrganizationRole.PLATFORM_OWNER:
            raise serializers.ValidationError(
                {"organization_role": "Platform owner cannot be created from this endpoint."}
            )

        if membership_role and not team:
            raise serializers.ValidationError(
                {"team": "A team is required for team-level roles."}
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
        attrs["resolved_organization_role"] = resolved_organization_role
        attrs["membership_role"] = membership_role
        return attrs

    def create(self, validated_data):
        team = validated_data.get("team_obj")
        organization = validated_data["target_organization"]
        organization_role = validated_data["resolved_organization_role"]
        membership_role = validated_data["membership_role"]
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

        UserProfile.objects.create(
            user=user,
            organization=organization,
            primary_team=team,
            organization_role=organization_role,
        )

        if team and membership_role:
            upsert_team_membership(
                user,
                team,
                membership_role,
                is_primary=True,
            )
        elif team is None:
            sync_user_profile_team_from_memberships(user)

        return user


class AdminUpdateUserSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    team = serializers.UUIDField(required=False, allow_null=True)
    team_membership_role = serializers.ChoiceField(choices=TeamMembershipRole.choices, required=False)
    organization_role = serializers.ChoiceField(
        choices=OrganizationRole.choices,
        required=False,
    )
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
        requester_organization_role = getattr(
            requester_profile,
            "organization_role",
            None,
        )

        instance = self.instance
        profile = getattr(instance, "profile", None)

        first_name = attrs.get("first_name", instance.first_name).strip()
        last_name = attrs.get("last_name", instance.last_name).strip()

        current_organization = profile.organization if profile else None
        team_obj = serializers.empty
        if "team" in attrs:
            if attrs["team"] is None:
                team_obj = None
            else:
                try:
                    team_obj = Team.objects.select_related("organization").get(
                        id=attrs["team"]
                    )
                except Team.DoesNotExist as exc:
                    raise serializers.ValidationError(
                        {"team": "Selected team does not exist."}
                    ) from exc

                if (
                    requester_organization_role == OrganizationRole.ORG_ADMIN
                    and requester_profile.organization_id != team_obj.organization_id
                ):
                    raise serializers.ValidationError(
                        {
                            "team": "You can only assign users to teams in your organization."
                        }
                    )

                current_organization = team_obj.organization

        membership_role = attrs.get("team_membership_role")
        resolved_organization_role = attrs.get("organization_role") or getattr(
            profile,
            "organization_role",
            OrganizationRole.MEMBER,
        )

        if resolved_organization_role == OrganizationRole.PLATFORM_OWNER:
            raise serializers.ValidationError(
                {"organization_role": "Platform owner cannot be assigned from this endpoint."}
            )

        target_team = None
        if team_obj is serializers.empty:
            target_team = getattr(profile, "primary_team", None)
        else:
            target_team = team_obj

        if membership_role and target_team is None:
            raise serializers.ValidationError(
                {"team": "A team is required for team-level roles."}
            )

        if (
            requester_organization_role == OrganizationRole.MEMBER
            and get_managed_team_ids_for_user(requester)
        ):
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

            if profile.organization_role != OrganizationRole.MEMBER:
                raise serializers.ValidationError(
                    {"detail": "You can only manage organization members."}
                )

            if (
                team_obj not in {serializers.empty, None}
                and team_obj.id not in managed_team_ids
            ):
                raise serializers.ValidationError(
                    {"team": "You can only assign users inside your managed teams."}
                )

            if membership_role not in {
                None,
                TeamMembershipRole.TESTER,
                TeamMembershipRole.VIEWER,
            }:
                raise serializers.ValidationError(
                    {"role": "You can only assign tester or viewer roles."}
                )

            if resolved_organization_role != OrganizationRole.MEMBER:
                raise serializers.ValidationError(
                    {"organization_role": "You can only manage organization members."}
                )

            attrs["managed_team_ids"] = managed_team_ids

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
        attrs["resolved_organization_role"] = resolved_organization_role
        attrs["membership_role"] = membership_role
        return attrs

    def update(self, instance, validated_data):
        profile = getattr(instance, "profile", None)
        requester = self.context["request"].user
        requester_profile = getattr(requester, "profile", None)
        requester_organization_role = getattr(
            requester_profile,
            "organization_role",
            None,
        )

        first_name = validated_data["clean_first_name"]
        last_name = validated_data["clean_last_name"]
        team_obj = validated_data.get("team_obj", serializers.empty)
        target_organization = validated_data.get("target_organization")
        resolved_organization_role = validated_data["resolved_organization_role"]
        membership_role = validated_data["membership_role"]

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
            update_fields: list[str] = []

            if team_obj is not serializers.empty:
                profile.primary_team = team_obj
                if team_obj is not None:
                    profile.organization = team_obj.organization
                update_fields.extend(["primary_team", "organization"])

            if profile.organization_role != resolved_organization_role:
                profile.organization_role = resolved_organization_role
                update_fields.append("organization_role")

            if update_fields:
                profile.save(update_fields=update_fields)

            if (
                requester_organization_role == OrganizationRole.MEMBER
                and get_managed_team_ids_for_user(requester)
            ):
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

                    if team_obj not in {serializers.empty, None} and team_obj.id in managed_team_ids:
                        upsert_team_membership(
                            instance,
                            team_obj,
                            membership_role,
                            is_primary=False,
                        )
            elif membership_role:
                if membership_role in {
                    TeamMembershipRole.TESTER,
                    TeamMembershipRole.VIEWER,
                }:
                    TeamMembership.objects.filter(
                        user=instance,
                        is_active=True,
                    ).exclude(role=TeamMembershipRole.MANAGER).update(
                        role=membership_role
                    )

                target_team = (
                    team_obj
                    if team_obj is not serializers.empty
                    else profile.primary_team
                )
                if target_team is not None:
                    upsert_team_membership(
                        instance,
                        target_team,
                        membership_role,
                        is_primary=True,
                    )
            elif team_obj is serializers.empty:
                sync_user_profile_team_from_memberships(instance)

        if "is_staff" in validated_data:
            instance.is_staff = validated_data["is_staff"]

        if "password" in validated_data and validated_data["password"]:
            instance.set_password(validated_data["password"])

        instance.save()
        return instance
