# change: new file for Checkpoint 1. Turns our product data into clean JSON for the Flutter app.
#
# Our products don't live in the database, they come from the Open Food Facts API as plain dicts.
# So ProductCardSerializer is a plain serializers.Serializer (every field listed by hand),
# not a ModelSerializer like food_of_the_day's. Only FavoriteProduct is a real model, so that one IS a ModelSerializer.
from rest_framework import serializers

from main.models import FavoriteProduct


# change: one product card, the same info the Discover card shows on the website.
# The product dict must go through prepare_card() (views.py) first: that's what adds "spoonfeed", "tiles", "tags"...
class ProductCardSerializer(serializers.Serializer):
    # source = the key in the Open Food Facts dict. The name on the left is what Flutter sees,
    # so the app gets friendly names ("barcode") instead of the API's ("code")
    barcode = serializers.CharField(source="code", read_only=True)
    # default = what to send when the API left that key out, so Flutter always gets every key (no missing-key crashes)
    name = serializers.CharField(source="product_name", read_only=True, default="")
    brand = serializers.CharField(source="brands", read_only=True, default="")
    quantity = serializers.CharField(read_only=True, default="")
    image_url = serializers.CharField(source="image_front_small_url", read_only=True, default="")

    # a dot in source walks into a nested dict: product["spoonfeed"]["grade"]
    grade = serializers.CharField(source="spoonfeed.grade", read_only=True)             # our A–E grade, "?" if unknown
    score = serializers.FloatField(source="spoonfeed.score", read_only=True)            # 0–100, null if unknown

    # the three tiles on the card, already cleaned by grade_value() ("A", "B+", "4", or "?")
    nutri_score = serializers.CharField(source="tiles.nutri", read_only=True)
    green_score = serializers.CharField(source="tiles.green", read_only=True)
    nova = serializers.CharField(source="tiles.nova", read_only=True)

    # SerializerMethodField = the value comes from the get_<name> method below
    tags = serializers.SerializerMethodField()
    is_favorite = serializers.BooleanField(read_only=True, default=False)               # red heart for this user
    preference_fit = serializers.DictField(source="fit", read_only=True, default=None)  # "Fits your preferences" chip, null when logged out

    # the website's tags carry a CSS class too ("badge-success"); the app only needs the words
    def get_tags(self, product):
        return [tag["text"] for tag in product.get("tags", [])]


# change: a saved (favorited) product, straight from our own database table
class FavoriteProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = FavoriteProduct
        fields = ["barcode", "product_name", "created_at"]
        read_only_fields = fields   # the app never edits these directly, it only toggles through the API
