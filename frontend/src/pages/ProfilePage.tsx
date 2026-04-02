/** Profile workspace updated to use the shared brand surfaces and spacing system. */
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  changeMyPassword,
  getMyProfile,
  updateMyProfile,
} from "../api/accounts/profile";
import { Button } from "../components/Button";
import { ErrorMessage } from "../components/ErrorMessage";
import { FormInput } from "../components/FormInput";
import { FormSelect } from "../components/FormSelect";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { Badge } from "../components/ui";
import { useAuthStore } from "../store/authStore";
import type {
  ChangePasswordPayload,
  MyProfile,
  NotificationProvider,
  UpdateMyProfilePayload,
} from "../types/accounts";

function getErrorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof (error as { response?: unknown }).response === "object"
  ) {
    const response = (error as {
      response?: { data?: { detail?: string; error?: string } };
    }).response;

    return response?.data?.detail || response?.data?.error || fallback;
  }

  return fallback;
}

const initialProfileForm: UpdateMyProfilePayload = {
  first_name: "",
  last_name: "",
  jira_token: "",
  github_token: "",
  notification_provider: "none",
  slack_user_id: "",
  slack_username: "",
  teams_user_id: "",
  notifications_enabled: true,
};

const initialPasswordForm: ChangePasswordPayload = {
  current_password: "",
  new_password: "",
  confirm_new_password: "",
};

const notificationProviderOptions = [
  { value: "none", label: "None" },
  { value: "slack", label: "Slack" },
  { value: "teams", label: "Microsoft Teams" },
];

