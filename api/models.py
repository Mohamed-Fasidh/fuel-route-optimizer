from django.db import models


class FuelStation(models.Model):
    truckstop_id = models.IntegerField()
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=2)
    rack_id = models.IntegerField(null=True, blank=True)
    retail_price = models.DecimalField(max_digits=7, decimal_places=4)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_source = models.CharField(max_length=40, default="city_centroid")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["state", "city"]),
            models.Index(fields=["retail_price"]),
            models.Index(fields=["latitude", "longitude"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["truckstop_id", "name", "address", "city", "state"],
                name="uniq_fuel_station_record",
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state}"
