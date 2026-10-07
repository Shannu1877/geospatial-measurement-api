"""Unit tests for MeasurementService geometry metrics calculation."""

import pyproj
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from app.schemas.common import MeasurementStatus
from app.services.measurement_service import MeasurementService


def test_polygon_area_calculation() -> None:
    """Verify Polygon area measurement in m² using projected UTM."""
    poly = Polygon([(10.0, 50.0), (10.01, 50.0), (10.01, 50.01), (10.0, 50.01), (10.0, 50.0)])
    crs = pyproj.CRS.from_epsg(4326)

    meas, status = MeasurementService.calculate_measurement(poly, crs)
    assert status == MeasurementStatus.COMPLETED
    assert meas is not None
    assert meas.type == "area"
    assert meas.unit == "m²"
    # Approx 715m x 1113m ≈ 795,000 m²
    assert 700000.0 < meas.value < 900000.0


def test_multipolygon_total_area() -> None:
    """Verify MultiPolygon calculates the aggregate area of all components."""
    poly1 = Polygon([(10.0, 50.0), (10.01, 50.0), (10.01, 50.01), (10.0, 50.01), (10.0, 50.0)])
    poly2 = Polygon([(10.02, 50.0), (10.03, 50.0), (10.03, 50.01), (10.02, 50.01), (10.02, 50.0)])
    multi_poly = MultiPolygon([poly1, poly2])
    crs = pyproj.CRS.from_epsg(4326)

    meas_single, _ = MeasurementService.calculate_measurement(poly1, crs)
    meas_multi, status = MeasurementService.calculate_measurement(multi_poly, crs)

    assert status == MeasurementStatus.COMPLETED
    assert meas_multi is not None
    assert meas_multi.type == "area"
    assert meas_multi.unit == "m²"
    # MultiPolygon area should be approximately double poly1
    assert abs(meas_multi.value - (meas_single.value * 2)) < 500.0


def test_linestring_length_calculation() -> None:
    """Verify LineString length measurement in meters."""
    line = LineString([(10.0, 50.0), (10.01, 50.0)])
    crs = pyproj.CRS.from_epsg(4326)

    meas, status = MeasurementService.calculate_measurement(line, crs)
    assert status == MeasurementStatus.COMPLETED
    assert meas is not None
    assert meas.type == "length"
    assert meas.unit == "m"
    # 0.01 degrees of longitude at 50 deg N is approx 715 meters
    assert 700.0 < meas.value < 730.0


def test_multilinestring_length_calculation() -> None:
    """Verify MultiLineString calculates total aggregate length."""
    line1 = LineString([(10.0, 50.0), (10.01, 50.0)])
    line2 = LineString([(10.01, 50.0), (10.02, 50.0)])
    multi_line = MultiLineString([line1, line2])
    crs = pyproj.CRS.from_epsg(4326)

    meas_single, _ = MeasurementService.calculate_measurement(line1, crs)
    meas_multi, status = MeasurementService.calculate_measurement(multi_line, crs)

    assert status == MeasurementStatus.COMPLETED
    assert meas_multi is not None
    assert meas_multi.type == "length"
    assert meas_multi.unit == "m"
    assert abs(meas_multi.value - (meas_single.value * 2)) < 5.0


def test_point_requires_no_measurement() -> None:
    """Verify Point geometry produces null measurement with COMPLETED status."""
    pt = Point(10.0, 50.0)
    crs = pyproj.CRS.from_epsg(4326)

    meas, status = MeasurementService.calculate_measurement(pt, crs)
    assert meas is None
    assert status == MeasurementStatus.COMPLETED


def test_multipoint_requires_no_measurement() -> None:
    """Verify MultiPoint geometry produces null measurement with COMPLETED status."""
    pts = MultiPoint([(10.0, 50.0), (10.01, 50.01)])
    crs = pyproj.CRS.from_epsg(4326)

    meas, status = MeasurementService.calculate_measurement(pts, crs)
    assert meas is None
    assert status == MeasurementStatus.COMPLETED


def test_unsupported_geometry_collection() -> None:
    """Verify unsupported geometry types do not crash and return UNSUPPORTED status."""
    geom_col = GeometryCollection([Point(0, 0), LineString([(0, 0), (1, 1)])])
    crs = pyproj.CRS.from_epsg(4326)

    meas, status = MeasurementService.calculate_measurement(geom_col, crs)
    assert meas is None
    assert status == MeasurementStatus.UNSUPPORTED


def test_missing_crs_handling() -> None:
    """Verify that features without CRS return MISSING_CRS status rather than crashing."""
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])

    meas, status = MeasurementService.calculate_measurement(poly, source_crs=None)
    assert meas is None
    assert status == MeasurementStatus.MISSING_CRS
