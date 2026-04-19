from rest_framework import serializers


class ReportingProjectSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class RecentRunCardSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    status = serializers.CharField()
    trigger_type = serializers.CharField()
    plan_name = serializers.CharField(allow_null=True)
    created_by_name = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    started_at = serializers.DateTimeField(allow_null=True)
    ended_at = serializers.DateTimeField(allow_null=True)
    run_case_count = serializers.IntegerField()
    passed_case_count = serializers.IntegerField()
    failed_case_count = serializers.IntegerField()
    pass_rate = serializers.FloatField()


class ProjectDashboardSummarySerializer(serializers.Serializer):
    total_runs = serializers.IntegerField()
    active_runs = serializers.IntegerField()
    completed_runs = serializers.IntegerField()
    total_run_cases = serializers.IntegerField()
    passed_run_cases = serializers.IntegerField()
    failed_run_cases = serializers.IntegerField()
    pass_rate = serializers.FloatField()


class ProjectDashboardStatusBreakdownSerializer(serializers.Serializer):
    pending = serializers.IntegerField()
    running = serializers.IntegerField()
    passed = serializers.IntegerField()
    failed = serializers.IntegerField()
    skipped = serializers.IntegerField()


class ProjectDashboardOverviewSerializer(serializers.Serializer):
    project = ReportingProjectSerializer()
    summary = ProjectDashboardSummarySerializer()
    status_breakdown = ProjectDashboardStatusBreakdownSerializer()
    recent_runs = RecentRunCardSerializer(many=True)


class PassRateTrendPointSerializer(serializers.Serializer):
    date = serializers.DateField()
    total_results = serializers.IntegerField()
    passed_results = serializers.IntegerField()
    failed_results = serializers.IntegerField()
    pass_rate = serializers.FloatField()


class ProjectPassRateTrendSerializer(serializers.Serializer):
    project = ReportingProjectSerializer()
    days = serializers.IntegerField()
    points = PassRateTrendPointSerializer(many=True)


class FailureHotspotSerializer(serializers.Serializer):
    test_case_id = serializers.UUIDField()
    test_case_title = serializers.CharField()
    scenario_title = serializers.CharField()
    suite_name = serializers.CharField()
    failure_count = serializers.IntegerField()
    error_count = serializers.IntegerField()
    last_failure_at = serializers.DateTimeField(allow_null=True)


class ProjectFailureHotspotsSerializer(serializers.Serializer):
    project = ReportingProjectSerializer()
    days = serializers.IntegerField()
    items = FailureHotspotSerializer(many=True)
