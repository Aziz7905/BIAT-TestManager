from __future__ import annotations

import sys
import threading
import time
from datetime import timedelta
from pathlib import Path
from unittest import mock

from asgiref.sync import async_to_sync, sync_to_async
from channels.testing.websocket import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.accounts.models import Organization, Team, TeamMembership, UserProfile
from apps.accounts.models.choices import OrganizationRole, TeamMembershipRole
from apps.automation.models import (
    AutomationScript,
    ExecutionCheckpoint,
    TestArtifact,
    TestExecution,
)
from apps.automation.models.choices import (
    ArtifactType,
    AutomationFramework,
    AutomationLanguage,
    ExecutionCheckpointStatus,
    ExecutionStatus,
)
from apps.automation.services import (
    create_execution_record,
    expire_stale_execution_checkpoints,
    issue_execution_stream_ticket,
    publish_execution_status_changed,
    request_execution_stop,
    run_execution,
)
from apps.automation.services.control import ExecutionControlUnavailable
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.testing.models import TestCase as QaTestCase
from apps.testing.models import TestScenario, TestSection, TestSuite

User = get_user_model()
_PASSWORD = "Pass1234!"  # NOSONAR
_IN_MEMORY_CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}


def _make_org_stack(domain_suffix: str, username: str):
    user = User.objects.create_user(
        username=username,
        password=_PASSWORD,
        email=f"{username}@{domain_suffix}",
    )
    org = Organization.objects.create(name=f"Org {domain_suffix}", domain=domain_suffix)
    UserProfile.objects.create(
        user=user,
        organization=org,
        organization_role=OrganizationRole.MEMBER,
    )
    team = Team.objects.create(organization=org, name="QA Team", manager=user)
    TeamMembership.objects.create(
        team=team, user=user, role=TeamMembershipRole.TESTER, is_active=True
    )
    return user, org, team


def _make_project_tree(team, owner):
    project = Project.objects.create(team=team, name="Banking Project", created_by=owner)
    ProjectMember.objects.create(project=project, user=owner, role=ProjectMemberRole.OWNER)
    suite = TestSuite.objects.create(
        project=project,
        name="Smoke Suite",
        folder_path="Smoke",
        created_by=owner,
    )
    section = TestSection.objects.create(suite=suite, name="Core", order_index=0)
    scenario = TestScenario.objects.create(section=section, title="Login flow", description="")
    test_case = QaTestCase.objects.create(
        scenario=scenario,
        title="Login with valid credentials",
        steps=[{"step": "Open login page", "outcome": "Login page appears"}],
        expected_result="User reaches the dashboard.",
    )
    return project, suite, test_case


def _make_script(test_case, script_content: str):
    return AutomationScript.objects.create(
        test_case=test_case,
        framework=AutomationFramework.PLAYWRIGHT,
        language=AutomationLanguage.PYTHON,
        script_content=script_content,
        is_active=True,
    )


