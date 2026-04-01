from django.contrib.auth import get_user_model

from apps.accounts.models import Organization, build_org_email

User = get_user_model()


def generate_org_email(first_name: str, last_name: str, organization: Organization) -> str:
    return build_org_email(first_name, last_name, organization.domain)


def build_unique_username(base_username: str) -> str:
    username = base_username
    suffix = 1

    while User.objects.filter(username__iexact=username).exists():
        username = f"{base_username}{suffix}"
        suffix += 1

    return username


def update_user_identity_from_name(
    user: User, # type: ignore
    organization: Organization,
    first_name: str,
    last_name: str,
) -> User: # type: ignore
    clean_first_name = first_name.strip()
    clean_last_name = last_name.strip()

    expected_email = generate_org_email(
        clean_first_name,
        clean_last_name,
        organization,
    )

    current_username = user.username or ""
    current_username_local = current_username.split("@")[0]

    regenerated_local = expected_email.split("@")[0]
    if current_username_local != regenerated_local:
        username = build_unique_username(regenerated_local)
    else:
        username = current_username

    user.first_name = clean_first_name
    user.last_name = clean_last_name
    user.email = expected_email
    user.username = username
    user.save(update_fields=["first_name", "last_name", "email", "username"])

    return user