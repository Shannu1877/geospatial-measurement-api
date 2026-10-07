"""Comprehensive tests for KML file ingestion, parsing, and measurement."""

from fastapi.testclient import TestClient
from tests.fixtures.sample_generators import create_sample_kml_bytes


def test_kml_polygon_area_calculation(client: TestClient) -> None:
    """Verify that a KML file containing a polygon returns an area measurement in m²."""
    kml_bytes = create_sample_kml_bytes()
    files = {"file": ("campus.kml", kml_bytes, "application/vnd.google-earth.kml+xml")}

    upload_resp = client.post("/api/files/", files=files)
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    features = meas_resp.json()["features"]

    poly_feat = next(f for f in features if f["geometry_type"] == "Polygon")
    assert poly_feat["measurement"] is not None
    assert poly_feat["measurement"]["type"] == "area"
    assert poly_feat["measurement"]["unit"] == "m²"
    assert poly_feat["measurement"]["value"] > 0


def test_kml_linestring_length_calculation(client: TestClient) -> None:
    """Verify that a KML file containing a LineString returns a length measurement in m."""
    kml_bytes = create_sample_kml_bytes()
    files = {"file": ("roads.kml", kml_bytes, "application/vnd.google-earth.kml+xml")}

    upload_resp = client.post("/api/files/", files=files)
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    features = meas_resp.json()["features"]

    line_feat = next(f for f in features if f["geometry_type"] == "LineString")
    assert line_feat["measurement"] is not None
    assert line_feat["measurement"]["type"] == "length"
    assert line_feat["measurement"]["unit"] == "m"
    assert line_feat["measurement"]["value"] > 0


def test_kml_point_null_measurement(client: TestClient) -> None:
    """Verify that a KML point feature has measurement null and status COMPLETED."""
    kml_bytes = create_sample_kml_bytes()
    files = {"file": ("pois.kml", kml_bytes, "application/vnd.google-earth.kml+xml")}

    upload_resp = client.post("/api/files/", files=files)
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    features = meas_resp.json()["features"]

    point_feat = next(f for f in features if f["geometry_type"] == "Point")
    assert point_feat["measurement"] is None
    assert point_feat["measurement_status"] == "COMPLETED"


def test_kml_properties_preservation(client: TestClient) -> None:
    """Verify that Placemark name and description attributes are preserved in properties."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Headquarters</name>
      <description>Corporate Main Office</description>
      <Point>
        <coordinates>-122.084,37.422,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>""".encode("utf-8")

    files = {"file": ("hq.kml", kml_content, "application/vnd.google-earth.kml+xml")}
    upload_resp = client.post("/api/files/", files=files)
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    features = meas_resp.json()["features"]
    assert len(features) == 1
    props = features[0]["properties"]
    assert props.get("Name") == "Headquarters" or props.get("name") == "Headquarters"
    assert "description" in [k.lower() for k in props.keys()]


def test_kml_3d_coordinates_handling(client: TestClient) -> None:
    """Verify that KML with 3D coordinates (with non-zero altitudes) processes without error."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Mountain Ridge Trail</name>
      <LineString>
        <coordinates>
          -122.0822,37.4222,150.0
          -122.0810,37.4214,320.5
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>""".encode("utf-8")

    files = {"file": ("ridge_trail.kml", kml_content, "application/vnd.google-earth.kml+xml")}
    upload_resp = client.post("/api/files/", files=files)
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    features = meas_resp.json()["features"]
    assert len(features) == 1
    assert features[0]["geometry_type"] == "LineString"
    assert features[0]["measurement"]["type"] == "length"
    assert features[0]["measurement"]["value"] > 0


def test_kml_uppercase_extension(client: TestClient) -> None:
    """Verify that uppercase .KML extension is accepted and processed successfully."""
    kml_bytes = create_sample_kml_bytes()
    files = {"file": ("UPPERCASE_TEST.KML", kml_bytes, "application/vnd.google-earth.kml+xml")}

    upload_resp = client.post("/api/files/", files=files)
    assert upload_resp.status_code == 200
    assert upload_resp.json()["filename"] == "UPPERCASE_TEST.KML"
    assert upload_resp.json()["status"] == "COMPLETED"


def test_kml_corrupted_xml_syntax(client: TestClient) -> None:
    """Verify that a KML file with unclosed or broken XML tags returns an error."""
    corrupted_kml = b"<?xml version='1.0'?><kml><Document><Placemark><name>Unclosed"
    files = {"file": ("broken.kml", corrupted_kml, "application/vnd.google-earth.kml+xml")}

    response = client.post("/api/files/", files=files)
    assert response.status_code in (400, 422)
    data = response.json()
    assert data["error"]["code"] in ("CORRUPT_GEOSPATIAL_FILE", "MALFORMED_GEOSPATIAL_FILE", "INVALID_FILE")


def test_kml_unicode_characters(client: TestClient) -> None:
    """Verify that KML with international and accented characters parses correctly."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Café de l'Étoile - 東京</name>
      <Point>
        <coordinates>139.6917,35.6895,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>""".encode("utf-8")

    files = {"file": ("intl.kml", kml_content, "application/vnd.google-earth.kml+xml")}
    upload_resp = client.post("/api/files/", files=files)
    assert upload_resp.status_code == 200
    file_id = upload_resp.json()["id"]

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    features = meas_resp.json()["features"]
    props = features[0]["properties"]
    prop_val = props.get("Name") or props.get("name")
    assert "Café" in prop_val or "東京" in prop_val