export default function ProfilePage() {
  const { initializeAuth } = useAuthStore();

  const [profile, setProfile] = useState<MyProfile | null>(null);
  const [profileForm, setProfileForm] =
    useState<UpdateMyProfilePayload>(initialProfileForm);
  const [passwordForm, setPasswordForm] =
    useState<ChangePasswordPayload>(initialPasswordForm);

  const [isLoading, setIsLoading] = useState(true);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isSavingPassword, setIsSavingPassword] = useState(false);

  const [profileErrorMessage, setProfileErrorMessage] = useState("");
  const [profileSuccessMessage, setProfileSuccessMessage] = useState("");
  const [passwordErrorMessage, setPasswordErrorMessage] = useState("");
  const [passwordSuccessMessage, setPasswordSuccessMessage] = useState("");

  const loadProfile = async (): Promise<void> => {
    try {
      setIsLoading(true);
      setProfileErrorMessage("");

      const profileData = await getMyProfile();

      setProfile(profileData);
      setProfileForm({
        first_name: profileData.first_name,
        last_name: profileData.last_name,
        jira_token: "",
        github_token: "",
        notification_provider: profileData.notification_provider,
        slack_user_id: profileData.slack_user_id ?? "",
        slack_username: profileData.slack_username ?? "",
        teams_user_id: profileData.teams_user_id ?? "",
        notifications_enabled: profileData.notifications_enabled,
      });
    } catch (error: unknown) {
      setProfileErrorMessage(
        getErrorMessage(error, "Failed to load profile.")
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadProfile();
  }, []);

  const handleProfileSubmit = async (
    event: FormEvent<HTMLFormElement>
  ): Promise<void> => {
    event.preventDefault();

    try {
      setIsSavingProfile(true);
      setProfileErrorMessage("");
      setProfileSuccessMessage("");

      const updatedProfile = await updateMyProfile({
        first_name: profileForm.first_name?.trim() || undefined,
        last_name: profileForm.last_name?.trim() || undefined,
        jira_token: profileForm.jira_token?.trim()
          ? profileForm.jira_token.trim()
          : null,
        github_token: profileForm.github_token?.trim()
          ? profileForm.github_token.trim()
          : null,
        notification_provider: profileForm.notification_provider,
        slack_user_id: profileForm.slack_user_id?.trim()
          ? profileForm.slack_user_id.trim()
          : null,
        slack_username: profileForm.slack_username?.trim()
          ? profileForm.slack_username.trim()
          : null,
        teams_user_id: profileForm.teams_user_id?.trim()
          ? profileForm.teams_user_id.trim()
          : null,
        notifications_enabled: profileForm.notifications_enabled,
      });

      setProfile(updatedProfile);
      setProfileSuccessMessage("Profile updated successfully.");
      await initializeAuth();

      setProfileForm((previousForm) => ({
        ...previousForm,
        jira_token: "",
        github_token: "",
      }));
    } catch (error: unknown) {
      setProfileErrorMessage(
        getErrorMessage(error, "Failed to update profile.")
      );
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handlePasswordSubmit = async (
    event: FormEvent<HTMLFormElement>
  ): Promise<void> => {
    event.preventDefault();

    try {
      setIsSavingPassword(true);
      setPasswordErrorMessage("");
      setPasswordSuccessMessage("");

      await changeMyPassword(passwordForm);

      setPasswordSuccessMessage("Password updated successfully.");
      setPasswordForm(initialPasswordForm);
    } catch (error: unknown) {
      setPasswordErrorMessage(
        getErrorMessage(error, "Failed to update password.")
      );
    } finally {
      setIsSavingPassword(false);
    }
  };

  const handleNotificationProviderChange = (
    provider: NotificationProvider
  ): void => {
    setProfileForm((previousForm) => {
      if (provider === "none") {
        return {
          ...previousForm,
          notification_provider: provider,
          slack_user_id: "",
          slack_username: "",
          teams_user_id: "",
        };
      }

      if (provider === "slack") {
        return {
          ...previousForm,
          notification_provider: provider,
          teams_user_id: "",
        };
      }

      return {
        ...previousForm,
        notification_provider: provider,
        slack_user_id: "",
        slack_username: "",
      };
    });
  };

  const jiraTokenPlaceholder = profile?.has_jira_token
    ? "Enter a new Jira token to replace the current one"
    : "Enter Jira token";

  const githubTokenPlaceholder = profile?.has_github_token
    ? "Enter a new GitHub token to replace the current one"
    : "Enter GitHub token";

  if (isLoading) {
    return (
      <div className="flex min-h-[220px] items-center justify-center rounded-[28px] border border-border bg-surface shadow-sm">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Badge variant="tag">Account workspace</Badge>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-text">My Profile</h1>
        <p className="mt-2 text-sm leading-6 text-muted">
          Update your account details, integrations, and notification settings.
        </p>
      </div>

      <div className="space-y-6">
        <section className="rounded-[28px] border border-border bg-surface p-6 shadow-panel">
          <h2 className="mb-4 text-lg font-semibold tracking-tight text-text">Account</h2>

          {profileSuccessMessage ? (
            <div className="mb-4 rounded-2xl border border-status-verified-text/15 bg-status-verified-bg px-4 py-3 text-sm text-status-verified-text shadow-sm">
              {profileSuccessMessage}
            </div>
          ) : null}

          {profileErrorMessage ? (
            <ErrorMessage
              message={profileErrorMessage}
              onDismiss={() => setProfileErrorMessage("")}
              className="mb-4"
            />
          ) : null}

          <form onSubmit={handleProfileSubmit} className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <FormInput
                id="profile-first-name"
                label="First name"
                type="text"
                value={profileForm.first_name ?? ""}
                onChange={(event) =>
                  setProfileForm((previousForm) => ({
                    ...previousForm,
                    first_name: event.target.value,
                  }))
                }
                required
              />

              <FormInput
                id="profile-last-name"
                label="Last name"
                type="text"
                value={profileForm.last_name ?? ""}
                onChange={(event) =>
                  setProfileForm((previousForm) => ({
                    ...previousForm,
                    last_name: event.target.value,
                  }))
                }
                required
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <FormInput
                id="profile-email"
                label="Email"
                type="text"
                value={profile?.email ?? ""}
                disabled
              />

              <FormInput
                id="profile-role"
                label="Role"
                type="text"
                value={profile?.role ?? ""}
                disabled
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <FormInput
                id="profile-organization"
                label="Organization"
                type="text"
                value={profile?.organization_name ?? ""}
                disabled
              />

              <FormInput
                id="profile-team"
                label="Teams"
                type="text"
                value={
                  profile?.team_memberships?.length
                    ? profile.team_memberships
                        .map((membership) => membership.team_name)
                        .join(", ")
                    : profile?.team_name ?? "No team assigned"
                }
                disabled
              />
            </div>

            <div>
              <h3 className="mb-4 text-base font-semibold tracking-tight text-text">
                Integrations
              </h3>

              <div className="grid gap-4 md:grid-cols-2">
                <FormInput
                  id="profile-jira-token"
                  label="Jira token"
                  type="password"
                  value={profileForm.jira_token ?? ""}
                  onChange={(event) =>
                    setProfileForm((previousForm) => ({
                      ...previousForm,
                      jira_token: event.target.value,
                    }))
                  }
                  placeholder={jiraTokenPlaceholder}
                />

                <FormInput
                  id="profile-github-token"
                  label="GitHub token"
                  type="password"
                  value={profileForm.github_token ?? ""}
                  onChange={(event) =>
                    setProfileForm((previousForm) => ({
                      ...previousForm,
                      github_token: event.target.value,
                    }))
                  }
                  placeholder={githubTokenPlaceholder}
                />
              </div>
            </div>

            <div>
              <h3 className="mb-4 text-base font-semibold tracking-tight text-text">
                Notifications
              </h3>

              <div className="grid gap-4 md:grid-cols-2">
                <FormSelect
                  id="profile-notification-provider"
                  label="Notification provider"
                  value={profileForm.notification_provider ?? "none"}
                  onChange={(event) =>
                    handleNotificationProviderChange(
                      event.target.value as NotificationProvider
                    )
                  }
                  options={notificationProviderOptions}
                />

                <div className="flex items-end">
                  <label className="flex items-center gap-2 text-sm text-text">
                    <input
                      type="checkbox"
                      checked={Boolean(profileForm.notifications_enabled)}
                      onChange={(event) =>
                        setProfileForm((previousForm) => ({
                          ...previousForm,
                          notifications_enabled: event.target.checked,
                        }))
                      }
                      className="h-4 w-4"
                    />
                    Notifications enabled
                  </label>
                </div>
              </div>

              {profileForm.notification_provider === "slack" ? (
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <FormInput
                    id="profile-slack-user-id"
                    label="Slack user ID"
                    type="text"
                    value={profileForm.slack_user_id ?? ""}
                    onChange={(event) =>
                      setProfileForm((previousForm) => ({
                        ...previousForm,
                        slack_user_id: event.target.value,
                      }))
                    }
                    placeholder="U12345678"
                  />

                  <FormInput
                    id="profile-slack-username"
                    label="Slack username"
                    type="text"
                    value={profileForm.slack_username ?? ""}
                    onChange={(event) =>
                      setProfileForm((previousForm) => ({
                        ...previousForm,
                        slack_username: event.target.value,
                      }))
                    }
                    placeholder="@name.surname"
                  />
                </div>
              ) : null}

              {profileForm.notification_provider === "teams" ? (
                <div className="mt-4">
                  <FormInput
                    id="profile-teams-user-id"
                    label="Microsoft Teams user ID"
                    type="text"
                    value={profileForm.teams_user_id ?? ""}
                    onChange={(event) =>
                      setProfileForm((previousForm) => ({
                        ...previousForm,
                        teams_user_id: event.target.value,
                      }))
                    }
                    placeholder="Teams user ID"
                  />
                </div>
              ) : null}
            </div>

            <div className="flex justify-end">
              <Button
                type="submit"
                isLoading={isSavingProfile}
                loadingText="Saving..."
              >
                Save changes
              </Button>
            </div>
          </form>
        </section>

        <section className="rounded-[28px] border border-border bg-surface p-6 shadow-panel">
          <h2 className="mb-4 text-lg font-semibold tracking-tight text-text">
            Change Password
          </h2>

          {passwordSuccessMessage ? (
            <div className="mb-4 rounded-2xl border border-status-verified-text/15 bg-status-verified-bg px-4 py-3 text-sm text-status-verified-text shadow-sm">
              {passwordSuccessMessage}
            </div>
          ) : null}

          {passwordErrorMessage ? (
            <ErrorMessage
              message={passwordErrorMessage}
              onDismiss={() => setPasswordErrorMessage("")}
              className="mb-4"
            />
          ) : null}

          <form onSubmit={handlePasswordSubmit}>
            <div className="grid gap-4">
              <FormInput
                id="current-password"
                label="Current password"
                type="password"
                value={passwordForm.current_password}
                onChange={(event) =>
                  setPasswordForm((previousForm) => ({
                    ...previousForm,
                    current_password: event.target.value,
                  }))
                }
                required
              />

              <FormInput
                id="new-password"
                label="New password"
                type="password"
                value={passwordForm.new_password}
                onChange={(event) =>
                  setPasswordForm((previousForm) => ({
                    ...previousForm,
                    new_password: event.target.value,
                  }))
                }
                required
              />

              <FormInput
                id="confirm-new-password"
                label="Confirm new password"
                type="password"
                value={passwordForm.confirm_new_password}
                onChange={(event) =>
                  setPasswordForm((previousForm) => ({
                    ...previousForm,
                    confirm_new_password: event.target.value,
                  }))
                }
                required
              />
            </div>

            <div className="mt-6 flex justify-end">
              <Button
                type="submit"
                isLoading={isSavingPassword}
                loadingText="Updating..."
              >
                Update password
              </Button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}
