from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from api.models import FuelStation


class RoutePlanAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        FuelStation.objects.create(
            truckstop_id=1,
            name="START FUEL",
            address="I-90",
            city="Chicago",
            state="IL",
            rack_id=1,
            retail_price="3.1000",
            latitude=41.8781,
            longitude=-87.6298,
            location_source="test",
        )
        FuelStation.objects.create(
            truckstop_id=2,
            name="CHEAP FUEL",
            address="I-55",
            city="Springfield",
            state="IL",
            rack_id=2,
            retail_price="2.8000",
            latitude=39.7817,
            longitude=-89.6501,
            location_source="test",
        )

    @patch("api.services.get_route")
    @patch("api.services.geocode_location")
    def test_route_plan_returns_json(self, mock_geocode, mock_route):
        from api.services import Point

        mock_geocode.side_effect = [
            (Point(41.8781, -87.6298), {"display_name": "Chicago", "cached": False}),
            (Point(39.7817, -89.6501), {"display_name": "Springfield", "cached": False}),
        ]
        mock_route.return_value = (
            {
                "distance": 350000,
                "duration": 14400,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-87.6298, 41.8781],
                        [-89.6501, 39.7817],
                    ],
                },
            },
            False,
        )

        response = self.client.post(
            "/api/v1/route-plan/",
            {
                "start_location": "Chicago, IL",
                "finish_location": "Springfield, IL",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("summary", response.data)
        self.assertIn("fuel_stops", response.data)
        self.assertIn("map", response.data)
