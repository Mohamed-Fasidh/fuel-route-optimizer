from rest_framework import serializers


class RoutePlanRequestSerializer(serializers.Serializer):
    start_location = serializers.CharField(max_length=300)
    finish_location = serializers.CharField(max_length=300)
    vehicle_mpg = serializers.FloatField(default=10, min_value=0.1)
    tank_capacity_gallons = serializers.FloatField(default=50, min_value=1)
    max_range_miles = serializers.FloatField(default=500, min_value=1)

    def validate(self, attrs):
        calculated_range = attrs["vehicle_mpg"] * attrs["tank_capacity_gallons"]
        if calculated_range > attrs["max_range_miles"] + 1e-9:
            raise serializers.ValidationError(
                "vehicle_mpg × tank_capacity_gallons cannot exceed max_range_miles."
            )
        if attrs["max_range_miles"] > 500:
            raise serializers.ValidationError("max_range_miles cannot exceed 500.")
        return attrs
