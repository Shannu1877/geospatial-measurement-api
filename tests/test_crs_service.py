"""Unit tests for CRSService projection selection, formatting, and reprojection."""

import pytest
import pyproj
from shapely.geometry import Point, Polygon

from app.exceptions.custom_exceptions import MissingCRSException
from app.services.crs_service import CRSService


def test_utm_zone_selection_across_globe() -> None:
    """Verify UTM zone and hemisphere calculation for coordinates worldwide."""
    # Paris: Longitude 2.3522, Latitude 48.8566 -> UTM Zone 31N (EPSG:32631)
    epsg_paris = CRSService.get_utm_epsg_from_lon_lat(2.3522, 48.8566)
    assert epsg_paris == 32631

    # New York: Longitude -74.006, Latitude 40.7128 -> UTM Zone 18N (EPSG:32618)
    epsg_ny = CRSService.get_utm_epsg_from_lon_lat(-74.006, 40.7128)
    assert epsg_ny == 32618

    # Sydney: Longitude 151.2093, Latitude -33.8688 -> UTM Zone 56S (EPSG:32756)
    epsg_sydney = CRSService.get_utm_epsg_from_lon_lat(151.2093, -33.8688)
    assert epsg_sydney == 32756

    # Rio de Janeiro: Longitude -43.1729, Latitude -22.9068 -> UTM Zone 23S (EPSG:32723)
    epsg_rio = CRSService.get_utm_epsg_from_lon_lat(-43.1729, -22.9068)
    assert epsg_rio == 32723

    # Equator & Prime Meridian: (0.0, 0.0) -> UTM Zone 31N (EPSG:32631)
    epsg_zero = CRSService.get_utm_epsg_from_lon_lat(0.0, 0.0)
    assert epsg_zero == 32631


def test_polar_ups_fallbacks() -> None:
    """Verify Universal Polar Stereographic codes for high latitudes."""
    # North Pole (>84 N)
    assert CRSService.get_utm_epsg_from_lon_lat(10.0, 85.0) == 32661
    # South Pole (<-80 S)
    assert CRSService.get_utm_epsg_from_lon_lat(10.0, -85.0) == 32761


def test_reprojection_of_polygon_from_epsg4326() -> None:
    """Verify reprojection of a geometry from EPSG:4326 to UTM."""
    poly = Polygon([(2.35, 48.85), (2.36, 48.85), (2.36, 48.86), (2.35, 48.86), (2.35, 48.85)])
    source_crs = pyproj.CRS.from_epsg(4326)

    target_crs, was_transformed = CRSService.get_projected_crs_for_geometry(source_crs, poly)
    assert was_transformed is True
    assert target_crs.to_epsg() == 32631

    projected_geom = CRSService.transform_geometry(poly, source_crs, target_crs)
    # Projected coordinates should now be in meters (easting/northing), not small degrees
    assert projected_geom.bounds[0] > 10000.0
    assert projected_geom.area > 10000.0


def test_projected_crs_preservation() -> None:
    """Verify that an already suitable projected CRS (e.g. UTM) is preserved without transformation."""
    poly = Polygon([(500000, 4000000), (501000, 4000000), (501000, 4001000), (500000, 4000000)])
    utm_crs = pyproj.CRS.from_epsg(32632)

    target_crs, was_transformed = CRSService.get_projected_crs_for_geometry(utm_crs, poly)
    assert was_transformed is False
    assert target_crs.to_epsg() == 32632


def test_missing_crs_raises_exception() -> None:
    """Verify that attempting projection resolution on missing CRS raises MissingCRSException."""
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])
    with pytest.raises(MissingCRSException):
        CRSService.get_projected_crs_for_geometry(None, poly)