@override_settings(
    CHANNEL_LAYERS=_IN_MEMORY_CHANNEL_LAYERS,
    AUTOMATION_PLAYWRIGHT_PYTHON_BIN=sys.executable,
    AUTOMATION_SELENIUM_PYTHON_BIN=sys.executable,
    AUTOMATION_PLAYWRIGHT_WORKDIR=str(Path(__file__).resolve().parents[3]),
    AUTOMATION_SELENIUM_WORKDIR=str(Path(__file__).resolve().parents[3]),
)
class StreamTicketApiTests(APITestCase):
    def setUp(self):
        self.user, self.org, self.team = _make_org_stack("stream-api.tn", "stream.api")
        self.project, _, self.test_case = _make_project_tree(self.team, self.user)
        script = _make_script(self.test_case, "print('ok')")
        self.execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            browser="chromium",
            platform="desktop",
            script=script,
        )
        self.client.force_authenticate(self.user)

    def test_issue_stream_ticket_for_visible_execution(self):
        response = self.client.post(
            reverse("test-execution-stream-ticket", kwargs={"pk": self.execution.id})
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("ticket", response.data)
        self.assertIn(str(self.execution.id), response.data["websocket_path"])
        self.assertIn(str(self.execution.id), response.data["browser_websocket_path"])
        self.assertEqual(response.data["expires_in"], 120)

    def test_hidden_execution_cannot_get_stream_ticket(self):
        outsider, outsider_org, outsider_team = _make_org_stack("outsider.tn", "outsider")
        outsider_project, _, outsider_case = _make_project_tree(outsider_team, outsider)
        outsider_script = _make_script(outsider_case, "print('nope')")
        hidden_execution = create_execution_record(
            test_case=outsider_case,
            triggered_by=outsider,
            browser="chromium",
            platform="desktop",
            script=outsider_script,
        )
        response = self.client.post(
            reverse("test-execution-stream-ticket", kwargs={"pk": hidden_execution.id})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_checkpoint_resume_returns_503_when_control_channel_is_down(self):
        checkpoint = ExecutionCheckpoint.objects.create(
            execution=self.execution,
            checkpoint_key="mfa",
            title="Approve MFA",
            instructions="Approve the browser prompt.",
            status=ExecutionCheckpointStatus.PENDING,
        )

        with mock.patch(
            "apps.automation.services.checkpoints.write_checkpoint_resume_signal",
            side_effect=ExecutionControlUnavailable("down"),
        ):
            response = self.client.post(
                reverse(
                    "execution-checkpoint-resume",
                    kwargs={
                        "execution_pk": self.execution.id,
                        "checkpoint_pk": checkpoint.id,
                    },
                )
            )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


@override_settings(
    CHANNEL_LAYERS=_IN_MEMORY_CHANNEL_LAYERS,
    AUTOMATION_PLAYWRIGHT_PYTHON_BIN=sys.executable,
    AUTOMATION_SELENIUM_PYTHON_BIN=sys.executable,
    AUTOMATION_PLAYWRIGHT_WORKDIR=str(Path(__file__).resolve().parents[3]),
    AUTOMATION_SELENIUM_WORKDIR=str(Path(__file__).resolve().parents[3]),
)
class ExecutionWebSocketTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user, self.org, self.team = _make_org_stack("stream-ws.tn", "stream.ws")
        self.project, _, self.test_case = _make_project_tree(self.team, self.user)
        script = _make_script(self.test_case, "print('ws')")
        self.execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            browser="chromium",
            platform="desktop",
            script=script,
        )

    def _publish_paused_status(self):
        self.execution.status = ExecutionStatus.PAUSED
        self.execution.save(update_fields=["status"])
        publish_execution_status_changed(self.execution)

    async def _connect(self, *, ticket: str):
        from biat_testmanager.asgi import application

        communicator = WebsocketCommunicator(
            application,
            f"/ws/executions/{self.execution.id}/?ticket={ticket}",
            headers=[(b"origin", b"http://localhost:5173")],
        )
        connected, _ = await communicator.connect()
        return communicator, connected

    def test_valid_ticket_receives_snapshot(self):
        async def scenario():
            stream_ticket = issue_execution_stream_ticket(self.execution, self.user)["ticket"]
            communicator, connected = await self._connect(ticket=stream_ticket)
            self.assertTrue(connected)
            try:
                message = await communicator.receive_json_from(timeout=1)
                self.assertEqual(message["type"], "execution.snapshot")
                self.assertEqual(message["execution_id"], str(self.execution.id))
                self.assertIn("execution", message["payload"])
            finally:
                await communicator.disconnect()

        async_to_sync(scenario)()

    def test_invalid_ticket_is_rejected(self):
        async def scenario():
            communicator, connected = await self._connect(ticket="bad-ticket")
            self.assertFalse(connected)

        async_to_sync(scenario)()

    def test_expired_ticket_is_rejected(self):
        async def scenario():
            with mock.patch("apps.automation.services.streaming.time.time", return_value=1000):
                stream_ticket = issue_execution_stream_ticket(self.execution, self.user)["ticket"]
            with mock.patch("apps.automation.services.streaming.time.time", return_value=1121):
                communicator, connected = await self._connect(ticket=stream_ticket)
            self.assertFalse(connected)

        async_to_sync(scenario)()

    def test_multiple_subscribers_receive_same_status_event(self):
        async def scenario():
            first_ticket = issue_execution_stream_ticket(self.execution, self.user)["ticket"]
            second_ticket = issue_execution_stream_ticket(self.execution, self.user)["ticket"]
            first, first_connected = await self._connect(ticket=first_ticket)
            second, second_connected = await self._connect(ticket=second_ticket)
            self.assertTrue(first_connected)
            self.assertTrue(second_connected)
            try:
                await first.receive_json_from(timeout=1)
                await second.receive_json_from(timeout=1)
                await sync_to_async(self._publish_paused_status)()
                first_event = await first.receive_json_from(timeout=1)
                second_event = await second.receive_json_from(timeout=1)
                self.assertEqual(first_event["type"], "execution.status_changed")
                self.assertEqual(second_event["type"], "execution.status_changed")
                self.assertEqual(first_event["payload"]["status"], ExecutionStatus.PAUSED)
            finally:
                await first.disconnect()
                await second.disconnect()

        async_to_sync(scenario)()


@override_settings(
    CHANNEL_LAYERS=_IN_MEMORY_CHANNEL_LAYERS,
    AUTOMATION_PLAYWRIGHT_PYTHON_BIN=sys.executable,
    AUTOMATION_SELENIUM_PYTHON_BIN=sys.executable,
    AUTOMATION_PLAYWRIGHT_WORKDIR=str(Path(__file__).resolve().parents[3]),
    AUTOMATION_SELENIUM_WORKDIR=str(Path(__file__).resolve().parents[3]),
)
class LiveExecutionRunnerTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user, self.org, self.team = _make_org_stack("runner.tn", "runner.user")
        self.project, _, self.test_case = _make_project_tree(self.team, self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _wait_for(self, predicate, *, timeout=8):
        started = time.time()
        while time.time() - started < timeout:
            if predicate():
                return True
            time.sleep(0.1)
        return False

    def test_runtime_helper_checkpoint_can_be_resumed(self):
        script = _make_script(
            self.test_case,
            """
from pathlib import Path
from apps.automation.runtime import artifact_created, report_step_passed, report_step_started, require_human_action
import os

artifact_dir = Path(os.environ["BIAT_ARTIFACT_DIR"])
note_path = artifact_dir / "manual-note.txt"
note_path.write_text("checkpoint reached", encoding="utf-8")

report_step_started(step_index=0, action="Open login page")
report_step_passed(step_index=0)
artifact_created(artifact_type="log", path=str(note_path), metadata={"kind": "note"})
report_step_started(step_index=1, action="Approve MFA")
require_human_action(title="Approve MFA", instructions="Complete the bank MFA flow", step_index=1)
report_step_passed(step_index=1)
report_step_started(step_index=2, action="Verify dashboard")
report_step_passed(step_index=2)
print("done")
""".strip(),
        )
        execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            browser="chromium",
            platform="desktop",
            script=script,
        )

        runner_thread = threading.Thread(target=run_execution, args=(str(execution.id),))
        runner_thread.start()

        checkpoint_ready = self._wait_for(
            lambda: ExecutionCheckpoint.objects.filter(
                execution=execution,
                status=ExecutionCheckpointStatus.PENDING,
            ).exists()
        )
        self.assertTrue(checkpoint_ready)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.PAUSED)

        checkpoint = ExecutionCheckpoint.objects.get(execution=execution)
        response = self.client.post(
            reverse(
                "execution-checkpoint-resume",
                kwargs={"execution_pk": execution.id, "checkpoint_pk": checkpoint.id},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        runner_thread.join(timeout=8)
        self.assertFalse(runner_thread.is_alive())
        execution.refresh_from_db()
        checkpoint.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.PASSED)
        self.assertEqual(checkpoint.status, ExecutionCheckpointStatus.RESOLVED)
        self.assertEqual(execution.steps.count(), 3)
        self.assertEqual(
            execution.steps.filter(status="passed").count(),
            3,
        )
        self.assertTrue(
            TestArtifact.objects.filter(
                execution=execution,
                artifact_type=ArtifactType.LOG,
                metadata_json__kind="note",
            ).exists()
        )

    def test_stop_signal_cancels_execution_waiting_at_checkpoint(self):
        script = _make_script(
            self.test_case,
            """
from apps.automation.runtime import report_step_started, require_human_action

report_step_started(step_index=0, action="Wait for manual approval")
require_human_action(title="Manual approval", instructions="Do something manual", step_index=0)
""".strip(),
        )
        execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            browser="chromium",
            platform="desktop",
            script=script,
        )
        runner_thread = threading.Thread(target=run_execution, args=(str(execution.id),))
        runner_thread.start()

        checkpoint_ready = self._wait_for(
            lambda: ExecutionCheckpoint.objects.filter(
                execution=execution,
                status=ExecutionCheckpointStatus.PENDING,
            ).exists()
        )
        self.assertTrue(checkpoint_ready)

        request_execution_stop(execution)
        runner_thread.join(timeout=8)
        self.assertFalse(runner_thread.is_alive())

        execution.refresh_from_db()
        checkpoint = ExecutionCheckpoint.objects.get(execution=execution)
        self.assertEqual(execution.status, ExecutionStatus.CANCELLED)
        self.assertEqual(checkpoint.status, ExecutionCheckpointStatus.CANCELLED)

    def test_old_scripts_without_runtime_events_still_use_case_steps(self):
        script = _make_script(
            self.test_case,
            "print('legacy runner path')",
        )
        execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            browser="chromium",
            platform="desktop",
            script=script,
        )

        run_execution(str(execution.id))
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.PASSED)
        self.assertEqual(execution.steps.count(), 1)
        self.assertEqual(execution.steps.first().status, "passed")


