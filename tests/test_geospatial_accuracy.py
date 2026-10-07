"""Accuracy verification tests proving geographic coordinates are not measured in degrees."""

import pyproj
from shapely.geometry import LineString, Polygon

from app.schemas.common import MeasurementStatus
from app.services.measurement_service import MeasurementService


def test_epsg4326_polygon_not_measured_in_degrees() -> None:
    """CRITICAL VERIFICATION: Prove EPSG:4326 polygon is NOT measured directly in degrees.

    A 1.0 x 1.0 degree box near the equator has a naive geometric area of 1.0 degree².
    In reality, 1 degree at the equator is ~111.3 km, meaning the true geodesic/projected
    area is roughly 1.23 x 10^10 square meters (~12,300 km²).

    This test asserts that the result is in square meters and differs by 10 orders of
    magnitude from the raw degree² calculation.
    """
    poly = Polygon([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)])
    naive_degree_area = poly.area
    assert naive_degree_area == 1.0, "Raw shapely area on EPSG:4326 should be 1.0 deg²"

    crs = pyproj.CRS.from_epsg(4326)
    meas, status = MeasurementService.calculate_measurement(poly, crs)

    assert status == MeasurementStatus.COMPLETED
    assert meas is not None
    assert meas.unit == "m²"
    assert meas.type == "area"

    # Verify that the value is the true metric area, NOT 1.0
    assert meas.value > 10_000_000_000.0, f"Calculated area {meas.value} is too small for metric m²"
    assert meas.value != naive_degree_area

    # Check realistic UTM projected bounds for a 1-degree equatorial tile (~12.3 billion m²)
    assert 12_000_000_000.0 <= meas.value <= 13_000_000_000.0


def test_epsg4326_linestring_not_measured_in_degrees() -> None:
    """Prove EPSG:4326 linestring is measured in meters, not degrees.

    A 1.0 degree horizontal line along the equator has naive shapely length 1.0.
    In meters, it is approximately 111,320 meters.
    """
    line = LineString([(0.0, 0.0), (1.0, 0.0)])
    naive_degree_length = line.length
    assert naive_degree_length == 1.0, "Raw shapely length on EPSG:4326 should be 1.0 deg"

    crs = pyproj.CRS.from_epsg(4326)
    meas, status = MeasurementService.calculate_measurement(line, crs)

    assert status == MeasurementStatus.COMPLETED
    assert meas is not None
    assert meas.unit == "m"
    assert meas.type == "length"

    # Must be ~111,320 meters, NOT 1.0
    assert meas.value > 100_000.0
    assert meas.value != naive_degree_length
    assert 110_000.0 <= meas.value <= 112_000.0


def test_projected_crs_metric_accuracy() -> None:
    """Verify that an already projected metric CRS (e.g. UTM) produces exact metric measurements."""
    # 100m by 100m square in UTM Zone 32N (EPSG:32632)
    poly = Polygon([
        (500000.0, 5000000.0),
        (500100.0, 5000000.0),
        (500100.0, 5000100.0),
        (500000.0, 5000100.0),
        (500000.0, 5000000.0),
    ])
    utm_crs = pyproj.CRS.from_epsg(32632)
    meas, status = MeasurementService.calculate_measurement(poly, utm_crs)

    assert status == MeasurementStatus.COMPLETED
    assert meas is not None
    assert meas.unit == "m²"
    # Exact 100m * 100m = 10,000.0 m²
    assert meas.value == 10000.0
