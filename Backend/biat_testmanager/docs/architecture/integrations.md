# Integrations Foundation

Batch 7 makes integrations first-class non-AI product features.

## Responsibilities

- `IntegrationConfig` stores shared team settings and optional project overrides.
- `UserIntegrationCredential` stores acting-as-user credentials separately from profile metadata.
- `RepositoryBinding` links a project to an external repository such as GitHub.
- `WebhookEvent` durably records webhook deliveries before any downstream processing.
- `ExternalIssueLink` links Jira/GitHub issues to project-owned domain objects.
- `IntegrationActionLog` records external integration operations as append-only audit data.

## Rules

- Integration records are scoped by team or project boundaries.
- Personal credentials are never returned by API serializers.
- Webhook ingestion requires an HMAC-SHA256 signature and stores only verified deliveries.
- Webhook list endpoints do not return payloads by default.
- Agent/MCP access is not part of this layer. Future agents may use these records, but they must not replace them.
- `IntegrationActionLog` currently records user-driven/system-driven actions. Agent foreign keys should be added only when the agents app exists.

## Provider Config Shapes

Team and project integration config is stored in encrypted JSON. Expected v1 keys:

- Jira: `base_url`, `project_key`, `webhook_secret`
- GitHub: `org`, `repo`, `webhook_secret`
- Jenkins: `url`, `webhook_secret`

Credentials are separate from config records and must never be returned by API responses.

Webhook signature headers:

- GitHub: `X-Hub-Signature-256`
- Jira/Jenkins: `X-BIAT-Signature-256`

The signature value is `sha256=<hmac_hex_digest>` over the raw request body using the configured `webhook_secret`.

## Current API Workflows

- Configure team integration settings.
- Configure project integration overrides.
- Store the current user's integration credential.
- Bind a project to a repository.
- Ingest GitHub/Jenkins-style webhook events.
- Link external issues to project-owned objects.
- List integration action logs without exposing large request/response payloads.