@override_settings(
    CHANNEL_LAYERS=_IN_MEMORY_CHANNEL_LAYERS,
    AUTOMATION_PLAYWRIGHT_PYTHON_BIN=sys.executable,
    AUTOMATION_SELENIUM_PYTHON_BIN=sys.executable,
)
class CheckpointExpiryTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user, self.org, self.team = _make_org_stack("expiry.tn", "expiry.user")
        self.project, _, self.test_case = _make_project_tree(self.team, self.user)
        script = _make_script(self.test_case, "print('expired')")
        self.execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            browser="chromium",
            platform="desktop",
            script=script,
        )
        self.execution.status = ExecutionStatus.PAUSED
        self.execution.save(update_fields=["status"])
        self.checkpoint = ExecutionCheckpoint.objects.create(
            execution=self.execution,
            checkpoint_key="stale-checkpoint",
            title="Stale checkpoint",
            instructions="Nobody resumed this one.",
            status=ExecutionCheckpointStatus.PENDING,
        )

    def test_expire_stale_checkpoint_marks_execution_error(self):
        past_time = self.checkpoint.requested_at - timedelta(hours=2)
        ExecutionCheckpoint.objects.filter(pk=self.checkpoint.pk).update(requested_at=past_time)
        expired_count = expire_stale_execution_checkpoints()
        self.assertEqual(expired_count, 1)
        self.execution.refresh_from_db()
        self.checkpoint.refresh_from_db()
        self.assertEqual(self.checkpoint.status, ExecutionCheckpointStatus.EXPIRED)
        self.assertEqual(self.execution.status, ExecutionStatus.ERROR)
