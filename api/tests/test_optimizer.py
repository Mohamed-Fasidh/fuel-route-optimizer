from decimal import Decimal

from django.test import SimpleTestCase

from api.services import Candidate, Point, optimize_fuel


class FakeStation:
    def __init__(self, station_id, name, price, city="Test", state="TX"):
        self.id = station_id
        self.truckstop_id = station_id
        self.name = name
        self.address = "Test address"
        self.city = city
        self.state = state
        self.retail_price = Decimal(str(price))
        self.latitude = 30.0
        self.longitude = -97.0
        self.location_source = "test"


class FuelOptimizerTests(SimpleTestCase):
    def candidate(self, station_id, position, price):
        return Candidate(
            station=FakeStation(station_id, f"Station {station_id}", price),
            route_position_miles=position,
            distance_from_route_miles=0.5,
        )

    def test_cheaper_reachable_station_gets_only_enough_fuel(self):
        candidates = [
            self.candidate(1, 0, 4.00),
            self.candidate(2, 300, 3.00),
            self.candidate(3, 600, 4.50),
        ]

        stops = optimize_fuel(
            candidates,
            route_distance=800,
            mpg=10,
            tank_capacity=50,
        )

        self.assertEqual(stops[0]["station_name"], "Station 1")
        self.assertAlmostEqual(stops[0]["purchase_gallons"], 30.0, places=2)
        self.assertEqual(stops[1]["station_name"], "Station 2")

    def test_destination_within_range_does_not_overfill(self):
        candidates = [
            self.candidate(1, 0, 3.00),
        ]

        stops = optimize_fuel(
            candidates,
            route_distance=250,
            mpg=10,
            tank_capacity=50,
        )

        self.assertEqual(len(stops), 1)
        self.assertAlmostEqual(stops[0]["purchase_gallons"], 25.0, places=2)

    def test_impossible_gap_raises(self):
        candidates = [
            self.candidate(1, 0, 3.00),
            self.candidate(2, 600, 2.00),
        ]

        with self.assertRaises(Exception):
            optimize_fuel(
                candidates,
                route_distance=700,
                mpg=10,
                tank_capacity=50,
            )
