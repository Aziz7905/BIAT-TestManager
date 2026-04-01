from django.shortcuts import get_object_or_404
from rest_framework import generics, parsers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.specs.serializers import (
    SpecificationSerializer,
    SpecificationSourceCreateSerializer,
    SpecificationSourceDetailSerializer,
    SpecificationSourceListSerializer,
    SpecificationSourceRecordSerializer,
    SpecificationSourceRecordUpdateSerializer,
    SpecificationSourceUpdateSerializer,
)
from apps.specs.services import (
    can_manage_specification_record,
    can_manage_specification_source,
    can_manage_specification_source_record,
    can_view_specifications,
    get_specification_queryset_for_actor,
    get_specification_source_queryset_for_actor,
    import_selected_records,
    parse_specification_source,
)


class SpecificationListCreateView(generics.ListCreateAPIView):
    serializer_class = SpecificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = get_specification_queryset_for_actor(self.request.user)
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def list(self, request, *args, **kwargs):
        if not can_view_specifications(request.user):
            raise PermissionDenied("You do not have permission to view specifications.")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not can_view_specifications(request.user):
            raise PermissionDenied("You do not have permission to create specifications.")
        return super().create(request, *args, **kwargs)


class SpecificationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SpecificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_specification_queryset_for_actor(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        if not can_view_specifications(request.user):
            raise PermissionDenied("You do not have permission to view this specification.")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        specification = self.get_object()
        if not can_manage_specification_record(request.user, specification):
            raise PermissionDenied("You do not have permission to update this specification.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        specification = self.get_object()
        if not can_manage_specification_record(request.user, specification):
            raise PermissionDenied("You do not have permission to delete this specification.")
        return super().destroy(request, *args, **kwargs)


class SpecificationSourceListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        queryset = get_specification_source_queryset_for_actor(self.request.user)
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SpecificationSourceCreateSerializer
        return SpecificationSourceListSerializer

    def list(self, request, *args, **kwargs):
        if not can_view_specifications(request.user):
            raise PermissionDenied("You do not have permission to view specification imports.")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not can_view_specifications(request.user):
            raise PermissionDenied("You do not have permission to create specification imports.")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source = serializer.save()
        source = get_specification_source_queryset_for_actor(request.user).get(pk=source.pk)
        detail_data = SpecificationSourceDetailSerializer(
            source,
            context=self.get_serializer_context(),
        ).data
        headers = self.get_success_headers(detail_data)
        return Response(detail_data, status=status.HTTP_201_CREATED, headers=headers)


class SpecificationSourceDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        return get_specification_source_queryset_for_actor(self.request.user)

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return SpecificationSourceUpdateSerializer
        return SpecificationSourceDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        if not can_view_specifications(request.user):
            raise PermissionDenied("You do not have permission to view this source.")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        source = self.get_object()
        if not can_manage_specification_source(request.user, source):
            raise PermissionDenied("You do not have permission to update this source.")
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(source, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        detail_serializer = SpecificationSourceDetailSerializer(
            source,
            context={"request": request},
        )
        return Response(detail_serializer.data)

    def destroy(self, request, *args, **kwargs):
        source = self.get_object()
        if not can_manage_specification_source(request.user, source):
            raise PermissionDenied("You do not have permission to delete this source.")
        return super().destroy(request, *args, **kwargs)


class SpecificationSourceParseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        source = get_object_or_404(get_specification_source_queryset_for_actor(request.user), pk=pk)
        if not can_manage_specification_source(request.user, source):
            raise PermissionDenied("You do not have permission to parse this source.")

        parse_specification_source(source)
        source = get_specification_source_queryset_for_actor(request.user).get(pk=pk)
        serializer = SpecificationSourceDetailSerializer(source, context={"request": request})
        return Response(serializer.data)


class SpecificationSourceRecordListView(generics.ListAPIView):
    serializer_class = SpecificationSourceRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_source(self):
        return get_object_or_404(
            get_specification_source_queryset_for_actor(self.request.user),
            pk=self.kwargs["source_pk"],
        )

    def get_queryset(self):
        return self.get_source().records.order_by("record_index")

    def list(self, request, *args, **kwargs):
        if not can_view_specifications(request.user):
            raise PermissionDenied("You do not have permission to view these source records.")
        return super().list(request, *args, **kwargs)


class SpecificationSourceRecordDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "record_pk"

    def get_source(self):
        return get_object_or_404(
            get_specification_source_queryset_for_actor(self.request.user),
            pk=self.kwargs["source_pk"],
        )

    def get_queryset(self):
        return self.get_source().records.all()

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return SpecificationSourceRecordUpdateSerializer
        return SpecificationSourceRecordSerializer

    def retrieve(self, request, *args, **kwargs):
        if not can_view_specifications(request.user):
            raise PermissionDenied("You do not have permission to view this source record.")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        record = self.get_object()
        if not can_manage_specification_source_record(request.user, record):
            raise PermissionDenied("You do not have permission to update this source record.")
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(record, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        detail_serializer = SpecificationSourceRecordSerializer(
            record,
            context={"request": request},
        )
        return Response(detail_serializer.data)


class SpecificationSourceImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        source = get_object_or_404(get_specification_source_queryset_for_actor(request.user), pk=pk)
        if not can_manage_specification_source(request.user, source):
            raise PermissionDenied("You do not have permission to import this source.")

        imported = import_selected_records(source, request.user)
        serializer = SpecificationSerializer(
            imported,
            many=True,
            context={"request": request},
        )
        return Response(
            {
                "imported_count": len(imported),
                "specifications": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
