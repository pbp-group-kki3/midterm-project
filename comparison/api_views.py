from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from comparison.models import SavedComparison
from comparison.serializers import (
    BarcodeListField,
    ComparisonMetadataSerializer,
    SavedComparisonSerializer,
)
from comparison.services import (
    build_comparison_sections,
    build_nutrition_rows,
    load_comparison_products,
)


class MobileSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        # Native JSON clients use session cookies. Browser requests and form
        # submissions still require Django's CSRF check.
        browser_headers = ("Origin", "Referer", "Sec-Fetch-Mode")
        if any(header in request.headers for header in browser_headers):
            return super().enforce_csrf(request)
        if request.method != "DELETE" and request.content_type != "application/json":
            return super().enforce_csrf(request)


def comparison_table(barcodes):
    products, unavailable = load_comparison_products(barcodes)
    return {
        "products": [
            {
                "barcode": product["compare_barcode"],
                "name": product.get("product_name") or "Unnamed product",
                "brand": product.get("brands") or "",
                "image_url": product.get("image_front_small_url"),
            }
            for product in products
        ],
        "sections": build_comparison_sections(products, build_nutrition_rows(products)),
        "unavailable_barcodes": unavailable,
    }


@api_view(["GET"])
def preview(request):
    """Compare two or three products using repeated barcode query parameters."""
    barcodes = BarcodeListField().run_validation(request.query_params.getlist("barcode"))
    return Response(comparison_table(barcodes))


@never_cache
@api_view(["GET", "POST"])
@authentication_classes([MobileSessionAuthentication])
@permission_classes([IsAuthenticated])
def saved_list(request):
    """List the signed-in user's lineups or save a complete comparison."""
    records = SavedComparison.objects.filter(user=request.user)
    if request.method in ("GET", "HEAD"):
        return Response(SavedComparisonSerializer(records, many=True).data)

    serializer = SavedComparisonSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    barcodes = serializer.validated_data["barcodes"]
    existing = records.filter(barcodes=barcodes).first()
    if existing:
        return Response(SavedComparisonSerializer(existing).data)

    _, missing = load_comparison_products(barcodes)
    if missing:
        return Response(
            {"detail": "Some products could not be loaded.", "unavailable_barcodes": missing},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        # Serialize competing mobile saves for this owner on PostgreSQL.
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        existing = records.filter(barcodes=barcodes).first()
        if existing:
            return Response(SavedComparisonSerializer(existing).data)
        serializer.save(user=request.user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@never_cache
@api_view(["GET", "PATCH", "DELETE"])
@authentication_classes([MobileSessionAuthentication])
@permission_classes([IsAuthenticated])
def saved_detail(request, pk):
    """Reopen a saved lineup with current product data, edit metadata, or delete it."""
    records = SavedComparison.objects.filter(user=request.user, pk=pk)
    if request.method == "DELETE":
        deleted, _ = records.delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    if request.method == "PATCH":
        with transaction.atomic():
            record = get_object_or_404(records.select_for_update())
            metadata = ComparisonMetadataSerializer(record, data=request.data, partial=True)
            metadata.is_valid(raise_exception=True)
            metadata.save()
        return Response(SavedComparisonSerializer(record).data)

    record = get_object_or_404(records)
    return Response({**SavedComparisonSerializer(record).data, **comparison_table(record.barcodes)})
