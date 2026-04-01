from apps.accounts.models import NotificationProvider, UserProfile


def clear_notification_identifiers(profile: UserProfile) -> UserProfile:
    profile.slack_user_id = None
    profile.slack_username = None
    profile.teams_user_id = None
    return profile


def normalize_notification_provider(provider: str | None) -> str:
    if provider in {
        NotificationProvider.SLACK,
        NotificationProvider.TEAMS,
        NotificationProvider.NONE,
    }:
        return provider

    return NotificationProvider.NONE