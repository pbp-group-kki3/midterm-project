from rest_framework import serializers

from comparison.models import SavedComparison
from main.services.openfoodfacts import is_valid_barcode


class BarcodeListField(serializers.ListField):
    def __init__(self, **kwargs):
        super().__init__(min_length=2, max_length=3, **kwargs)

    def to_internal_value(self, data):
        values = super().to_internal_value(data)
        if not all(is_valid_barcode(value) and value.isascii() for value in values):
            raise serializers.ValidationError("Use barcode strings of 1 to 32 ASCII digits.")
        if len(set(values)) != len(values):
            raise serializers.ValidationError("Choose distinct products.")
        return values


class SavedComparisonSerializer(serializers.ModelSerializer):
    barcodes = BarcodeListField()

    class Meta:
        model = SavedComparison
        fields = ["id", "name", "notes", "barcodes", "created_at"]
        read_only_fields = ["id", "created_at"]


class ComparisonMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedComparison
        fields = ["name", "notes"]

    def validate(self, attrs):
        if "barcodes" in self.initial_data:
            raise serializers.ValidationError("A saved lineup's barcodes cannot be edited.")
        if not attrs:
            raise serializers.ValidationError("Provide a name or notes to update.")
        return attrs
