import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import AppLayout from "../components/layout/AppLayout";
import { Badge, Button, ErrorMessage, Input, PageHeader, Spinner } from "../components/ui";
import { getMyProfile, updateMyProfile, changeMyPassword } from "../api/accounts/profile";
import { useAuthStore } from "../store/authStore";
import type { MyProfile, NotificationProvider, UpdateProfilePayload } from "../types/accounts";

function roleBadge(role: MyProfile["organization_role"]) {
  const colorMap = {
    platform_owner: "purple",
    org_admin: "blue",
    member: "slate",
  } as const;

  const labelMap = {
    platform_owner: "Platform Owner",
    org_admin: "Org Admin",
    member: "Member",
  } as const;

  return <Badge label={labelMap[role]} color={colorMap[role]} />;
}

function formatMembershipRole(role: string) {
  return role.replaceAll("_", " ");
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-5">
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {children}
    </section>
  );
}

function syncCurrentUserProfile(profile: MyProfile) {
  const currentUser = useAuthStore.getState().user;
  if (!currentUser) {
    return;
  }

  useAuthStore.setState({
    user: {
      ...currentUser,
      first_name: profile.first_name,
      last_name: profile.last_name,
      email: profile.email,
      profile: {
        ...currentUser.profile,
        id: profile.id,
        organization: profile.organization,
        organization_name: profile.organization_name,
        organization_role: profile.organization_role,
        team: profile.team,
        team_name: profile.team_name,
        team_memberships: profile.team_memberships,
        notification_provider: profile.notification_provider,
        notifications_enabled: profile.notifications_enabled,
        created_at: profile.created_at,
      },
    },
  });
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<MyProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [savingInfo, setSavingInfo] = useState(false);

  const [jiraToken, setJiraToken] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [savingIntegrations, setSavingIntegrations] = useState(false);

  const [provider, setProvider] = useState<NotificationProvider>("none");
  const [notificationsEnabled, setNotificationsEnabled] = useState(false);
  const [slackUserId, setSlackUserId] = useState("");
  const [slackUsername, setSlackUsername] = useState("");
  const [teamsUserId, setTeamsUserId] = useState("");
  const [savingNotifications, setSavingNotifications] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  useEffect(() => {
    getMyProfile()
      .then((loadedProfile) => {
        setProfile(loadedProfile);
        setFirstName(loadedProfile.first_name);
        setLastName(loadedProfile.last_name);
        setProvider(loadedProfile.notification_provider);
        setNotificationsEnabled(loadedProfile.notifications_enabled);
        setSlackUserId(loadedProfile.slack_user_id ?? "");
        setSlackUsername(loadedProfile.slack_username ?? "");
        setTeamsUserId(loadedProfile.teams_user_id ?? "");
        syncCurrentUserProfile(loadedProfile);
      })
      .catch(() => setError("Failed to load profile."))
      .finally(() => setLoading(false));
  }, []);

  async function savePersonalInfo() {
    setSavingInfo(true);
    setError("");

    try {
      const updatedProfile = await updateMyProfile({
        first_name: firstName,
        last_name: lastName,
      });
      setProfile(updatedProfile);
      syncCurrentUserProfile(updatedProfile);
    } catch {
      setError("Failed to save personal information.");
    } finally {
      setSavingInfo(false);
    }
  }

  async function saveIntegrations() {
    setSavingIntegrations(true);
    setError("");

    const payload: UpdateProfilePayload = {};
    if (jiraToken) {
      payload.jira_token = jiraToken;
    }
    if (githubToken) {
      payload.github_token = githubToken;
    }

    try {
      const updatedProfile = await updateMyProfile(payload);
      setProfile(updatedProfile);
      syncCurrentUserProfile(updatedProfile);
      setJiraToken("");
      setGithubToken("");
    } catch {
      setError("Failed to save integration credentials.");
    } finally {
      setSavingIntegrations(false);
    }
  }

  async function saveNotifications() {
    setSavingNotifications(true);
    setError("");

    try {
      const updatedProfile = await updateMyProfile({
        notification_provider: provider,
        notifications_enabled: notificationsEnabled,
        slack_user_id: slackUserId || undefined,
        slack_username: slackUsername || undefined,
        teams_user_id: teamsUserId || undefined,
      });
      setProfile(updatedProfile);
      syncCurrentUserProfile(updatedProfile);
    } catch {
      setError("Failed to save notification settings.");
    } finally {
      setSavingNotifications(false);
    }
  }

  async function handleChangePassword() {
    setError("");
    setPasswordSuccess(false);

    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }

    setSavingPassword(true);
    try {
      await changeMyPassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordSuccess(true);
    } catch {
      setError("Failed to change password. Check your current password.");
    } finally {
      setSavingPassword(false);
    }
  }

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto px-6 py-8">
        <div className="mx-auto max-w-4xl space-y-6">
          <PageHeader
            title="My Profile"
            subtitle="Manage your identity, notifications, and personal credentials."
          />

          {error && <ErrorMessage message={error} onDismiss={() => setError("")} />}

          {loading ? (
            <div className="flex min-h-[50vh] items-center justify-center rounded-lg border border-slate-200 bg-white">
              <Spinner size="lg" />
            </div>
          ) : (
            <>
              <Section title="Personal Information" description="Your account identity inside the workspace.">
                <div className="mb-6 flex flex-wrap items-center gap-4">
                  <span className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-lg font-bold text-blue-700">
                    {profile?.first_name?.[0]}
                    {profile?.last_name?.[0]}
                  </span>
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-900">{profile?.email}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      {profile?.organization_name && (
                        <span className="text-sm text-slate-500">{profile.organization_name}</span>
                      )}
                      {profile?.organization_role && roleBadge(profile.organization_role)}
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <Input
                    id="profile-first-name"
                    label="First name"
                    value={firstName}
                    onChange={(event) => setFirstName(event.target.value)}
                  />
                  <Input
                    id="profile-last-name"
                    label="Last name"
                    value={lastName}
                    onChange={(event) => setLastName(event.target.value)}
                  />
                </div>

                <div className="mt-4 space-y-2 text-sm text-slate-600">
                  <p>
                    Primary team:{" "}
                    <span className="font-medium text-slate-800">{profile?.team_name ?? "Not assigned"}</span>
                  </p>
                  {(profile?.team_memberships.length ?? 0) > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {profile?.team_memberships.map((membership) => (
                        <span
                          key={membership.id}
                          className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600"
                        >
                          {membership.team_name} - {formatMembershipRole(membership.role)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="mt-5">
                  <Button isLoading={savingInfo} loadingText="Saving..." onClick={savePersonalInfo}>
                    Save changes
                  </Button>
                </div>
              </Section>

              <Section title="Personal Credentials" description="These secrets are write-only and never returned by the API.">
                <div className="grid gap-4 md:grid-cols-2">
                  <Input
                    id="profile-jira-token"
                    label={`Jira token${profile?.has_jira_token ? " (set)" : ""}`}
                    type="password"
                    value={jiraToken}
                    onChange={(event) => setJiraToken(event.target.value)}
                    placeholder={profile?.has_jira_token ? "Leave blank to keep current token" : "Enter token"}
                  />
                  <Input
                    id="profile-github-token"
                    label={`GitHub token${profile?.has_github_token ? " (set)" : ""}`}
                    type="password"
                    value={githubToken}
                    onChange={(event) => setGithubToken(event.target.value)}
                    placeholder={profile?.has_github_token ? "Leave blank to keep current token" : "Enter token"}
                  />
                </div>

                <div className="mt-5">
                  <Button isLoading={savingIntegrations} loadingText="Saving..." onClick={saveIntegrations}>
                    Save credentials
                  </Button>
                </div>
              </Section>

              <Section title="Notifications" description="Choose how this account should be notified.">
                <div className="space-y-4">
                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-slate-700">Provider</label>
                    <select
                      value={provider}
                      onChange={(event) => setProvider(event.target.value as NotificationProvider)}
                      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-400"
                    >
                      <option value="none">None</option>
                      <option value="slack">Slack</option>
                      <option value="teams">Microsoft Teams</option>
                    </select>
                  </div>

                  <label className="flex cursor-pointer items-center gap-3">
                    <input
                      type="checkbox"
                      checked={notificationsEnabled}
                      onChange={(event) => setNotificationsEnabled(event.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 accent-blue-600"
                    />
                    <span className="text-sm text-slate-700">Enable notifications</span>
                  </label>

                  {provider === "slack" && (
                    <div className="grid gap-4 md:grid-cols-2">
                      <Input
                        id="profile-slack-user-id"
                        label="Slack user ID"
                        value={slackUserId}
                        onChange={(event) => setSlackUserId(event.target.value)}
                        placeholder="U0123456789"
                      />
                      <Input
                        id="profile-slack-username"
                        label="Slack username"
                        value={slackUsername}
                        onChange={(event) => setSlackUsername(event.target.value)}
                        placeholder="john.doe"
                      />
                    </div>
                  )}

                  {provider === "teams" && (
                    <Input
                      id="profile-teams-user-id"
                      label="Teams user ID"
                      value={teamsUserId}
                      onChange={(event) => setTeamsUserId(event.target.value)}
                      placeholder="user@org.onmicrosoft.com"
                    />
                  )}
                </div>

                <div className="mt-5">
                  <Button isLoading={savingNotifications} loadingText="Saving..." onClick={saveNotifications}>
                    Save notification settings
                  </Button>
                </div>
              </Section>

              <Section title="Change Password" description="Update your password for this account.">
                <div className="grid gap-4 md:grid-cols-3">
                  <Input
                    id="profile-current-password"
                    label="Current password"
                    type="password"
                    value={currentPassword}
                    onChange={(event) => setCurrentPassword(event.target.value)}
                  />
                  <Input
                    id="profile-new-password"
                    label="New password"
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                  />
                  <Input
                    id="profile-confirm-password"
                    label="Confirm new password"
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                  />
                </div>

                {passwordSuccess && (
                  <p className="mt-4 text-sm font-medium text-green-600">
                    Password updated successfully.
                  </p>
                )}

                <div className="mt-5">
                  <Button isLoading={savingPassword} loadingText="Updating..." onClick={handleChangePassword}>
                    Update password
                  </Button>
                </div>
              </Section>
            </>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
