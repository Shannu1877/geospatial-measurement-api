"""Comprehensive unit tests for CRSService projection selection, formatting, and reprojection."""

import pytest
import pyproj
from shapely.geometry import LineString, Polygon

from app.exceptions.custom_exceptions import InvalidCRSException, MissingCRSException
from app.services.crs_service import CRSService


def test_utm_zone_selection_worldwide() -> None:
    """Verify UTM zone and hemisphere calculation for coordinates across the globe."""
    # Paris: Longitude 2.3522, Latitude 48.8566 -> UTM Zone 31N (EPSG:32631)
    assert CRSService.get_utm_epsg_from_lon_lat(2.3522, 48.8566) == 32631

    # New York: Longitude -74.006, Latitude 40.7128 -> UTM Zone 18N (EPSG:32618)
    assert CRSService.get_utm_epsg_from_lon_lat(-74.006, 40.7128) == 32618

    # Sydney: Longitude 151.2093, Latitude -33.8688 -> UTM Zone 56S (EPSG:32756)
    assert CRSService.get_utm_epsg_from_lon_lat(151.2093, -33.8688) == 32756

    # Rio de Janeiro: Longitude -43.1729, Latitude -22.9068 -> UTM Zone 23S (EPSG:32723)
    assert CRSService.get_utm_epsg_from_lon_lat(-43.1729, -22.9068) == 32723

    # Equator & Prime Meridian: (0.0, 0.0) -> UTM Zone 31N (EPSG:32631)
    assert CRSService.get_utm_epsg_from_lon_lat(0.0, 0.0) == 32631


def test_polar_ups_fallbacks() -> None:
    """Verify Universal Polar Stereographic codes for extreme polar latitudes."""
    # North Pole (>84 N)
    assert CRSService.get_utm_epsg_from_lon_lat(10.0, 85.0) == 32661
    # South Pole (<-80 S)
    assert CRSService.get_utm_epsg_from_lon_lat(10.0, -85.0) == 32761


def test_reprojection_of_polygon_from_epsg4326() -> None:
    """Verify reprojection of geometry from geographic EPSG:4326 to UTM."""
    poly = Polygon([(2.35, 48.85), (2.36, 48.85), (2.36, 48.86), (2.35, 48.86), (2.35, 48.85)])
    source_crs = pyproj.CRS.from_epsg(4326)

    target_crs, was_transformed = CRSService.get_projected_crs_for_geometry(source_crs, poly)
    assert was_transformed is True
    assert target_crs.to_epsg() == 32631

    projected_geom = CRSService.transform_geometry(poly, source_crs, target_crs)
    assert projected_geom.bounds[0] > 10_000.0  # Coordinates in meters easting/northing
    assert projected_geom.area > 10_000.0


def test_web_mercator_reprojected_to_utm() -> None:
    """Verify that Web Mercator (EPSG:3857) is recognized and reprojected to UTM to fix distortion."""
    # Paris in EPSG:3857
    poly = Polygon([(261800, 6249000), (262800, 6249000), (262800, 6250000), (261800, 6250000), (261800, 6249000)])
    web_merc_crs = pyproj.CRS.from_epsg(3857)

    target_crs, was_transformed = CRSService.get_projected_crs_for_geometry(web_merc_crs, poly)
    assert was_transformed is True
    assert target_crs.to_epsg() == 32631


def test_projected_metric_crs_preserved() -> None:
    """Verify that an already suitable metric projected CRS (e.g. UTM) is preserved without transformation."""
    poly = Polygon([(500000, 4000000), (501000, 4000000), (501000, 4001000), (500000, 4000000)])
    utm_crs = pyproj.CRS.from_epsg(32632)

    target_crs, was_transformed = CRSService.get_projected_crs_for_geometry(utm_crs, poly)
    assert was_transformed is False
    assert target_crs.to_epsg() == 32632


def test_projected_non_metric_crs_reprojected() -> None:
    """Verify that a projected CRS in US Survey Feet (EPSG:2227) is reprojected to UTM for metric output."""
    poly = Polygon([(6000000, 2100000), (6001000, 2100000), (6001000, 2101000), (6000000, 2100000)])
    nad83_feet = pyproj.CRS.from_epsg(2227)

    target_crs, was_transformed = CRSService.get_projected_crs_for_geometry(nad83_feet, poly)
    assert was_transformed is True
    # Should reproject to California UTM zone (Zone 10N / EPSG:32610)
    assert target_crs.to_epsg() == 32610


def test_missing_crs_raises_exception() -> None:
    """Verify that attempting projection resolution on missing CRS raises MissingCRSException."""
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])
    with pytest.raises(MissingCRSException):
        CRSService.get_projected_crs_for_geometry(None, poly)


def test_invalid_crs_string_raises_exception() -> None:
    """Verify that parsing invalid CRS string raises InvalidCRSException."""
    with pytest.raises(InvalidCRSException):
        CRSService.parse_crs("INVALID:NOT_A_CRS_999999")
