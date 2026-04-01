from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.models import Team, TeamMembership, UserProfileRole
from apps.projects.access import can_manage_project_member_record
from apps.projects.models import Project, ProjectMember, ProjectMemberRole

User = get_user_model()


class ProjectSerializer(serializers.ModelSerializer):
    team = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.select_related("organization").all()
    )
    team_name = serializers.CharField(source="team.name", read_only=True)
    organization = serializers.UUIDField(source="team.organization.id", read_only=True)
    organization_name = serializers.CharField(
        source="team.organization.name",
        read_only=True,
    )
    created_by = serializers.IntegerField(source="created_by.id", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    member_names = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "team",
            "team_name",
            "organization",
            "organization_name",
            "name",
            "description",
            "status",
            "created_by",
            "created_by_name",
            "member_names",
            "member_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "created_by",
            "created_by_name",
            "member_names",
            "member_count",
            "created_at",
            "updated_at",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        full_name = obj.created_by.get_full_name().strip()
        return full_name or obj.created_by.email or obj.created_by.username

    def get_member_names(self, obj):
        return [
            member.user.get_full_name().strip()
            or member.user.email
            or member.user.username
            for member in obj.members.select_related("user").all()
        ]

    def get_member_count(self, obj):
        return obj.members.count()

    def validate(self, attrs):
        request = self.context["request"]
        requester = request.user
        requester_profile = getattr(requester, "profile", None)
        requester_role = getattr(requester_profile, "role", None)
        team = attrs.get("team") or getattr(self.instance, "team", None)

        if team is None:
            raise serializers.ValidationError({"team": "Team is required."})

        if requester_role == UserProfileRole.ORG_ADMIN:
            if requester_profile.organization_id != team.organization_id:
                raise serializers.ValidationError(
                    {"team": "You can only manage projects in your organization."}
                )

        if requester_role == UserProfileRole.TEAM_MANAGER:
            if not TeamMembership.objects.filter(
                user=requester,
                team=team,
                role="manager",
                is_active=True,
            ).exists():
                raise serializers.ValidationError(
                    {"team": "You can only manage projects for teams you manage."}
                )

        if (
            self.instance is not None
            and "team" in attrs
            and team != self.instance.team
            and self.instance.members.exists()
        ):
            raise serializers.ValidationError(
                {
                    "team": "Move or remove the current project members before changing the team."
                }
            )

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        project = Project.objects.create(created_by=request.user, **validated_data)

        if TeamMembership.objects.filter(
            user=request.user,
            team=project.team,
            is_active=True,
        ).exists():
            ProjectMember.objects.get_or_create(
                project=project,
                user=request.user,
                defaults={"role": ProjectMemberRole.OWNER},
            )

        return project

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class ProjectMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    user_role = serializers.CharField(source="user.profile.role", read_only=True)

    class Meta:
        model = ProjectMember
        fields = [
            "id",
            "user_id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "user_role",
            "role",
            "joined_at",
        ]

    def get_full_name(self, obj):
        full_name = obj.user.get_full_name().strip()
        return full_name or obj.user.email or obj.user.username


class ProjectMemberCreateSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.select_related("profile"))
    role = serializers.ChoiceField(choices=ProjectMemberRole.choices)

    def validate(self, attrs):
        project = self.context["project"]
        target_user = attrs["user"]
        target_profile = getattr(target_user, "profile", None)

        if not target_profile:
            raise serializers.ValidationError({"user": "Selected user does not have a profile."})

        if target_profile.organization_id != project.team.organization_id:
            raise serializers.ValidationError(
                {"user": "Selected user must belong to the same organization as the project."}
            )

        if target_profile.role not in {
            UserProfileRole.TEAM_MANAGER,
            UserProfileRole.TESTER,
            UserProfileRole.VIEWER,
        }:
            raise serializers.ValidationError(
                {"user": "Only team members can be assigned to a project."}
            )

        if not TeamMembership.objects.filter(
            user=target_user,
            team=project.team,
            is_active=True,
        ).exists():
            raise serializers.ValidationError(
                {"user": "The selected user must be assigned to the project's team first."}
            )

        if ProjectMember.objects.filter(project=project, user=target_user).exists():
            raise serializers.ValidationError(
                {"user": "This user is already assigned to the selected project."}
            )

        attrs["project"] = project
        return attrs

    def create(self, validated_data):
        return ProjectMember.objects.create(
            project=validated_data["project"],
            user=validated_data["user"],
            role=validated_data["role"],
        )


class ProjectMemberUpdateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=ProjectMemberRole.choices)

    class Meta:
        model = ProjectMember
        fields = ["role"]

    def validate(self, attrs):
        membership = self.instance
        actor = self.context["request"].user

        if not can_manage_project_member_record(actor, membership):
            raise serializers.ValidationError(
                {"detail": "You do not have permission to manage this project member."}
            )

        return attrs
