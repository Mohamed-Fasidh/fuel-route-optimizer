from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="FuelStation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("truckstop_id", models.IntegerField()),
                ("name", models.CharField(max_length=255)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("city", models.CharField(max_length=120)),
                ("state", models.CharField(max_length=2)),
                ("rack_id", models.IntegerField(blank=True, null=True)),
                ("retail_price", models.DecimalField(decimal_places=4, max_digits=7)),
                ("latitude", models.FloatField(blank=True, null=True)),
                ("longitude", models.FloatField(blank=True, null=True)),
                ("location_source", models.CharField(default="city_centroid", max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["state", "city"], name="api_fuelsta_state_cit_7d7d1e_idx"),
                    models.Index(fields=["retail_price"], name="api_fuelsta_retail_p_8cbd31_idx"),
                    models.Index(fields=["latitude", "longitude"], name="api_fuelsta_latitude_0dcd4d_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("truckstop_id", "name", "address", "city", "state"),
                        name="uniq_fuel_station_record",
                    )
                ],
            },
        ),
    ]
